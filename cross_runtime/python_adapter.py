#!/usr/bin/env python3
"""Python VM adapter for cross-runtime conformance testing.

Runs unified test vectors against the Python FluxMiniVM from
``runners.unified_runner`` and returns structured ``CrossRuntimeResult``
objects suitable for comparison with other runtimes (Go, Rust, etc.).

Usage (standalone)::

    python python_adapter.py                          # run all vectors
    python python_adapter.py --filter arith           # run only arithmetic
    python python_adapter.py --verbose                # show disassembly

Usage (as library)::

    from python_adapter import PythonAdapter
    adapter = PythonAdapter()
    result = adapter.run_vector(vector_dict)
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List, Optional

# Ensure the project root is importable so ``runners.unified_runner``
# resolves regardless of the caller's cwd.
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from runners.unified_runner import FluxMiniVM  # noqa: E402


# ===================================================================
#  Data types
# ===================================================================

@dataclass
class CrossRuntimeResult:
    """Structured result from running one test vector on a VM.

    Attributes:
        name:             Human-readable test vector name.
        runtime:          Runtime identifier (``"python"`` or ``"go"``).
        passed:           ``True`` when all expectations matched.
        halted:           Actual halted state after execution.
        error:            Actual error-flag state after execution.
        registers:        Actual non-zero register values ``{R<n>: value}``.
        expected_halted:  Expected halted state from the vector.
        expected_error:   Expected error state from the vector.
        expected_registers: Expected register map from the vector.
        register_mismatches: List of ``(reg_key, expected, actual)``.
        insn_count:       Number of instructions executed.
        elapsed_us:       Execution time in microseconds.
        details:          Human-readable mismatch details (empty if passed).
        skipped:          ``True`` if the test was skipped (e.g. slow tag).
        skip_reason:      Why the test was skipped.
    """
    name: str
    runtime: str = "python"
    passed: bool = False
    halted: bool = False
    error: bool = False
    registers: Dict[str, int] = field(default_factory=dict)
    expected_halted: Optional[bool] = None
    expected_error: Optional[bool] = None
    expected_registers: Dict[str, int] = field(default_factory=dict)
    register_mismatches: List[tuple] = field(default_factory=list)
    insn_count: int = 0
    elapsed_us: float = 0.0
    details: str = ""
    skipped: bool = False
    skip_reason: str = ""


# ===================================================================
#  Python adapter
# ===================================================================

class PythonAdapter:
    """Run cross-runtime test vectors on the Python ``FluxMiniVM``."""

    def __init__(self, verbose: bool = False, skip_slow: bool = True) -> None:
        self.verbose = verbose
        self.skip_slow = skip_slow

    # ------------------------------------------------------------------
    #  Bytecode parsing (mirrors ConformanceRunner._parse_bytecode)
    # ------------------------------------------------------------------

    @staticmethod
    def parse_bytecode(vec: dict) -> bytes:
        """Extract bytecode bytes from a vector dict.

        Accepts ``"bytecode"`` (list of ints) or ``"bytecode_hex"``
        (space-separated hex string).
        """
        raw = vec.get("bytecode") or vec.get("bytecode_hex")
        if raw is None:
            raise KeyError("vector missing 'bytecode' / 'bytecode_hex'")
        if isinstance(raw, list):
            return bytes(int(b) & 0xFF for b in raw)
        if isinstance(raw, str):
            s = raw.strip().removeprefix("0x").removeprefix("0X")
            return bytes.fromhex(s)
        raise TypeError(f"unsupported bytecode type: {type(raw).__name__}")

    # ------------------------------------------------------------------
    #  Register helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _parse_reg_map(raw: Any) -> Dict[str, int]:
        """Coerce a register description into ``{"R<n>": value}``."""
        if not raw:
            return {}
        if isinstance(raw, dict):
            out: Dict[str, int] = {}
            for k, v in raw.items():
                ks = str(k).upper().lstrip("R")
                idx = int(ks)
                out[f"R{idx}"] = int(v)
            return out
        if isinstance(raw, list):
            return {f"R{i}": int(v) for i, v in enumerate(raw) if i != 0}
        raise TypeError(f"unsupported registers type: {type(raw).__name__}")

    # ------------------------------------------------------------------
    #  Vector execution
    # ------------------------------------------------------------------

    def run_vector(self, vec: dict) -> CrossRuntimeResult:
        """Execute a single test vector and return a structured result.

        Parameters
        ----------
        vec : dict
            A test-vector dict as loaded from ``unified_test_vectors.json``.
            Must contain ``name``, ``bytecode_hex``, and ``expected_final``.
        """
        name = vec.get("name", "<unnamed>")
        tags = vec.get("tags", [])

        # Handle skip
        if self.skip_slow and "slow" in tags:
            return CrossRuntimeResult(
                name=name, runtime="python",
                skipped=True, skip_reason="slow test",
            )

        # Parse expected state
        exp_final = vec.get("expected_final", {})
        exp_regs_raw = exp_final.get("registers", {})
        exp_halted = exp_final.get("halted")
        exp_error = exp_final.get("error", False)
        expected_registers = self._parse_reg_map(exp_regs_raw)

        # Parse bytecode
        bytecode = self.parse_bytecode(vec)

        # Parse optional initial registers
        init_regs_raw = vec.get("initial_registers", {})
        init_regs = {}
        for k, v in init_regs_raw.items():
            ks = str(k).upper().lstrip("R")
            init_regs[int(ks)] = int(v)

        # Execute on Python VM
        vm = FluxMiniVM()
        for idx, val in init_regs.items():
            v = int(val) & vm._MASK32
            if v & vm._SIGN32:
                v -= 0x100000000
            vm.regs[idx] = v
        vm.regs[0] = 0

        t0 = time.monotonic()
        vm.execute(bytecode)
        elapsed = (time.monotonic() - t0) * 1_000_000  # us

        # Collect actual register state (only non-zero, plus any expected)
        actual_regs: Dict[str, int] = {}
        all_indices = set()
        for key in expected_registers:
            all_indices.add(int(key.lstrip("R")))
        for idx in sorted(all_indices):
            val = vm.rr(idx)
            actual_regs[f"R{idx}"] = val
        # Also include R0 explicitly if expected
        if "R0" in expected_registers:
            actual_regs["R0"] = vm.rr(0)

        # Compare registers
        mismatches: List[tuple] = []
        for key, exp_val in expected_registers.items():
            act_val = actual_regs.get(key, 0)
            if act_val != exp_val:
                mismatches.append((key, exp_val, act_val))

        # Compare halt / error
        halt_ok = (exp_halted is None) or (vm.halted == exp_halted)
        error_ok = (vm.error_flag == exp_error)

        passed = halt_ok and error_ok and len(mismatches) == 0

        # Build details
        parts: List[str] = []
        if not halt_ok:
            parts.append(f"halted: expected={exp_halted}, got={vm.halted}")
        if not error_ok:
            parts.append(f"error: expected={exp_error}, got={vm.error_flag}")
        for key, exp, act in mismatches:
            parts.append(f"{key}: expected={exp}, actual={act}")
        if vm.error_flag and not exp_error:
            parts.append("unexpected VM error flag")
        details = "; ".join(parts) if parts else ""

        return CrossRuntimeResult(
            name=name,
            runtime="python",
            passed=passed,
            halted=vm.halted,
            error=vm.error_flag,
            registers=actual_regs,
            expected_halted=exp_halted,
            expected_error=exp_error,
            expected_registers=expected_registers,
            register_mismatches=mismatches,
            insn_count=vm.insn_count,
            elapsed_us=elapsed,
            details=details,
        )

    # ------------------------------------------------------------------
    #  Batch execution
    # ------------------------------------------------------------------

    def run_all(self, vectors: List[dict]) -> List[CrossRuntimeResult]:
        """Run a list of test vectors and return results."""
        results: List[CrossRuntimeResult] = []
        for vec in vectors:
            result = self.run_vector(vec)
            results.append(result)
            if result.skipped:
                tag = "\033[33mSKIP\033[0m"
                print(f"  [{tag}] {result.name}  ({result.skip_reason})")
            elif result.passed:
                tag = "\033[32mPASS\033[0m"
                print(f"  [{tag}] {result.name}  ({result.elapsed_us:.0f} us)")
            else:
                tag = "\033[31mFAIL\033[0m"
                print(f"  [{tag}] {result.name}  ({result.elapsed_us:.0f} us)")
                print(f"         {result.details}")
            if self.verbose and not result.skipped:
                self._verbose(vec, result)
        return results

    def _verbose(self, vec: dict, result: CrossRuntimeResult) -> None:
        """Print verbose disassembly and register dump."""
        try:
            bc = self.parse_bytecode(vec)
            from runners.unified_runner import _disassemble  # noqa: E402
            print("         bytecode:")
            for off, raw, mnem in _disassemble(bc):
                print(f"           {off:04x}:  {raw:<14s}  {mnem}")
        except Exception:
            pass
        print(f"         halted={result.halted}  error={result.error}  "
              f"insns={result.insn_count}")
        if result.expected_registers:
            print("         registers:")
            for key in sorted(result.expected_registers,
                              key=lambda k: int(k.lstrip("R"))):
                exp = result.expected_registers[key]
                act = result.registers.get(key, 0)
                m = "OK" if act == exp else "MISMATCH"
                print(f"           {key}: expected={exp}, actual={act} [{m}]")


# ===================================================================
#  CLI
# ===================================================================

def _load_vectors(path: str) -> List[dict]:
    """Load vectors from a JSON file."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return data.get("vectors", data) if isinstance(data, dict) else data


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="python_adapter.py",
        description="Python VM adapter for cross-runtime conformance",
    )
    parser.add_argument(
        "--vectors", default=None,
        help="Path to unified_test_vectors.json (default: auto-detect)",
    )
    parser.add_argument("--filter", default=None, help="Name filter substring")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--include-slow", action="store_true",
                        help="Run slow-tagged tests")
    args = parser.parse_args(argv)

    # Locate vectors file
    vectors_path = args.vectors
    if not vectors_path:
        candidates = [
            Path(__file__).parent / "unified_test_vectors.json",
            Path.cwd() / "unified_test_vectors.json",
        ]
        for c in candidates:
            if c.is_file():
                vectors_path = str(c)
                break
    if not vectors_path:
        print("ERROR: cannot find unified_test_vectors.json", file=sys.stderr)
        return 1

    vectors = _load_vectors(vectors_path)
    if args.filter:
        fl = args.filter.lower()
        vectors = [v for v in vectors if fl in v.get("name", "").lower()]

    adapter = PythonAdapter(
        verbose=args.verbose,
        skip_slow=not args.include_slow,
    )

    print("=" * 60)
    print("  Cross-Runtime Conformance — Python VM Adapter")
    print("=" * 60)
    print(f"  vectors  : {vectors_path}")
    print(f"  count    : {len(vectors)}")
    print()

    results = adapter.run_all(vectors)

    total = len(results)
    ran = [r for r in results if not r.skipped]
    skipped = [r for r in results if r.skipped]
    passed = sum(1 for r in ran if r.passed)
    failed = sum(1 for r in ran if not r.passed)

    print()
    print(f"  Results: {passed} passed, {failed} failed, "
          f"{len(skipped)} skipped (of {total} total)")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
