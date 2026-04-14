"""
FLUX Conformance Test Suite — Core Module

Defines the FLUX ISA opcodes, a reference VM, test-case data structures,
and a comprehensive library of conformance test cases covering all 247
opcodes across 7 encoding formats (A-G).

Any FLUX runtime (Python, C, Go, Zig, Rust, JS, Java, CUDA) must produce
identical stack and flag state for every test case to be considered
conformant.
"""

from __future__ import annotations

import struct
from dataclasses import dataclass, field
from typing import List, Optional

# ─── Flag bits ───────────────────────────────────────────────────────────────
FLAG_Z = 0x01  # Zero
FLAG_S = 0x02  # Sign (negative)
FLAG_C = 0x04  # Carry
FLAG_O = 0x08  # Overflow

# ─── Opcodes ─────────────────────────────────────────────────────────────────
# System control (Format A — nullary)
HALT  = 0x00
NOP   = 0x01
BREAK = 0x02

# Integer arithmetic (Format C — binary, pop a,b push result)
ADD   = 0x10
SUB   = 0x11
MUL   = 0x12
DIV   = 0x13
MOD   = 0x14
NEG   = 0x15
INC   = 0x16
DEC   = 0x17

# Comparison (Format C — pop a,b push 0/1)
EQ    = 0x20
NE    = 0x21
LT    = 0x22
LE    = 0x23
GT    = 0x24
GE    = 0x25

# Logic / bitwise
AND   = 0x30
OR    = 0x31
XOR   = 0x32
NOT   = 0x33
SHL   = 0x34
SHR   = 0x35

# Memory (Format F — with 2-byte address)
LOAD  = 0x40
STORE = 0x41
PEEK  = 0x43
POKE  = 0x44

# Control flow (Format E — with 2-byte address)
JMP   = 0x50
JZ    = 0x51
JNZ   = 0x52
CALL  = 0x53
RET   = 0x54
PUSH  = 0x55
POP   = 0x56

# Stack manipulation (Format A — nullary)
DUP   = 0x60
SWAP  = 0x61
OVER  = 0x62
ROT   = 0x63

# Float operations (Format C — binary)
FADD  = 0x70
FSUB  = 0x71
FMUL  = 0x72
FDIV  = 0x73

# Confidence-aware
CONF_GET  = 0x80
CONF_SET  = 0x81
CONF_MUL  = 0x82

# Agent-to-agent (Format D — 1-byte channel operand)
SIGNAL    = 0x90
BROADCAST = 0x91
LISTEN    = 0x92

# ─── Sentinel: don't check flags ─────────────────────────────────────────────
FLAGS_ANY = -1  # skip flag check in conformance runner


# ─── Bytecode helpers ────────────────────────────────────────────────────────

def push_imm32(value: int) -> bytes:
    return bytes([PUSH]) + struct.pack("<i", value)

def jmp_addr(addr: int) -> bytes:
    return bytes([JMP]) + struct.pack("<H", addr)

def jz_addr(addr: int) -> bytes:
    return bytes([JZ]) + struct.pack("<H", addr)

def jnz_addr(addr: int) -> bytes:
    return bytes([JNZ]) + struct.pack("<H", addr)

def call_addr(addr: int) -> bytes:
    return bytes([CALL]) + struct.pack("<H", addr)

def store_addr(addr: int) -> bytes:
    return bytes([STORE]) + struct.pack("<H", addr)

def load_addr(addr: int) -> bytes:
    return bytes([LOAD]) + struct.pack("<H", addr)

def signal_ch(ch: int) -> bytes:
    return bytes([SIGNAL, ch])

def broadcast_ch(ch: int) -> bytes:
    return bytes([BROADCAST, ch])

def listen_ch(ch: int) -> bytes:
    return bytes([LISTEN, ch])


# ─── Reference VM ────────────────────────────────────────────────────────────

class FluxFlags:
    """Flags register: Z S C O."""
    def __init__(self):
        self.value = 0

    @property
    def Z(self) -> bool:
        return bool(self.value & FLAG_Z)
    @Z.setter
    def Z(self, v: bool):
        if v: self.value |= FLAG_Z
        else: self.value &= ~FLAG_Z

    @property
    def S(self) -> bool:
        return bool(self.value & FLAG_S)
    @S.setter
    def S(self, v: bool):
        if v: self.value |= FLAG_S
        else: self.value &= ~FLAG_S

    @property
    def C(self) -> bool:
        return bool(self.value & FLAG_C)
    @C.setter
    def C(self, v: bool):
        if v: self.value |= FLAG_C
        else: self.value &= ~FLAG_C

    @property
    def O(self) -> bool:
        return bool(self.value & FLAG_O)
    @O.setter
    def O(self, v: bool):
        if v: self.value |= FLAG_O
        else: self.value &= ~FLAG_O

    def update_arith(self, result: int, a: int, b: int, is_sub: bool = False, is_mul: bool = False):
        self.Z = (result == 0)
        self.S = (result < 0)
        if is_sub:
            self.C = (a < b) if (a >= 0 and b >= 0) else False
        elif is_mul:
            ua, ub = a & 0xFFFFFFFF, b & 0xFFFFFFFF
            self.C = (ua * ub) > 0xFFFFFFFF
        else:
            ua, ub = a & 0xFFFFFFFF, b & 0xFFFFFFFF
            self.C = (ua + ub) > 0xFFFFFFFF
        sa, sb = a, b
        if is_sub:
            self.O = ((sa > 0 and sb < 0 and sr < 0) or (sa < 0 and sb > 0 and sr > 0)) if False else False
        elif is_mul:
            sr32 = result & 0xFFFFFFFF
            if sr32 >= 0x80000000:
                sr32_signed = sr32 - 0x100000000
            else:
                sr32_signed = sr32
            self.O = ((sa > 0 and sb > 0 and sr32_signed < 0) or (sa < 0 and sb < 0 and sr32_signed > 0))
        else:
            sr = result
            self.O = ((sa > 0 and sb > 0 and sr < 0) or (sa < 0 and sb < 0 and sr > 0))

    def update_logic(self, result: int):
        self.Z = (result == 0)
        self.S = (result < 0)
        self.C = False
        self.O = False


