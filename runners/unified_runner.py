#!/usr/bin/env python3
"""FLUX ISA Conformance Test Runner -- Unified ISA opcodes.

A self-contained Python script (zero external dependencies) that:
  1. Reads JSON test vectors from a directory
  2. Executes them on a built-in minimal FLUX VM
  3. Reports PASS / FAIL with optional verbose output
  4. Optionally emits JUnit XML

Usage
-----
    python unified_runner.py
    python unified_runner.py --vectors-dir runners/vectors/ --verbose
    python unified_runner.py --filter "arith" --junit-xml report.xml
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
import xml.etree.ElementTree as ET
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# ===================================================================
#  Unified ISA -- Opcode Definitions
# ===================================================================

# Format A -- 1 byte:  [op]
HALT: int = 0x00
NOP:  int = 0x01
RET:  int = 0x02

# Format B -- 2 bytes: [op][rd]
INC:  int = 0x08
DEC:  int = 0x09
NOT:  int = 0x0A
NEG:  int = 0x0B
PUSH: int = 0x0C
POP:  int = 0x0D

# Format F -- 4 bytes: [op][rd][imm16_lo][imm16_hi]
MOVI: int = 0x18
ADDI: int = 0x19
SUBI: int = 0x1A

# Format E -- 4 bytes: [op][rd][rs1][rs2]
ADD:    int = 0x20
SUB:    int = 0x21
MUL:    int = 0x22
DIV:    int = 0x23
MOD:    int = 0x24
AND:    int = 0x25
OR:     int = 0x26
XOR:    int = 0x27

# Format E -- comparisons: [op][rd][rs1][rs2]
CMP_EQ: int = 0x2C
CMP_LT: int = 0x2D
CMP_GT: int = 0x2E
CMP_NE: int = 0x2F

# Format F -- control flow: [op][cond][imm16_lo][imm16_hi]
JMP:  int = 0x43
JZ:   int = 0x44
JNZ:  int = 0x45

# Format F -- subroutine call: [op][0x00][imm16_lo][imm16_hi]
CALL: int = 0x4A

# Format B -- communication stubs: [op][rd]
TELL:  int = 0x50
ASK:   int = 0x51
BCAST: int = 0x53

# Canonical opcode table
_OPCODE_NAMES: Dict[int, str] = {
    HALT: "HALT", NOP: "NOP", RET: "RET",
    INC: "INC", DEC: "DEC", NOT: "NOT", NEG: "NEG", PUSH: "PUSH", POP: "POP",
    MOVI: "MOVI", ADDI: "ADDI", SUBI: "SUBI",
    ADD: "ADD", SUB: "SUB", MUL: "MUL", DIV: "DIV", MOD: "MOD",
    AND: "AND", OR: "OR", XOR: "XOR",
    CMP_EQ: "CMP_EQ", CMP_LT: "CMP_LT", CMP_GT: "CMP_GT", CMP_NE: "CMP_NE",
    JMP: "JMP", JZ: "JZ", JNZ: "JNZ", CALL: "CALL",
    TELL: "TELL", ASK: "ASK", BCAST: "BCAST",
}

_FMT_A = frozenset({HALT, NOP, RET})
_FMT_B = frozenset({INC, DEC, NOT, NEG, PUSH, POP, TELL, ASK, BCAST})
_FMT_E = frozenset({ADD, SUB, MUL, DIV, MOD, AND, OR, XOR,
                     CMP_EQ, CMP_LT, CMP_GT, CMP_NE})
_FMT_F = frozenset({MOVI, ADDI, SUBI, JMP, JZ, JNZ, CALL})


def _insn_size(op: int) -> int:
    """Byte-size of an instruction starting with *op*."""
    if op in _FMT_A:
        return 1
    if op in _FMT_B:
        return 2
    return 4                       # Format E and Format F


# ===================================================================
#  Disassembler (used for --verbose output)
# ===================================================================

def _disassemble_one(code: bytes, off: int) -> Tuple[str, int]:
    """Return ``(mnemonic_str, next_offset)`` for one instruction."""
    if off >= len(code):
        return ("??? (end)", off)

    op = code[off]
    name = _OPCODE_NAMES.get(op, f"UNKNOWN_0x{op:02X}")

    if _insn_size(op) == 1:
        return (name, off + 1)

    if _insn_size(op) == 2:
        rd = code[off + 1] if off + 1 < len(code) else 0
        return (f"{name} R{rd}", off + 2)

    # 4-byte instruction ------------------------------------------------
    rd  = code[off + 1] if off + 1 < len(code) else 0
    b2  = code[off + 2] if off + 2 < len(code) else 0
    b3  = code[off + 3] if off + 3 < len(code) else 0

    if op in _FMT_E:
        return (f"{name} R{rd}, R{b2}, R{b3}", off + 4)

    # Format F -- signed immediate
    raw = b2 | (b3 << 8)
    imm = raw - 0x10000 if raw >= 0x8000 else raw
    return (f"{name} R{rd}, {imm:#06x}  ({imm})", off + 4)


def _disassemble(code: bytes) -> List[Tuple[int, str, str]]:
    """Full disassembly: list of ``(offset, hex_bytes, mnemonic)``."""
    lines: List[Tuple[int, str, str]] = []
    off = 0
    while off < len(code):
        mnem, nxt = _disassemble_one(code, off)
        raw = " ".join(f"{code[i]:02x}" for i in range(off, nxt))
        lines.append((off, raw, mnem))
        off = nxt
    return lines


# ===================================================================
#  Test Result
# ===================================================================

@dataclass
class TestResult:
    """Outcome of a single conformance test vector."""
    name: str
    passed: bool
    halted_matched: bool = True
    error_matched: bool = True
    register_mismatches: List[Tuple[int, int, int]] = field(default_factory=list)
    vm_error_flag: bool = False
    elapsed_s: float = 0.0
    vector_file: str = ""
    details: str = ""

    @property
    def status_str(self) -> str:
        return "PASS" if self.passed else "FAIL"


# ===================================================================
#  FluxMiniVM -- Minimal FLUX Virtual Machine
# ===================================================================

class FluxMiniVM:
    """Minimal FLUX VM implementing the Unified ISA.

    * 64 general-purpose registers (R0 hardwired to 0)
    * Dict-based byte-addressable memory
    * List-based value stack
    * 32-bit signed register semantics (wrap on overflow)
    """

    NUM_REGS = 64
    _MASK32 = 0xFFFFFFFF
    _SIGN32 = 0x80000000
    _MAX_INSN = 10_000_000          # safety limit per execution

    def __init__(self) -> None:
        self.regs: List[int] = [0] * self.NUM_REGS
        self.memory: Dict[int, int] = {}
        self.stack: List[int] = []
        self.pc: int = 0
        self.halted: bool = False
        self.error_flag: bool = False
        self.insn_count: int = 0
        self._code: bytes = b""

    # -- register helpers -----------------------------------------------

    def rr(self, idx: int) -> int:
        """Read register (R0 is always 0)."""
        return 0 if idx == 0 else self.regs[idx]

    def wr(self, idx: int, val: int) -> None:
        """Write register (clamped to 32-bit signed; R0 stays 0)."""
        if idx == 0:
            return
        val &= self._MASK32
        if val & self._SIGN32:
            val -= 0x100000000
        self.regs[idx] = val

    # -- memory helpers -------------------------------------------------

    def mem_load(self, addr: int) -> int:
        return self.memory.get(addr & self._MASK32, 0)

    def mem_store(self, addr: int, val: int) -> None:
        self.memory[addr & self._MASK32] = val & 0xFF

    # -- fetch helpers --------------------------------------------------

    def _fb(self) -> int:                           # fetch byte
        if self.pc >= len(self._code):
            self.halted = True
            return 0
        b = self._code[self.pc]
        self.pc += 1
        return b

    def _fi16(self) -> int:                         # fetch signed imm16
        lo = self._fb()
        hi = self._fb()
        v = lo | (hi << 8)
        return v - 0x10000 if v >= 0x8000 else v

    # -- truncating division (C-style, toward zero) ---------------------

    @staticmethod
    def _tdiv(a: int, b: int) -> int:
        s = -1 if (a < 0) != (b < 0) else 1
        return s * (abs(a) // abs(b))

    # -- main loop ------------------------------------------------------

    def execute(self, code: bytes) -> None:
        self._code = code
        self.pc = 0
        self.halted = False
        self.error_flag = False
        self.insn_count = 0
        while not self.halted and self.pc < len(self._code):
            self._step()
            self.insn_count += 1
            if self.insn_count >= self._MAX_INSN:
                self.error_flag = True
                self.halted = True

    # -- single step ----------------------------------------------------

    def _step(self) -> None:
        op = self._fb()

        # ---- Format A -------------------------------------------------
        if op == HALT:
            self.halted = True
            return
        if op == NOP:
            return
        if op == RET:
            if not self.stack:
                self.error_flag = True
                self.halted = True
                return
            self.pc = self.stack.pop()
            return

        # ---- Format B (unary / stack / stubs) -------------------------
        if op in _FMT_B:
            rd = self._fb()
            if   op == INC:  self.wr(rd, self.rr(rd) + 1)
            elif op == DEC:  self.wr(rd, self.rr(rd) - 1)
            elif op == NOT:  self.wr(rd, ~self.rr(rd))
            elif op == NEG:  self.wr(rd, -self.rr(rd))
            elif op == PUSH: self.stack.append(self.rr(rd))
            elif op == POP:
                if not self.stack:
                    self.error_flag = True
                    self.halted = True
                    return
                self.wr(rd, self.stack.pop())
            elif op in (TELL, ASK, BCAST):
                # Stub: consume operand, set error flag
                self.error_flag = True
            return

        # ---- 4-byte instructions --------------------------------------
        rd = self._fb()

        # Format F -- immediate / control-flow
        if op in _FMT_F:
            imm = self._fi16()
            if   op == MOVI: self.wr(rd, imm)
            elif op == ADDI: self.wr(rd, self.rr(rd) + imm)
            elif op == SUBI: self.wr(rd, self.rr(rd) - imm)
            elif op == JMP:  self.pc += imm
            elif op == JZ:
                if self.rr(rd) == 0:
                    self.pc += imm
            elif op == JNZ:
                if self.rr(rd) != 0:
                    self.pc += imm
            elif op == CALL:
                self.stack.append(self.pc)     # push return address
                self.pc += imm
            return

        # Format E -- register-register ALU / comparison
        if op in _FMT_E:
            rs1 = self._fb()
            rs2 = self._fb()
            v1 = self.rr(rs1)
            v2 = self.rr(rs2)
            if   op == ADD:    self.wr(rd, v1 + v2)
            elif op == SUB:    self.wr(rd, v1 - v2)
            elif op == MUL:    self.wr(rd, v1 * v2)
            elif op == DIV:
                if v2 == 0:
                    self.error_flag = True
                    self.halted = True
                    return
                self.wr(rd, self._tdiv(v1, v2))
            elif op == MOD:
                if v2 == 0:
                    self.error_flag = True
                    self.halted = True
                    return
                self.wr(rd, v1 - self._tdiv(v1, v2) * v2)
            elif op == AND:    self.wr(rd, v1 & v2)
            elif op == OR:     self.wr(rd, v1 | v2)
            elif op == XOR:    self.wr(rd, v1 ^ v2)
            elif op == CMP_EQ: self.wr(rd, 1 if v1 == v2 else 0)
            elif op == CMP_LT: self.wr(rd, 1 if v1 <  v2 else 0)
            elif op == CMP_GT: self.wr(rd, 1 if v1 >  v2 else 0)
            elif op == CMP_NE: self.wr(rd, 1 if v1 != v2 else 0)
            return

        # Unknown opcode
        self.error_flag = True
        self.halted = True


# ===================================================================
#  Conformance Runner
# ===================================================================

class ConformanceRunner:
    """Load JSON test vectors, execute on FluxMiniVM, collect results."""

    def __init__(self, vectors_dir: str = "runners/vectors/",
                 verbose: bool = False) -> None:
        self.vectors_dir = vectors_dir
        self.verbose = verbose

    # ------------------------------------------------------------------
    #  Vector loading & parsing
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_bytecode(vec: dict) -> bytes:
        """Extract bytecode from a vector dict (supports multiple formats)."""
        raw = vec.get("bytecode") or vec.get("bytecode_hex")
        if raw is None:
            raise KeyError("vector missing 'bytecode' / 'bytecode_hex'")
        if isinstance(raw, list):
            return bytes(int(b) & 0xFF for b in raw)
        if isinstance(raw, str):
            s = raw.strip().removeprefix("0x").removeprefix("0X")
            if len(s) % 2:
                s = "0" + s
            return bytes.fromhex(s)
        raise TypeError(f"unsupported bytecode type: {type(raw).__name__}")

    @staticmethod
    def _parse_regs(raw: Any) -> Dict[int, int]:
        """Coerce a register description into ``{index: value}``.

        Accepts ``None``, a ``list`` (positional), or a ``dict`` whose
        keys may be ``"R1"``, ``"r1"``, ``"1"``, or ``1``.
        """
        if raw is None:
            return {}
        if isinstance(raw, list):
            return {i: int(v) for i, v in enumerate(raw) if i != 0}
        if isinstance(raw, dict):
            out: Dict[int, int] = {}
            for k, v in raw.items():
                ks = k.upper().lstrip("R") if isinstance(k, str) else str(k)
                idx = int(ks)
                if idx != 0:
                    out[idx] = int(v)
            return out
        raise TypeError(f"unsupported registers type: {type(raw).__name__}")

    @staticmethod
    def _parse_initial_regs(vec: dict) -> Dict[int, int]:
        """Parse initial register state from a vector."""
        return ConformanceRunner._parse_regs(vec.get("initial_registers"))

    @staticmethod
    def _parse_expected_regs(vec: dict) -> Dict[int, int]:
        """Parse expected register state from a vector (supports both formats).

        Accepts ``expected_registers`` (flat) or ``expected.gp`` (nested).
        """
        exp = vec.get("expected")
        if isinstance(exp, dict):
            # Nested format: expected.gp
            gp = exp.get("gp")
            if gp is not None:
                return ConformanceRunner._parse_regs(gp)
        # Flat format: expected_registers
        return ConformanceRunner._parse_regs(vec.get("expected_registers"))

    @staticmethod
    def _parse_expected_halt(vec: dict) -> Tuple[Optional[bool], Optional[bool]]:
        """Parse expected halt / error state.

        Returns ``(expected_halted, expected_error)``.
        Handles both flat fields (``expected_halted``, ``expected_error``) and
        nested format (``expected.final_state``).
        """
        exp_error: Optional[bool] = None
        exp_halted: Optional[bool] = None

        # Flat format
        eh = vec.get("expected_halted")
        if eh is not None:
            exp_halted = bool(eh)

        ee = vec.get("expected_error")
        if ee is not None:
            exp_error = bool(ee)

        # Nested format (overrides flat if present)
        exp = vec.get("expected")
        if isinstance(exp, dict):
            state = exp.get("final_state", "").upper()
            if state == "HALTED":
                exp_halted = True
            elif state == "RUNNING":
                exp_halted = False
            elif state == "ERRORED":
                exp_error = True

        return (exp_halted, exp_error)

    @staticmethod
    def _load_vectors(directory: str,
                      filter_str: Optional[str] = None
                      ) -> List[Tuple[str, dict]]:
        """Discover ``*.json`` files under *directory*."""
        vectors: List[Tuple[str, dict]] = []
        base = Path(directory)
        if not base.is_dir():
            print(f"WARNING: vectors directory not found: {directory}",
                  file=sys.stderr)
            return vectors
        for p in sorted(base.glob("**/*.json")):
            with open(p, "r", encoding="utf-8") as f:
                data = json.load(f)
            name = data.get("name") or data.get("id") or p.stem
            vid = data.get("id") or ""
            if filter_str:
                fl = filter_str.lower()
                if fl not in name.lower() and fl not in vid.lower():
                    continue
            vectors.append((str(p), data))
        return vectors

    # ------------------------------------------------------------------
    #  Single test execution
    # ------------------------------------------------------------------

    def run_test(self, path: str, vec: dict) -> Tuple[TestResult, FluxMiniVM]:
        """Execute one vector and return ``(result, vm)``."""
        name = vec.get("name") or vec.get("id") or Path(path).stem
        t0 = time.monotonic()

        bytecode = self._parse_bytecode(vec)
        initial = self._parse_initial_regs(vec)
        expected_regs = self._parse_expected_regs(vec)
        (exp_halted, exp_error) = self._parse_expected_halt(vec)

        # Build VM
        vm = FluxMiniVM()
        for idx, val in initial.items():
            v = int(val) & vm._MASK32
            if v & vm._SIGN32:
                v -= 0x100000000
            vm.regs[idx] = v
        vm.regs[0] = 0

        # Execute
        vm.execute(bytecode)
        elapsed = time.monotonic() - t0

        # Compare registers
        mismatches: List[Tuple[int, int, int]] = []
        for idx, exp_val in expected_regs.items():
            act_val = vm.rr(idx)
            if act_val != exp_val:
                mismatches.append((idx, exp_val, act_val))

        # Compare halt / error state
        halted_ok = True
        error_ok = True

        if exp_halted is not None and vm.halted != exp_halted:
            halted_ok = False
        if exp_error is not None and vm.error_flag != exp_error:
            error_ok = False

        # Error flag is acceptable if explicitly expected, otherwise it
        # counts as a failure.
        if exp_error is True:
            error_acceptable = vm.error_flag
        elif exp_error is False:
            error_acceptable = not vm.error_flag
        else:
            # No explicit expectation: error flag is a failure
            error_acceptable = not vm.error_flag

        passed = (len(mismatches) == 0 and halted_ok and error_acceptable)

        # Build details string
        parts: List[str] = []
        if not halted_ok:
            parts.append(f"halted: expected={exp_halted}, got={vm.halted}")
        if not error_ok:
            parts.append(f"error: expected={exp_error}, got={vm.error_flag}")
        for idx, exp, act in mismatches:
            parts.append(f"R{idx}: expected={exp}, actual={act}")
        if vm.error_flag:
            parts.append("VM error flag set")
        details = "; ".join(parts) if parts else "OK"

        result = TestResult(
            name=name,
            passed=passed,
            halted_matched=halted_ok,
            error_matched=error_ok,
            register_mismatches=mismatches,
            vm_error_flag=vm.error_flag,
            elapsed_s=elapsed,
            vector_file=path,
            details=details,
        )
        return result, vm

    # ------------------------------------------------------------------
    #  Run all matching vectors
    # ------------------------------------------------------------------

    def run_all(self, filter_str: Optional[str] = None
                ) -> List[TestResult]:
        vectors = self._load_vectors(self.vectors_dir, filter_str)
        results: List[TestResult] = []

        if not vectors:
            print(f"No test vectors found in {self.vectors_dir!r}",
                  file=sys.stderr)

        for path, data in vectors:
            result, vm = self.run_test(path, data)
            results.append(result)

            # Coloured status tag
            if result.passed:
                tag = "\033[32mPASS\033[0m"
            else:
                tag = "\033[31mFAIL\033[0m"
            ms = result.elapsed_s * 1000
            print(f"  [{tag}] {result.name}  ({ms:.2f} ms)")

            if self.verbose:
                self._verbose_output(result, vm, data)

        return results

    # ------------------------------------------------------------------
    #  Verbose helper
    # ------------------------------------------------------------------

    def _verbose_output(self, result: TestResult, vm: FluxMiniVM,
                        vec: dict) -> None:
        print(f"         file: {result.vector_file}")
        print(f"         halted={vm.halted}  error={vm.error_flag}  "
              f"insns={vm.insn_count}")

        if not result.passed:
            print(f"         >>> {result.details}")

        # Disassembly
        try:
            bc = self._parse_bytecode(vec)
            if bc:
                print("         bytecode:")
                for off, raw, mnem in _disassemble(bc):
                    print(f"           {off:04x}:  {raw:<14s}  {mnem}")
        except Exception:
            pass

        # Register comparison table
        initial = self._parse_initial_regs(vec)
        expected = self._parse_expected_regs(vec)
        all_idx = sorted(set(list(initial.keys()) + list(expected.keys())))
        if all_idx:
            print("         registers:")
            for idx in all_idx:
                ini = initial.get(idx, 0)
                act = vm.rr(idx)
                exp = expected.get(idx, None)
                exp_s = ""
                if exp is not None:
                    match = "OK" if act == exp else "MISMATCH"
                    exp_s = f"  expected={exp} [{match}]"
                print(f"           R{idx}: init={ini}, actual={act}{exp_s}")

    # ------------------------------------------------------------------
    #  JUnit XML output
    # ------------------------------------------------------------------

    @staticmethod
    def write_junit_xml(results: List[TestResult], output_path: str) -> None:
        """Write a JUnit-compatible XML report to *output_path*."""
        testsuite = ET.Element("testsuite")
        testsuite.set("name", "FLUX Unified ISA Conformance")
        testsuite.set("tests", str(len(results)))
        failures = sum(1 for r in results if not r.passed)
        testsuite.set("failures", str(failures))
        testsuite.set("errors", "0")
        testsuite.set("time", f"{sum(r.elapsed_s for r in results):.3f}")

        for r in results:
            tc = ET.SubElement(testsuite, "testcase")
            tc.set("name", r.name)
            tc.set("classname", "flux.unified")
            tc.set("time", f"{r.elapsed_s:.6f}")
            if not r.passed:
                fail = ET.SubElement(tc, "failure")
                fail.set("message", r.details)
                fail.set("type", "AssertionError")
                fail.text = r.details

        tree = ET.ElementTree(testsuite)
        ET.indent(tree, space="  ")
        parent = os.path.dirname(os.path.abspath(output_path))
        os.makedirs(parent, exist_ok=True)
        tree.write(output_path, encoding="unicode", xml_declaration=True)


# ===================================================================
#  CLI entry point
# ===================================================================

def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="unified_runner.py",
        description="FLUX ISA Conformance Test Runner -- Unified ISA opcodes",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  %(prog)s                                   # run all vectors (default dir)
  %(prog)s --vectors-dir ./my_vectors        # custom vectors directory
  %(prog)s --filter "arith" --verbose        # verbose, name filter
  %(prog)s --junit-xml report.xml            # emit JUnit XML report
""",
    )
    p.add_argument(
        "--vectors-dir", default="runners/vectors/",
        help="Directory with JSON test-vector files (default: runners/vectors/)",
    )
    p.add_argument(
        "--filter", default=None,
        help="Only run tests whose name contains this substring (case-insensitive)",
    )
    p.add_argument(
        "--verbose", "-v", action="store_true",
        help="Show disassembly, register dumps, and mismatch details",
    )
    p.add_argument(
        "--junit-xml", default=None, metavar="PATH",
        help="Write JUnit XML report to PATH",
    )
    return p