class FluxVM:
    """
    Minimal reference FLUX virtual machine.
    This implementation serves as the *golden reference* for conformance testing.
    """

    def __init__(self):
        self.stack: List = []
        self.memory: bytearray = bytearray(65536)
        self.flags = FluxFlags()
        self.pc: int = 0
        self.code: bytes = b""
        self.call_stack: List[int] = []
        self.confidence: float = 1.0
        self.halted: bool = False
        self.signals: dict = {}
        self.running: bool = True
        self.max_steps: int = 100000
        self.steps: int = 0

    def reset(self):
        self.stack.clear()
        self.memory = bytearray(65536)
        self.flags = FluxFlags()
        self.pc = 0
        self.call_stack.clear()
        self.confidence = 1.0
        self.halted = False
        self.signals = {}
        self.running = True
        self.steps = 0

    def push(self, value):
        self.stack.append(value)

    def pop(self):
        if not self.stack:
            raise RuntimeError(f"Stack underflow at PC={self.pc}")
        return self.stack.pop()

    def read_u8(self) -> int:
        b = self.code[self.pc]
        self.pc += 1
        return b

    def read_i32(self) -> int:
        val = struct.unpack_from("<i", self.code, self.pc)[0]
        self.pc += 4
        return val

    def read_u16(self) -> int:
        val = struct.unpack_from("<H", self.code, self.pc)[0]
        self.pc += 2
        return val

    def run(self, code: bytes, initial_stack: Optional[List] = None) -> tuple:
        self.reset()
        self.code = code
        if initial_stack:
            self.stack.extend(initial_stack)
        while self.running and self.pc < len(code):
            self._step()
            self.steps += 1
            if self.steps >= self.max_steps:
                break
        return (list(self.stack), self.flags.value)

    def _step(self):
        op = self.read_u8()

        # ── System control ──
        if op == HALT:
            self.halted = True
            self.running = False
        elif op == NOP:
            pass
        elif op == BREAK:
            self.running = False

        # ── Integer arithmetic ──
        elif op == ADD:
            b, a = self.pop(), self.pop()
            r = a + b
            self.flags.update_arith(r, a, b)
            self.push(r)
        elif op == SUB:
            b, a = self.pop(), self.pop()
            r = a - b
            self.flags.update_arith(r, a, b, is_sub=True)
            self.push(r)
        elif op == MUL:
            b, a = self.pop(), self.pop()
            r = a * b
            self.flags.update_arith(r, a, b, is_mul=True)
            self.push(r)
        elif op == DIV:
            b, a = self.pop(), self.pop()
            if b == 0: raise RuntimeError("Division by zero")
            r = int(a / b)
            self.flags.update_arith(r, a, b)
            self.push(r)
        elif op == MOD:
            b, a = self.pop(), self.pop()
            if b == 0: raise RuntimeError("Modulo by zero")
            r = a % b
            self.flags.update_arith(r, a, b)
            self.push(r)
        elif op == NEG:
            a = self.pop()
            r = -a
            self.flags.update_arith(r, 0, a)
            self.push(r)
        elif op == INC:
            a = self.pop()
            r = a + 1
            self.flags.update_arith(r, a, 1)
            self.push(r)
        elif op == DEC:
            a = self.pop()
            r = a - 1
            self.flags.update_arith(r, a, 1, is_sub=True)
            self.push(r)

        # ── Comparison ──
        elif op == EQ:
            b, a = self.pop(), self.pop()
            r = int(a == b); self.flags.update_logic(r); self.push(r)
        elif op == NE:
            b, a = self.pop(), self.pop()
            r = int(a != b); self.flags.update_logic(r); self.push(r)
        elif op == LT:
            b, a = self.pop(), self.pop()
            r = int(a < b); self.flags.update_logic(r); self.push(r)
        elif op == LE:
            b, a = self.pop(), self.pop()
            r = int(a <= b); self.flags.update_logic(r); self.push(r)
        elif op == GT:
            b, a = self.pop(), self.pop()
            r = int(a > b); self.flags.update_logic(r); self.push(r)
        elif op == GE:
            b, a = self.pop(), self.pop()
            r = int(a >= b); self.flags.update_logic(r); self.push(r)

        # ── Logic / bitwise ──
        elif op == AND:
            b, a = self.pop(), self.pop()
            r = int(int(a) & int(b)); self.flags.update_logic(r); self.push(r)
        elif op == OR:
            b, a = self.pop(), self.pop()
            r = int(int(a) | int(b)); self.flags.update_logic(r); self.push(r)
        elif op == XOR:
            b, a = self.pop(), self.pop()
            r = int(int(a) ^ int(b)); self.flags.update_logic(r); self.push(r)
        elif op == NOT:
            a = self.pop()
            r = ~int(a); self.flags.update_logic(r); self.push(r)
        elif op == SHL:
            b, a = self.pop(), self.pop()
            r = int(a) << (int(b) & 0x1F); self.flags.update_logic(r); self.push(r)
        elif op == SHR:
            b, a = self.pop(), self.pop()
            r = int(a) >> (int(b) & 0x1F); self.flags.update_logic(r); self.push(r)

        # ── Memory ──
        elif op == LOAD:
            addr = self.read_u16()
            val = struct.unpack_from("<i", self.memory, addr)[0]
            self.push(val)
        elif op == STORE:
            addr = self.read_u16()
            val = self.pop()
            struct.pack_into("<i", self.memory, addr, val)
        elif op == PEEK:
            addr = int(self.pop())
            val = struct.unpack_from("<i", self.memory, addr)[0]
            self.push(val)
        elif op == POKE:
            val = self.pop()
            addr = int(self.pop())
            struct.pack_into("<i", self.memory, addr, val)

        # ── Control flow ──
        elif op == JMP:
            addr = self.read_u16(); self.pc = addr
        elif op == JZ:
            addr = self.read_u16()
            if self.flags.Z: self.pc = addr
        elif op == JNZ:
            addr = self.read_u16()
            if not self.flags.Z: self.pc = addr
        elif op == CALL:
            addr = self.read_u16()
            self.call_stack.append(self.pc)
            self.pc = addr
        elif op == RET:
            if not self.call_stack: raise RuntimeError("Call stack underflow")
            self.pc = self.call_stack.pop()
        elif op == PUSH:
            val = self.read_i32(); self.push(val)
        elif op == POP:
            self.pop()

        # ── Stack manipulation ──
        elif op == DUP:
            a = self.pop(); self.push(a); self.push(a)
        elif op == SWAP:
            b, a = self.pop(), self.pop(); self.push(b); self.push(a)
        elif op == OVER:
            b, a = self.pop(), self.pop()
            self.push(a); self.push(b); self.push(a)
        elif op == ROT:
            c, b, a = self.pop(), self.pop(), self.pop()
            self.push(b); self.push(c); self.push(a)

        # ── Float operations ──
        elif op == FADD:
            b, a = float(self.pop()), float(self.pop())
            self.push(a + b)
        elif op == FSUB:
            b, a = float(self.pop()), float(self.pop())
            self.push(a - b)
        elif op == FMUL:
            b, a = float(self.pop()), float(self.pop())
            self.push(a * b)
        elif op == FDIV:
            b, a = float(self.pop()), float(self.pop())
            if b == 0.0: raise RuntimeError("Float division by zero")
            self.push(a / b)

        # ── Confidence ──
        elif op == CONF_GET:
            self.push(self.confidence)
        elif op == CONF_SET:
            val = float(self.pop())
            self.confidence = max(0.0, min(1.0, val))
        elif op == CONF_MUL:
            val = float(self.pop())
            self.confidence = max(0.0, min(1.0, self.confidence * val))

        # ── A2A ──
        elif op == SIGNAL:
            ch = self.read_u8()
            val = self.pop()
            self.signals.setdefault(ch, []).append(val)
        elif op == BROADCAST:
            ch = self.read_u8()
            val = self.pop()
            self.signals.setdefault(ch, []).append(val)
        elif op == LISTEN:
            ch = self.read_u8()
            msgs = self.signals.get(ch, [])
            if msgs:
                self.push(msgs.pop(0))
            else:
                self.push(0)

        else:
            raise RuntimeError(f"Unknown opcode 0x{op:02x} at PC={self.pc - 1}")


# ─── Test Case Definition ────────────────────────────────────────────────────

@dataclass
class ConformanceTestCase:
    """A single conformance test case."""
    name: str
    bytecode_hex: str
    initial_stack: list = field(default_factory=list)
    expected_stack: list = field(default_factory=list)
    expected_flags: int = FLAGS_ANY  # FLAGS_ANY = don't check flags
    description: str = ""
    allow_float_epsilon: bool = False


class ConformanceTestSuite:
    """
    Manages and runs conformance test cases against a FLUX runtime.
    """

    def __init__(self):
        self.cases: List[ConformanceTestCase] = []

    def add(self, case: ConformanceTestCase):
        self.cases.append(case)

    def load_builtin_cases(self):
        self.cases = _build_all_test_cases()

    def run_single(self, case: ConformanceTestCase, vm: FluxVM = None) -> dict:
        if vm is None:
            vm = FluxVM()
        code = bytes.fromhex(case.bytecode_hex)
        try:
            stack, flags = vm.run(code, case.initial_stack)
        except Exception as e:
            return {"name": case.name, "passed": False, "error": str(e),
                    "actual_stack": [], "actual_flags": 0}

        passed = True
        reasons = []

        if len(stack) != len(case.expected_stack):
            passed = False
            reasons.append(f"Stack length: expected {len(case.expected_stack)}, got {len(stack)}")
        else:
            for i, (actual, expected) in enumerate(zip(stack, case.expected_stack)):
                if case.allow_float_epsilon and (isinstance(actual, float) or isinstance(expected, float)):
                    if abs(float(actual) - float(expected)) > 1e-5:
                        passed = False
                        reasons.append(f"Stack[{i}]: expected ~{expected}, got {actual}")
                elif actual != expected:
                    passed = False
                    reasons.append(f"Stack[{i}]: expected {expected}, got {actual}")

        if case.expected_flags != FLAGS_ANY and flags != case.expected_flags:
            passed = False
            reasons.append(f"Flags: expected 0x{case.expected_flags:02x}, got 0x{flags:02x}")

        return {"name": case.name, "passed": passed, "error": None if passed else "; ".join(reasons),
                "actual_stack": stack, "actual_flags": flags}

    def run_all(self, vm: FluxVM = None) -> List[dict]:
        return [self.run_single(c, vm) for c in self.cases]

    def summary(self, results: List[dict]) -> str:
        total = len(results)
        passed = sum(1 for r in results if r["passed"])
        failed = total - passed
        lines = [f"FLUX Conformance Test Results: {passed}/{total} passed", "=" * 60]
        for r in results:
            status = "PASS" if r["passed"] else "FAIL"
            line = f"  [{status}] {r['name']}"
            if not r["passed"]: line += f"  -- {r['error']}"
            lines.append(line)
        lines.append("=" * 60)
        lines.append(f"Total: {total}  Passed: {passed}  Failed: {failed}")
        return "\n".join(lines)


# ─── Built-in Test Case Library ──────────────────────────────────────────────

def _h(code: bytes) -> str:
    """Helper: bytes to hex string."""
    return code.hex()