def main(argv: Optional[List[str]] = None) -> int:
    args = _build_parser().parse_args(argv)

    # Resolve vectors directory: explicit absolute, or relative to script dir
    vectors_dir = args.vectors_dir
    if not os.path.isabs(vectors_dir):
        script_parent = Path(__file__).resolve().parent
        candidate = script_parent / vectors_dir
        if candidate.is_dir():
            vectors_dir = str(candidate)
        else:
            # Fall back to project root (parent of script's dir)
            project_root = script_parent.parent
            candidate2 = project_root / vectors_dir
            if candidate2.is_dir():
                vectors_dir = str(candidate2)

    runner = ConformanceRunner(vectors_dir=vectors_dir, verbose=args.verbose)

    print("=" * 60)
    print("  FLUX Unified ISA Conformance Runner")
    print("=" * 60)
    print(f"  vectors directory : {vectors_dir}")
    if args.filter:
        print(f"  filter            : {args.filter!r}")
    print(f"  verbose           : {args.verbose}")
    print()

    results = runner.run_all(filter_str=args.filter)

    # Summary
    total = len(results)
    passed = sum(1 for r in results if r.passed)
    failed = total - passed

    print()
    if total == 0:
        print("  No tests executed.")
        rc = 1
    else:
        p = "\033[32m" + str(passed) + " passed\033[0m"
        f = "\033[31m" + str(failed) + " failed\033[0m"
        print(f"  Results: {total} tests, {p}, {f}")
        rc = 1 if failed else 0

    if args.junit_xml:
        runner.write_junit_xml(results, args.junit_xml)
        print(f"  JUnit XML -> {args.junit_xml}")

    return rc


if __name__ == "__main__":
    sys.exit(main())