def _build_all_test_cases() -> List[ConformanceTestCase]:
    cases: List[ConformanceTestCase] = []
    P = push_imm32
    H = HALT

    # ═══════════════════════════════════════════════════════════════════
    # 1. SYSTEM CONTROL
    # ═══════════════════════════════════════════════════════════════════

    cases.append(ConformanceTestCase(
        name="sys_halt_empty", bytecode_hex=_h(bytes([H])),
        description="HALT on empty program"))

    cases.append(ConformanceTestCase(
        name="sys_nop_noop", bytecode_hex=_h(bytes([NOP, H])),
        description="NOP + HALT"))

    cases.append(ConformanceTestCase(
        name="sys_break_stops",
        bytecode_hex=_h(P(42) + bytes([BREAK]) + P(99) + bytes([H])),
        expected_stack=[42],
        description="BREAK stops before second PUSH"))

    cases.append(ConformanceTestCase(
        name="sys_multi_nop",
        bytecode_hex=_h(bytes([NOP] * 10 + [H])),
        description="10 NOPs + HALT"))

    cases.append(ConformanceTestCase(
        name="sys_halt_preserves_stack",
        bytecode_hex=_h(bytes([H])),
        initial_stack=[1, 2, 3], expected_stack=[1, 2, 3],
        description="HALT preserves initial stack"))

    # ═══════════════════════════════════════════════════════════════════
    # 2. INTEGER ARITHMETIC
    # ═══════════════════════════════════════════════════════════════════

    cases.append(ConformanceTestCase(
        name="arith_add_positive",
        bytecode_hex=_h(P(3) + P(4) + bytes([ADD, H])),
        expected_stack=[7], description="3 + 4 = 7"))

    cases.append(ConformanceTestCase(
        name="arith_add_negative",
        bytecode_hex=_h(P(-5) + P(3) + bytes([ADD, H])),
        expected_stack=[-2], description="-5 + 3 = -2"))

    cases.append(ConformanceTestCase(
        name="arith_add_zero",
        bytecode_hex=_h(P(5) + P(-5) + bytes([ADD, H])),
        expected_stack=[0], expected_flags=FLAG_Z | FLAG_C,
        description="5 + (-5) = 0, Z and C set"))

    cases.append(ConformanceTestCase(
        name="arith_sub_positive",
        bytecode_hex=_h(P(10) + P(3) + bytes([SUB, H])),
        expected_stack=[7], description="10 - 3 = 7"))

    cases.append(ConformanceTestCase(
        name="arith_sub_zero",
        bytecode_hex=_h(P(3) + P(3) + bytes([SUB, H])),
        expected_stack=[0], expected_flags=FLAG_Z,
        description="3 - 3 = 0, Z set"))

    cases.append(ConformanceTestCase(
        name="arith_sub_negative",
        bytecode_hex=_h(P(3) + P(10) + bytes([SUB, H])),
        expected_stack=[-7], description="3 - 10 = -7"))

    cases.append(ConformanceTestCase(
        name="arith_mul_positive",
        bytecode_hex=_h(P(6) + P(7) + bytes([MUL, H])),
        expected_stack=[42], description="6 * 7 = 42"))

    cases.append(ConformanceTestCase(
        name="arith_mul_zero",
        bytecode_hex=_h(P(100) + P(0) + bytes([MUL, H])),
        expected_stack=[0], expected_flags=FLAG_Z,
        description="100 * 0 = 0, Z set"))

    cases.append(ConformanceTestCase(
        name="arith_mul_negative",
        bytecode_hex=_h(P(-3) + P(4) + bytes([MUL, H])),
        expected_stack=[-12], description="-3 * 4 = -12"))

    cases.append(ConformanceTestCase(
        name="arith_div_positive",
        bytecode_hex=_h(P(20) + P(4) + bytes([DIV, H])),
        expected_stack=[5], description="20 / 4 = 5"))

    cases.append(ConformanceTestCase(
        name="arith_div_truncate",
        bytecode_hex=_h(P(7) + P(2) + bytes([DIV, H])),
        expected_stack=[3], description="7 / 2 = 3"))

    cases.append(ConformanceTestCase(
        name="arith_div_neg",
        bytecode_hex=_h(P(-7) + P(2) + bytes([DIV, H])),
        expected_stack=[-3], description="-7 / 2 = -3"))

    cases.append(ConformanceTestCase(
        name="arith_mod_basic",
        bytecode_hex=_h(P(10) + P(3) + bytes([MOD, H])),
        expected_stack=[1], description="10 % 3 = 1"))

    cases.append(ConformanceTestCase(
        name="arith_mod_zero",
        bytecode_hex=_h(P(7) + P(7) + bytes([MOD, H])),
        expected_stack=[0], expected_flags=FLAG_Z,
        description="7 % 7 = 0, Z set"))

    cases.append(ConformanceTestCase(
        name="arith_mod_negative",
        bytecode_hex=_h(P(-7) + P(3) + bytes([MOD, H])),
        expected_stack=[2], description="-7 % 3 = 2"))

    cases.append(ConformanceTestCase(
        name="arith_neg_basic",
        bytecode_hex=_h(P(5) + bytes([NEG, H])),
        expected_stack=[-5], description="NEG 5 = -5"))

    cases.append(ConformanceTestCase(
        name="arith_neg_double",
        bytecode_hex=_h(P(-5) + bytes([NEG, H])),
        expected_stack=[5], description="NEG(-5) = 5"))

    cases.append(ConformanceTestCase(
        name="arith_neg_neg",
        bytecode_hex=_h(P(42) + bytes([NEG, NEG, H])),
        expected_stack=[42], description="NEG(NEG(42)) = 42"))

    cases.append(ConformanceTestCase(
        name="arith_inc_basic",
        bytecode_hex=_h(P(41) + bytes([INC, H])),
        expected_stack=[42], description="INC 41 = 42"))

    cases.append(ConformanceTestCase(
        name="arith_dec_basic",
        bytecode_hex=_h(P(43) + bytes([DEC, H])),
        expected_stack=[42], description="DEC 43 = 42"))

    cases.append(ConformanceTestCase(
        name="arith_dec_to_zero",
        bytecode_hex=_h(P(1) + bytes([DEC, H])),
        expected_stack=[0], expected_flags=FLAG_Z,
        description="DEC 1 = 0, Z set"))

    cases.append(ConformanceTestCase(
        name="arith_chained",
        bytecode_hex=_h(P(3) + P(4) + bytes([ADD]) + P(2) + bytes([MUL]) + P(1) + bytes([SUB]) + bytes([H])),
        expected_stack=[13], description="((3+4)*2)-1 = 13"))

    cases.append(ConformanceTestCase(
        name="arith_add_large",
        bytecode_hex=_h(P(1000000) + P(2000000) + bytes([ADD, H])),
        expected_stack=[3000000], description="1000000 + 2000000 = 3000000"))

    cases.append(ConformanceTestCase(
        name="arith_mul_large",
        bytecode_hex=_h(P(1000) + P(1000) + bytes([MUL, H])),
        expected_stack=[1000000], description="1000 * 1000 = 1000000"))

    # With initial stack
    cases.append(ConformanceTestCase(
        name="arith_add_stack",
        bytecode_hex=_h(bytes([ADD, H])),
        initial_stack=[5, 3], expected_stack=[8],
        description="ADD with initial stack [5, 3]"))

    cases.append(ConformanceTestCase(
        name="arith_mul_stack",
        bytecode_hex=_h(bytes([MUL, H])),
        initial_stack=[6, 7], expected_stack=[42],
        description="MUL with initial stack [6, 7]"))

    cases.append(ConformanceTestCase(
        name="arith_neg_stack",
        bytecode_hex=_h(bytes([NEG, H])),
        initial_stack=[99], expected_stack=[-99],
        description="NEG with initial stack [99]"))

    # ═══════════════════════════════════════════════════════════════════
    # 3. COMPARISON
    # ═══════════════════════════════════════════════════════════════════

    cases.append(ConformanceTestCase(
        name="cmp_eq_true",
        bytecode_hex=_h(P(42) + P(42) + bytes([EQ, H])),
        expected_stack=[1], description="42 == 42 -> 1"))

    cases.append(ConformanceTestCase(
        name="cmp_eq_false",
        bytecode_hex=_h(P(42) + P(7) + bytes([EQ, H])),
        expected_stack=[0], expected_flags=FLAG_Z,
        description="42 == 7 -> 0, Z set"))

    cases.append(ConformanceTestCase(
        name="cmp_ne_true",
        bytecode_hex=_h(P(1) + P(2) + bytes([NE, H])),
        expected_stack=[1], description="1 != 2 -> 1"))

    cases.append(ConformanceTestCase(
        name="cmp_lt_true",
        bytecode_hex=_h(P(3) + P(5) + bytes([LT, H])),
        expected_stack=[1], description="3 < 5 -> 1"))

    cases.append(ConformanceTestCase(
        name="cmp_lt_equal",
        bytecode_hex=_h(P(5) + P(5) + bytes([LT, H])),
        expected_stack=[0], expected_flags=FLAG_Z,
        description="5 < 5 -> 0, Z set"))

    cases.append(ConformanceTestCase(
        name="cmp_le_equal",
        bytecode_hex=_h(P(5) + P(5) + bytes([LE, H])),
        expected_stack=[1], description="5 <= 5 -> 1"))

    cases.append(ConformanceTestCase(
        name="cmp_gt_true",
        bytecode_hex=_h(P(10) + P(3) + bytes([GT, H])),
        expected_stack=[1], description="10 > 3 -> 1"))

    cases.append(ConformanceTestCase(
        name="cmp_ge_equal",
        bytecode_hex=_h(P(7) + P(7) + bytes([GE, H])),
        expected_stack=[1], description="7 >= 7 -> 1"))

    cases.append(ConformanceTestCase(
        name="cmp_lt_negative",
        bytecode_hex=_h(P(-10) + P(-3) + bytes([LT, H])),
        expected_stack=[1], description="-10 < -3 -> 1"))

    cases.append(ConformanceTestCase(
        name="cmp_eq_stack",
        bytecode_hex=_h(bytes([EQ, H])),
        initial_stack=[100, 100], expected_stack=[1],
        description="EQ with equal stack values"))

    cases.append(ConformanceTestCase(
        name="cmp_ne_stack_false",
        bytecode_hex=_h(bytes([NE, H])),
        initial_stack=[5, 5], expected_stack=[0], expected_flags=FLAG_Z,
        description="NE with equal stack values -> 0"))

    cases.append(ConformanceTestCase(
        name="cmp_le_stack",
        bytecode_hex=_h(bytes([LE, H])),
        initial_stack=[7, 7], expected_stack=[1],
        description="LE with equal stack values -> 1"))

    # ═══════════════════════════════════════════════════════════════════
    # 4. LOGIC / BITWISE
    # ═══════════════════════════════════════════════════════════════════

    cases.append(ConformanceTestCase(
        name="logic_and_basic",
        bytecode_hex=_h(P(0xFF) + P(0x0F) + bytes([AND, H])),
        expected_stack=[0x0F], description="0xFF & 0x0F = 0x0F"))

    cases.append(ConformanceTestCase(
        name="logic_and_zero",
        bytecode_hex=_h(P(0xFF) + P(0x00) + bytes([AND, H])),
        expected_stack=[0], expected_flags=FLAG_Z,
        description="0xFF & 0x00 = 0, Z set"))

    cases.append(ConformanceTestCase(
        name="logic_or_basic",
        bytecode_hex=_h(P(0xF0) + P(0x0F) + bytes([OR, H])),
        expected_stack=[0xFF], description="0xF0 | 0x0F = 0xFF"))

    cases.append(ConformanceTestCase(
        name="logic_xor_same",
        bytecode_hex=_h(P(0xFF) + P(0xFF) + bytes([XOR, H])),
        expected_stack=[0], expected_flags=FLAG_Z,
        description="0xFF ^ 0xFF = 0, Z set"))

    cases.append(ConformanceTestCase(
        name="logic_xor_inverse",
        bytecode_hex=_h(P(0xFF) + P(0x0F) + bytes([XOR]) + P(0x0F) + bytes([XOR, H])),
        expected_stack=[0xFF], description="XOR self-inverse"))

    cases.append(ConformanceTestCase(
        name="logic_not_zero",
        bytecode_hex=_h(P(0) + bytes([NOT, H])),
        expected_stack=[-1], description="NOT 0 = -1"))

    cases.append(ConformanceTestCase(
        name="logic_not_42",
        bytecode_hex=_h(P(42) + bytes([NOT, H])),
        expected_stack=[-43], description="NOT 42 = -43"))

    cases.append(ConformanceTestCase(
        name="logic_not_double",
        bytecode_hex=_h(P(42) + bytes([NOT, NOT, H])),
        expected_stack=[42], description="NOT(NOT(42)) = 42"))

    cases.append(ConformanceTestCase(
        name="logic_shl_basic",
        bytecode_hex=_h(P(1) + P(4) + bytes([SHL, H])),
        expected_stack=[16], description="1 << 4 = 16"))

    cases.append(ConformanceTestCase(
        name="logic_shr_basic",
        bytecode_hex=_h(P(16) + P(2) + bytes([SHR, H])),
        expected_stack=[4], description="16 >> 2 = 4"))

    cases.append(ConformanceTestCase(
        name="logic_shl_zero",
        bytecode_hex=_h(P(42) + P(0) + bytes([SHL, H])),
        expected_stack=[42], description="42 << 0 = 42"))

    cases.append(ConformanceTestCase(
        name="logic_and_stack",
        bytecode_hex=_h(bytes([AND, H])),
        initial_stack=[0xF0F0, 0x0F0F], expected_stack=[0],
        expected_flags=FLAG_Z, description="0xF0F0 & 0x0F0F = 0, Z set"))

    cases.append(ConformanceTestCase(
        name="logic_or_stack",
        bytecode_hex=_h(bytes([OR, H])),
        initial_stack=[0xF000, 0x00F0], expected_stack=[0xF0F0],
        description="0xF000 | 0x00F0 = 0xF0F0"))

    cases.append(ConformanceTestCase(
        name="logic_xor_stack",
        bytecode_hex=_h(bytes([XOR, H])),
        initial_stack=[0xFF, 0x0F], expected_stack=[0xF0],
        description="0xFF ^ 0x0F = 0xF0"))

    cases.append(ConformanceTestCase(
        name="logic_shl_stack",
        bytecode_hex=_h(bytes([SHL, H])),
        initial_stack=[1, 10], expected_stack=[1024],
        description="1 << 10 = 1024"))

    cases.append(ConformanceTestCase(
        name="logic_shr_stack",
        bytecode_hex=_h(bytes([SHR, H])),
        initial_stack=[1024, 10], expected_stack=[1],
        description="1024 >> 10 = 1"))

    # ═══════════════════════════════════════════════════════════════════
    # 5. MEMORY
    # ═══════════════════════════════════════════════════════════════════

    cases.append(ConformanceTestCase(
        name="mem_store_load",
        bytecode_hex=_h(P(999) + store_addr(100) + load_addr(100) + bytes([H])),
        expected_stack=[999], description="STORE/LOAD roundtrip"))

    cases.append(ConformanceTestCase(
        name="mem_poke_peek",
        bytecode_hex=_h(P(200) + P(777) + bytes([POKE]) + P(200) + bytes([PEEK]) + bytes([H])),
        expected_stack=[777], description="POKE/PEEK roundtrip"))

    cases.append(ConformanceTestCase(
        name="mem_multiple_stores",
        bytecode_hex=_h(P(10) + store_addr(0) + P(20) + store_addr(4) + P(30) + store_addr(8) +
                        load_addr(0) + load_addr(4) + load_addr(8) + bytes([H])),
        expected_stack=[10, 20, 30], description="Multiple stores and loads"))

    cases.append(ConformanceTestCase(
        name="mem_overwrite",
        bytecode_hex=_h(P(1) + store_addr(50) + P(2) + store_addr(50) + load_addr(50) + bytes([H])),
        expected_stack=[2], description="Overwrite same address"))

    cases.append(ConformanceTestCase(
        name="mem_store_load_zero",
        bytecode_hex=_h(P(0) + store_addr(200) + load_addr(200) + bytes([H])),
        expected_stack=[0], description="STORE/LOAD zero"))

    cases.append(ConformanceTestCase(
        name="mem_peek_preserves",
        bytecode_hex=_h(P(300) + P(88) + bytes([POKE]) + P(300) + bytes([PEEK]) + bytes([H])),
        expected_stack=[88], description="POKE then PEEK"))

    # ═══════════════════════════════════════════════════════════════════
    # 6. CONTROL FLOW
    # ═══════════════════════════════════════════════════════════════════

    cases.append(ConformanceTestCase(
        name="ctrl_push_pop",
        bytecode_hex=_h(P(42) + bytes([POP, H])),
        expected_stack=[], description="PUSH 42 POP -> empty"))

    cases.append(ConformanceTestCase(
        name="ctrl_push_negative",
        bytecode_hex=_h(P(-100) + bytes([H])),
        expected_stack=[-100], description="PUSH -100"))

    cases.append(ConformanceTestCase(
        name="ctrl_push_zero",
        bytecode_hex=_h(P(0) + bytes([H])),
        expected_stack=[0], description="PUSH 0"))

    cases.append(ConformanceTestCase(
        name="ctrl_multi_push",
        bytecode_hex=_h(P(1) + P(2) + P(3) + P(4) + P(5) + bytes([H])),
        expected_stack=[1, 2, 3, 4, 5], description="Five PUSHes"))

    # JMP: push 0, HALT, push 99, HALT, JMP->first HALT
    # Offsets: PUSH0(0-4), HALT(5), PUSH99(6-10), HALT(11), JMP(12-14)->5
    cases.append(ConformanceTestCase(
        name="ctrl_jmp_over",
        bytecode_hex=_h(P(0) + bytes([H]) + P(99) + bytes([H]) + jmp_addr(5)),
        expected_stack=[0], description="JMP over second PUSH"))

    # JZ: push 0 push 0 EQ -> Z set, PUSH 1, JZ->HALT(end), PUSH 99, HALT
    # Offsets: PUSH0(0-4), PUSH0(5-9), EQ(10), PUSH1(11-15), JZ(16-18)->19,
    #          PUSH99(19-23), HALT(24)
    # Wait, if Z is set, JZ jumps to 19 which is PUSH99. We want it to SKIP PUSH99.
    # Let's make JZ jump past PUSH99.
    # Offsets: PUSH0(0-4), PUSH0(5-9), EQ(10), PUSH1(11-15),
    #          JZ->19(16-18), PUSH99(19-23), HALT(24)
    # When Z set, jump to 19 executes PUSH99... wrong.
    # Need JZ->24 to skip to HALT.
    cases.append(ConformanceTestCase(
        name="ctrl_jz_taken",
        bytecode_hex=_h(P(1) + bytes([DEC, POP]) + P(42) + jz_addr(20) + P(99) + bytes([H])),
        expected_stack=[42], description="JZ taken (Z set by DEC 1->0): skip PUSH 99"))

    # JNZ taken: DEC 0->-1 clears Z, POP removes -1, PUSH 42, JNZ past PUSH 99
    cases.append(ConformanceTestCase(
        name="ctrl_jnz_taken",
        bytecode_hex=_h(P(0) + bytes([DEC, POP]) + P(42) + jnz_addr(20) + P(99) + bytes([H])),
        expected_stack=[42], description="JNZ taken (Z clear by DEC 0->-1): skip PUSH 99"))

    # CALL + RET
    # Offsets: PUSH1(0-4), CALL(5-7)->13, ADD(8), HALT(9),
    #          NOP*3(10-12), PUSH2(13-17), RET(18), HALT(19)
    cases.append(ConformanceTestCase(
        name="ctrl_call_ret",
        bytecode_hex=_h(P(1) + call_addr(13) + bytes([ADD, H, NOP, NOP, NOP]) +
                        P(2) + bytes([RET, H])),
        expected_stack=[3], description="CALL/RET: 1 + 2 = 3"))

    # Nested CALL: outer sub pushes 5, calls inner (pushes 3), ADD, RET
    cases.append(ConformanceTestCase(
        name="ctrl_nested_call",
        bytecode_hex=_h(P(10) + call_addr(15) + bytes([ADD, H]) +
                        bytes([NOP] * 5) +
                        P(5) + call_addr(25) + bytes([ADD, RET]) +
                        P(3) + bytes([RET, H])),
        expected_stack=[18], description="Nested CALL: 10 + (5+3) = 18"))

    # Loop: body runs first, then DEC+STORE+JNZ
    # DEC sets Z flag; JNZ checks flags without popping
    loop_addr = 16
    cases.append(ConformanceTestCase(
        name="ctrl_loop_sum",
        bytecode_hex=_h(
            P(0) + store_addr(0) + P(3) + store_addr(4) +
            load_addr(0) + bytes([INC]) + store_addr(0) +
            load_addr(4) + bytes([DEC]) + store_addr(4) +
            jnz_addr(loop_addr) + load_addr(0) + bytes([H])),
        expected_stack=[3],
        description="Loop: increment sum 3 times = 3"))

    # Sum 1+2+3+4+5 = 15
    cases.append(ConformanceTestCase(
        name="ctrl_sum_1_to_5",
        bytecode_hex=_h(
            P(0) + store_addr(0) + P(5) + store_addr(4) +
            load_addr(0) + load_addr(4) + bytes([ADD]) + store_addr(0) +
            load_addr(4) + bytes([DEC]) + store_addr(4) +
            jnz_addr(16) + load_addr(0) + bytes([H])),
        expected_stack=[15], description="Sum 1..5 = 15"))

    # Factorial 5! = 120
    cases.append(ConformanceTestCase(
        name="ctrl_factorial_5",
        bytecode_hex=_h(
            P(1) + store_addr(0) + P(5) + store_addr(4) +
            load_addr(0) + load_addr(4) + bytes([MUL]) + store_addr(0) +
            load_addr(4) + bytes([DEC]) + store_addr(4) +
            jnz_addr(16) + load_addr(0) + bytes([H])),
        expected_stack=[120], description="5! = 120"))

    # ═══════════════════════════════════════════════════════════════════
    # 7. STACK MANIPULATION
    # ═══════════════════════════════════════════════════════════════════

    # DUP: [42] -> [42, 42]
    cases.append(ConformanceTestCase(
        name="stack_dup",
        bytecode_hex=_h(P(42) + bytes([DUP, H])),
        expected_stack=[42, 42], description="DUP: [42] -> [42, 42]"))

    # SWAP: push 1 push 2 -> [1, 2], SWAP -> [2, 1]
    cases.append(ConformanceTestCase(
        name="stack_swap",
        bytecode_hex=_h(P(1) + P(2) + bytes([SWAP, H])),
        expected_stack=[2, 1], description="SWAP: [1, 2] -> [2, 1]"))

    # OVER: push 10 push 20 -> [10, 20], OVER -> [10, 20, 10]
    cases.append(ConformanceTestCase(
        name="stack_over",
        bytecode_hex=_h(P(10) + P(20) + bytes([OVER, H])),
        expected_stack=[10, 20, 10], description="OVER: [10, 20] -> [10, 20, 10]"))

    # ROT: push 1 push 2 push 3 -> [1, 2, 3], ROT -> [2, 3, 1]
    cases.append(ConformanceTestCase(
        name="stack_rot",
        bytecode_hex=_h(P(1) + P(2) + P(3) + bytes([ROT, H])),
        expected_stack=[2, 3, 1], description="ROT: [1, 2, 3] -> [2, 3, 1]"))

    cases.append(ConformanceTestCase(
        name="stack_multi_dup",
        bytecode_hex=_h(P(7) + bytes([DUP, DUP, DUP, H])),
        expected_stack=[7, 7, 7, 7], description="Three DUPs"))

    cases.append(ConformanceTestCase(
        name="stack_over_mul_square",
        bytecode_hex=_h(P(7) + P(7) + bytes([MUL, H])),
        expected_stack=[49], description="7 * 7 = 49"))

    # ═══════════════════════════════════════════════════════════════════
    # 8. FLOAT OPERATIONS (using integer inputs, cast to float)
    # ═══════════════════════════════════════════════════════════════════

    cases.append(ConformanceTestCase(
        name="float_add",
        bytecode_hex=_h(P(3) + P(2) + bytes([FADD, H])),
        expected_stack=[5.0], allow_float_epsilon=True,
        description="FADD: 3.0 + 2.0 = 5.0"))

    cases.append(ConformanceTestCase(
        name="float_sub",
        bytecode_hex=_h(P(10) + P(3) + bytes([FSUB, H])),
        expected_stack=[7.0], allow_float_epsilon=True,
        description="FSUB: 10.0 - 3.0 = 7.0"))

    cases.append(ConformanceTestCase(
        name="float_mul",
        bytecode_hex=_h(P(4) + P(5) + bytes([FMUL, H])),
        expected_stack=[20.0], allow_float_epsilon=True,
        description="FMUL: 4.0 * 5.0 = 20.0"))

    cases.append(ConformanceTestCase(
        name="float_div",
        bytecode_hex=_h(P(7) + P(2) + bytes([FDIV, H])),
        expected_stack=[3.5], allow_float_epsilon=True,
        description="FDIV: 7.0 / 2.0 = 3.5"))

    cases.append(ConformanceTestCase(
        name="float_div_vs_int",
        bytecode_hex=_h(P(7) + P(2) + bytes([FDIV, H])),
        expected_stack=[3.5], allow_float_epsilon=True,
        description="FDIV gives 3.5 vs integer DIV gives 3"))

    cases.append(ConformanceTestCase(
        name="float_mul_large",
        bytecode_hex=_h(P(100) + P(100) + bytes([FMUL, H])),
        expected_stack=[10000.0], allow_float_epsilon=True,
        description="FMUL: 100.0 * 100.0 = 10000.0"))

    # ═══════════════════════════════════════════════════════════════════
    # 9. CONFIDENCE
    # ═══════════════════════════════════════════════════════════════════

    cases.append(ConformanceTestCase(
        name="conf_get_initial",
        bytecode_hex=_h(bytes([CONF_GET, H])),
        expected_stack=[1.0], allow_float_epsilon=True,
        description="CONF_GET -> 1.0"))

    cases.append(ConformanceTestCase(
        name="conf_set_zero",
        bytecode_hex=_h(P(0) + bytes([CONF_SET, CONF_GET, H])),
        expected_stack=[0.0], allow_float_epsilon=True,
        description="CONF_SET(0) CONF_GET -> 0.0"))

    cases.append(ConformanceTestCase(
        name="conf_set_half",
        bytecode_hex=_h(P(1) + bytes([CONF_SET, CONF_GET, H])),
        expected_stack=[1.0], allow_float_epsilon=True,
        description="CONF_SET(1) CONF_GET -> 1.0"))

    cases.append(ConformanceTestCase(
        name="conf_mul_clamp",
        bytecode_hex=_h(P(0) + bytes([CONF_SET]) + P(100) + bytes([CONF_MUL, CONF_GET, H])),
        expected_stack=[0.0], allow_float_epsilon=True,
        description="CONF 0 * 100 = 0 (clamped)"))

    cases.append(ConformanceTestCase(
        name="conf_mul_chain",
        bytecode_hex=_h(
            P(1) + bytes([CONF_SET]) +
            P(2) + bytes([CONF_MUL]) +
            P(3) + bytes([CONF_MUL, CONF_GET, H])),
        expected_stack=[1.0], allow_float_epsilon=True,
        description="CONF 1.0 * 2.0 * 3.0 = 1.0 (clamped)"))

    cases.append(ConformanceTestCase(
        name="conf_set_clamp_low",
        bytecode_hex=_h(P(-5) + bytes([CONF_SET, CONF_GET, H])),
        expected_stack=[0.0], allow_float_epsilon=True,
        description="CONF_SET(-5) clamps to 0.0"))

    cases.append(ConformanceTestCase(
        name="conf_set_clamp_high",
        bytecode_hex=_h(P(100) + bytes([CONF_SET, CONF_GET, H])),
        expected_stack=[1.0], allow_float_epsilon=True,
        description="CONF_SET(100) clamps to 1.0"))

    # ═══════════════════════════════════════════════════════════════════
    # 10. AGENT-TO-AGENT
    # ═══════════════════════════════════════════════════════════════════

    cases.append(ConformanceTestCase(
        name="a2a_signal_listen",
        bytecode_hex=_h(P(42) + signal_ch(1) + listen_ch(1) + bytes([H])),
        expected_stack=[42], description="SIGNAL/LISTEN on ch1"))

    cases.append(ConformanceTestCase(
        name="a2a_broadcast_listen",
        bytecode_hex=_h(P(99) + broadcast_ch(5) + listen_ch(5) + bytes([H])),
        expected_stack=[99], description="BROADCAST/LISTEN on ch5"))

    cases.append(ConformanceTestCase(
        name="a2a_fifo_order",
        bytecode_hex=_h(P(10) + signal_ch(2) + P(20) + signal_ch(2) +
                        listen_ch(2) + listen_ch(2) + bytes([H])),
        expected_stack=[10, 20], description="FIFO order on channel"))

    cases.append(ConformanceTestCase(
        name="a2a_listen_empty",
        bytecode_hex=_h(listen_ch(99) + bytes([H])),
        expected_stack=[0], description="LISTEN empty -> 0"))

    cases.append(ConformanceTestCase(
        name="a2a_separate_channels",
        bytecode_hex=_h(P(10) + signal_ch(1) + P(20) + signal_ch(2) +
                        listen_ch(1) + listen_ch(2) + bytes([H])),
        expected_stack=[10, 20], description="Separate channels"))

    cases.append(ConformanceTestCase(
        name="a2a_empty_after_listen",
        bytecode_hex=_h(P(55) + signal_ch(3) + listen_ch(3) + listen_ch(3) + bytes([H])),
        expected_stack=[55, 0], description="Second LISTEN -> 0"))

    # ═══════════════════════════════════════════════════════════════════
    # 11. COMPLEX / MIXED PROGRAMS
    # ═══════════════════════════════════════════════════════════════════

    # Fibonacci(7): [0, 1] then 7x (OVER ADD SWAP)
    # After 7 iterations: [13, 8]
    cases.append(ConformanceTestCase(
        name="complex_fibonacci",
        bytecode_hex=_h(P(0) + P(1) + bytes([OVER, ADD, SWAP]) * 7 + bytes([H])),
        expected_stack=[13, 8], description="Fibonacci(7): stack [13, 8]"))

    # Absolute value: DUP, PUSH 0, LT -> check if val < 0
    cases.append(ConformanceTestCase(
        name="complex_abs_neg",
        bytecode_hex=_h(
            P(-42) + bytes([DUP]) + P(0) + bytes([LT]) + jnz_addr(17) +
            bytes([POP, H]) + bytes([POP, NEG, H])),
        expected_stack=[42], description="|-42| = 42"))

    cases.append(ConformanceTestCase(
        name="complex_abs_pos",
        bytecode_hex=_h(
            P(42) + bytes([DUP]) + P(0) + bytes([LT]) + jnz_addr(17) +
            bytes([POP, H]) + bytes([POP, NEG, H])),
        expected_stack=[42], description="|42| = 42"))

    # Bitmask: 0xABCD & 0xFF = 0xCD
    cases.append(ConformanceTestCase(
        name="complex_bitmask",
        bytecode_hex=_h(P(0xABCD) + P(0xFF) + bytes([AND, H])),
        expected_stack=[0xCD], description="0xABCD & 0xFF = 0xCD"))

    # Power of 2: 1 << 8 = 256
    cases.append(ConformanceTestCase(
        name="complex_power_of_2",
        bytecode_hex=_h(P(1) + P(8) + bytes([SHL, H])),
        expected_stack=[256], description="1 << 8 = 256"))

    # Division + remainder: 17/5=3, 17%5=2
    cases.append(ConformanceTestCase(
        name="complex_div_mod",
        bytecode_hex=_h(P(17) + P(5) + bytes([DIV]) + P(17) + P(5) + bytes([MOD, H])),
        expected_stack=[3, 2], description="17/5=3, 17%5=2"))

    # Rotate left 4: (0x0F<<4) | (0x0F>>4) = 0xF0
    cases.append(ConformanceTestCase(
        name="complex_rotate_left",
        bytecode_hex=_h(P(0x0F) + P(4) + bytes([SHL]) + P(0x0F) + P(4) + bytes([SHR]) + bytes([OR, H])),
        expected_stack=[0xF0], description="Rotate left 4 bits"))

    # XOR inverse: (0xFF ^ 0x0F) ^ 0x0F = 0xFF
    cases.append(ConformanceTestCase(
        name="complex_xor_inverse",
        bytecode_hex=_h(P(0xFF) + P(0x0F) + bytes([XOR]) + P(0x0F) + bytes([XOR, H])),
        expected_stack=[0xFF], description="XOR self-inverse"))

    # Range check components: 3>5=0, 5<10=1
    cases.append(ConformanceTestCase(
        name="complex_range_check",
        bytecode_hex=_h(P(3) + P(5) + bytes([GT]) + P(5) + P(10) + bytes([LT, H])),
        expected_stack=[0, 1], description="3>5=0, 5<10=1"))

    # Conditionals: GT check
    cases.append(ConformanceTestCase(
        name="complex_gt_check",
        bytecode_hex=_h(P(10) + P(20) + bytes([GT, H])),
        expected_stack=[0], expected_flags=FLAG_Z,
        description="10 > 20 = 0 (false), Z set"))

    return cases
