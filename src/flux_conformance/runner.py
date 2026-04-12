"""FLUX Conformance Test Runner -- MiniVM bytecode interpreter and test execution engine.

Provides a lightweight FLUX ISA v2 bytecode interpreter (MiniVM), test vector
definitions, programmatic vector generation, conformance execution, and reporting.
"""

from __future__ import annotations

import math
import random
import struct
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

NUM_REGISTERS = 16
MEMORY_SIZE = 256
STACK_DEPTH = 64
MAX_INSTRUCTIONS = 100_000
MASK32 = 0xFFFFFFFF
SIGN_BIT = 0x80000000

# Opcode name lookup (partial -- extended to full ISA in OPCODE_NAMES)
_OPCODE_NAMES: dict[int, str] = {
    # System / Format A
    0x00: "HALT", 0x01: "NOP", 0x02: "RET", 0x03: "IRET", 0x04: "BRK",
    # Register / Format B
    0x08: "INC", 0x09: "DEC", 0x0A: "NOT", 0x0B: "NEG",
    0x0C: "PUSH", 0x0D: "POP", 0x0E: "CONF_LD", 0x0F: "CONF_ST",
    # System ext / Format C
    0x10: "SYS", 0x11: "TRAP", 0x12: "DBG", 0x13: "CLF", 0x14: "SEMA",
    0x15: "YIELD", 0x16: "CACHE", 0x17: "STRIPCF",
    # Immediate / Format D
    0x18: "MOVI", 0x19: "ADDI", 0x1A: "SUBI", 0x1B: "ANDI",
    0x1C: "ORI", 0x1D: "XORI", 0x1E: "SHLI", 0x1F: "SHRI",
    # Arithmetic / Format E
    0x20: "ADD", 0x21: "SUB", 0x22: "MUL", 0x23: "DIV", 0x24: "MOD",
    0x25: "AND", 0x26: "OR", 0x27: "XOR", 0x28: "SHL", 0x29: "SHR",
    0x2A: "MIN", 0x2B: "MAX",
    0x2C: "CMP_EQ", 0x2D: "CMP_LT", 0x2E: "CMP_GT", 0x2F: "CMP_NE",
    # Float / memory / control / Format E
    0x30: "FADD", 0x31: "FSUB", 0x32: "FMUL", 0x33: "FDIV",
    0x34: "FMIN", 0x35: "FMAX", 0x36: "FTOI", 0x37: "ITOF",
    0x38: "LOAD", 0x39: "STORE", 0x3A: "MOV", 0x3B: "SWP",
    0x3C: "JZ", 0x3D: "JNZ", 0x3E: "JLT", 0x3F: "JGT",
    # Format F
    0x40: "MOVI16", 0x41: "ADDI16", 0x42: "SUBI16",
    0x43: "JMP", 0x44: "JAL", 0x45: "CALL", 0x46: "LOOP", 0x47: "SELECT",
    # Format G
    0x48: "LOADOFF", 0x49: "STOREOFF", 0x4A: "LOADI", 0x4B: "STOREI",
    0x4C: "ENTER", 0x4D: "LEAVE", 0x4E: "COPY", 0x4F: "FILL",
    # A2A / Format E
    0x50: "TELL", 0x51: "ASK", 0x52: "DELEG", 0x53: "BCAST",
    0x54: "ACCEPT", 0x55: "DECLINE", 0x56: "REPORT", 0x57: "MERGE",
    0x58: "FORK", 0x59: "JOIN", 0x5A: "SIGNAL", 0x5B: "AWAIT",
    0x5C: "TRUST", 0x5D: "DISCOV", 0x5E: "STATUS", 0x5F: "HEARTBT",
    # Confidence 0x60-0x6F
    0x60: "C_ADD", 0x61: "C_SUB", 0x62: "C_MUL", 0x63: "C_DIV",
    0x64: "C_AVG", 0x65: "C_WAVG", 0x66: "C_MAX", 0x67: "C_MIN",
    0x68: "C_MEDIAN", 0x69: "C_STDEV", 0x6A: "C_RANK",
    0x6B: "C_VOTE", 0x6C: "C_CONSENSUS", 0x6D: "C_WEIGHT",
    0x6E: "C_QUORUM", 0x6F: "C_SLATE",
    # Concurrency 0x70-0x7F
    0x70: "SPAWN", 0x71: "KILL", 0x72: "JOIN_T", 0x73: "MUTEX",
    0x74: "RWLOCK", 0x75: "BARRIER", 0x76: "CHAN", 0x77: "SELECT_T",
    0x78: "POLL", 0x79: "EPOLL", 0x7A: "TIMER", 0x7B: "ALARM",
    0x7C: "SIGNAL_S", 0x7D: "MASK", 0x7E: "SIGRET", 0x7F: "RCALL",
    # I/O 0x80-0x8F
    0x80: "IN", 0x81: "OUT", 0x82: "INB", 0x83: "OUTB",
    0x84: "MAP_IO", 0x85: "UNMAP_IO", 0x86: "DMA", 0x87: "IRQ",
    0x88: "ACK_IRQ", 0x89: "MASK_IRQ", 0x8A: "MMIO_R", 0x8B: "MMIO_W",
    0x8C: "PAGE_IN", 0x8D: "PAGE_OUT", 0x8E: "TLB", 0x8F: "FLUSH",
    # Extended math 0x90-0x9F
    0x90: "ABS", 0x91: "SIGN", 0x92: "SQRT", 0x93: "POW", 0x94: "LOG2",
    0x95: "CLZ", 0x96: "CTZ", 0x97: "POPCNT", 0x98: "CRC32", 0x99: "SHA256",
    0x9A: "RND", 0x9B: "SEED", 0x9C: "FMOD", 0x9D: "FSQRT",
    0x9E: "FSIN", 0x9F: "FCOS",
    # Collection / Crypto 0xA0-0xAF
    0xA0: "LEN", 0xA1: "CAP", 0xA2: "APPEND", 0xA3: "REMOVE",
    0xA4: "INDEX", 0xA5: "SLICE", 0xA6: "MAP", 0xA7: "FILTER",
    0xA8: "REDUCE", 0xA9: "SORT",
    0xAA: "KEYGEN", 0xAB: "SIGN_D", 0xAC: "VERIFY",
    0xAD: "ENCRYPT", 0xAE: "DECRYPT", 0xAF: "HASH",
    # String 0xB0-0xBF
    0xB0: "STRLEN", 0xB1: "STRCAT", 0xB2: "STRCMP", 0xB3: "STRCPY",
    0xB4: "SUBSTR", 0xB5: "STRFIND", 0xB6: "SPLIT", 0xB7: "JOIN_S",
    0xB8: "TRIM", 0xB9: "UPPER", 0xBA: "LOWER", 0xBB: "REPLACE",
    0xBC: "REPEAT", 0xBD: "PAD", 0xBE: "FORMAT", 0xBF: "PARSE",
    # Diagnostics / Format A
    0xF0: "HALT_ERR", 0xF1: "REBOOT", 0xF2: "DUMP", 0xF3: "ASSERT",
    0xF4: "ID", 0xF5: "VER", 0xF6: "CLK", 0xF7: "PCLK",
    0xF8: "WDOG", 0xF9: "SLEEP", 0xFA: "PANIC", 0xFF: "ILLEGAL",
}

# Format lookup table
_OPCODE_FORMATS: dict[int, str] = {}

# Format A: system / diagnostics
for _code in [
    0x00, 0x01, 0x02, 0x03, 0x04,
    0xF0, 0xF1, 0xF2, 0xF3, 0xF4, 0xF5, 0xF6, 0xF7,
    0xF8, 0xF9, 0xFA, 0xFB, 0xFC, 0xFD, 0xFE, 0xFF,
]:
    _OPCODE_FORMATS[_code] = "A"

# Format B: register ops
for _code in [0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F]:
    _OPCODE_FORMATS[_code] = "B"

# Format C: system extensions
for _code in [0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17]:
    _OPCODE_FORMATS[_code] = "C"

# Format D: immediate ops
for _code in [0x18, 0x19, 0x1A, 0x1B, 0x1C, 0x1D, 0x1E, 0x1F,
              0xA0, 0xA1, 0xB0]:
    _OPCODE_FORMATS[_code] = "D"

# Format E: register triples / memory / control / A2A / extended
for _code in [
    0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28, 0x29,
    0x2A, 0x2B, 0x2C, 0x2D, 0x2E, 0x2F,
    0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37, 0x38, 0x39,
    0x3A, 0x3B, 0x3C, 0x3D, 0x3E, 0x3F,
    0x50, 0x51, 0x52, 0x53, 0x54, 0x55, 0x56, 0x57, 0x58, 0x59,
    0x5A, 0x5B, 0x5C, 0x5D, 0x5E, 0x5F,
    *range(0x60, 0x70), *range(0x70, 0x80), *range(0x80, 0x90),
    *range(0x90, 0xA0),
    0xA2, 0xA3, 0xA4, 0xA5, 0xA6, 0xA7, 0xA8, 0xA9,
    0xAB, 0xAC, 0xAD, 0xAE, 0xAF,
    *range(0xB1, 0xC0),
]:
    _OPCODE_FORMATS[_code] = "E"

# Format F: 16-bit immediate / control flow
for _code in [0x40, 0x41, 0x42, 0x43, 0x44, 0x45, 0x46, 0x47]:
    _OPCODE_FORMATS[_code] = "F"

# Format G: memory extensions
for _code in [0x48, 0x49, 0x4A, 0x4B, 0x4C, 0x4D, 0x4E, 0x4F, 0xAA]:
    _OPCODE_FORMATS[_code] = "G"

FORMAT_SIZES = {"A": 1, "B": 2, "C": 2, "D": 3, "E": 4, "F": 4, "G": 5}


# ---------------------------------------------------------------------------
# Encoding helpers
# ---------------------------------------------------------------------------

def encode_a(opcode: int) -> bytes:
    """Encode a Format A instruction (opcode only, 1 byte)."""
    return bytes([opcode])


def encode_b(opcode: int, rd: int) -> bytes:
    """Encode a Format B instruction (opcode + register, 2 bytes)."""
    return bytes([opcode, rd & 0xF])


def encode_c(opcode: int, imm8: int) -> bytes:
    """Encode a Format C instruction (opcode + 8-bit immediate, 2 bytes)."""
    return bytes([opcode, imm8 & 0xFF])


def encode_d(opcode: int, rd: int, imm8: int) -> bytes:
    """Encode a Format D instruction (opcode + register + 8-bit immediate, 3 bytes)."""
    return bytes([opcode, rd & 0xF, imm8 & 0xFF])


def encode_e(opcode: int, rd: int, rs1: int, rs2: int) -> bytes:
    """Encode a Format E instruction (opcode + 3 registers, 4 bytes)."""
    return bytes([opcode, rd & 0xF, rs1 & 0xF, rs2 & 0xF])


def encode_f(opcode: int, rd: int, imm16: int) -> bytes:
    """Encode a Format F instruction (opcode + register + 16-bit LE immediate, 4 bytes)."""
    return bytes([opcode, rd & 0xF, imm16 & 0xFF, (imm16 >> 8) & 0xFF])


def encode_g(opcode: int, rd: int, rs1: int, imm16: int) -> bytes:
    """Encode a Format G instruction (opcode + 2 registers + 16-bit LE immediate, 5 bytes)."""
    return bytes([opcode, rd & 0xF, rs1 & 0xF, imm16 & 0xFF, (imm16 >> 8) & 0xFF])


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _s32(val: int) -> int:
    """Clamp value to signed 32-bit range."""
    val = val & MASK32
    if val >= SIGN_BIT:
        val -= (MASK32 + 1)
    return val


def _u32(val: int) -> int:
    """Clamp value to unsigned 32-bit range."""
    return val & MASK32


def _reg_to_float(val: int) -> float:
    """Interpret a 32-bit register value as IEEE 754 single-precision float."""
    return struct.unpack("<f", struct.pack("<I", val & MASK32))[0]


def _float_to_reg(f: float) -> int:
    """Convert a Python float to its IEEE 754 single-precision bit pattern (as signed int)."""
    return _s32(struct.unpack("<I", struct.pack("<f", f))[0])


# ---------------------------------------------------------------------------
# Flags
# ---------------------------------------------------------------------------

@dataclass
class Flags:
    """FLUX VM flags register."""
    zero: bool = False
    negative: bool = False
    overflow: bool = False
    carry: bool = False
    error: bool = False

    def clear(self) -> None:
        self.zero = False
        self.negative = False
        self.overflow = False
        self.carry = False
        self.error = False

    def update_arithmetic(self, result: int, a: int, b: int, is_sub: bool = False) -> None:
        """Update flags after an arithmetic operation."""
        self.zero = (result == 0)
        self.negative = (result < 0)
        ua, ub = _u32(a), _u32(b)
        if is_sub:
            self.carry = ua < ub
            self.overflow = (a >= 0 and b < 0 and result < 0) or (a < 0 and b >= 0 and result >= 0)
        else:
            self.carry = (ua + ub) > MASK32
            self.overflow = (a >= 0 and b >= 0 and result < 0) or (a < 0 and b < 0 and result >= 0)


# ---------------------------------------------------------------------------
# MiniVM
# ---------------------------------------------------------------------------

class MiniVM:
    """Lightweight FLUX ISA v2 bytecode interpreter for conformance testing.

    Features:
      - 16 general-purpose 32-bit signed registers (R0-R15)
      - 256-byte addressable memory
      - 64-entry call stack
      - Flags: zero, negative, overflow, carry, error
      - Execution trace for A2A and debug opcodes
    """

    def __init__(self) -> None:
        self.registers: list[int] = [0] * NUM_REGISTERS
        self.memory: bytearray = bytearray(MEMORY_SIZE)
        self.pc: int = 0
        self.flags = Flags()
        self.stack: list[int] = []
        self.halted: bool = False
        self.halt_error: bool = False
        self.cycle_count: int = 0
        self.trace: list[str] = []
        self.a2a_log: list[dict[str, Any]] = []
        self.program: bytes = b""
        self._rng = random.Random(42)

    # -- public interface ----------------------------------------------------

    def reset(self) -> None:
        """Reset VM to initial state."""
        self.registers = [0] * NUM_REGISTERS
        self.memory = bytearray(MEMORY_SIZE)
        self.pc = 0
        self.flags.clear()
        self.stack.clear()
        self.halted = False
        self.halt_error = False
        self.cycle_count = 0
        self.trace.clear()
        self.a2a_log.clear()
        self._rng = random.Random(42)

    def load(self, program: bytes) -> None:
        """Load a bytecode program."""
        self.program = program
        self.reset()

    def run(self) -> None:
        """Execute until HALT or error."""
        while not self.halted and self.cycle_count < MAX_INSTRUCTIONS:
            self._step()

    def _step(self) -> None:
        """Execute one instruction."""
        if self.pc >= len(self.program):
            self.halted = True
            self.halt_error = True
            self.flags.error = True
            self.trace.append("ERROR: PC out of bounds")
            return

        opcode = self.program[self.pc]
        fmt = _OPCODE_FORMATS.get(opcode)
        if fmt is None:
            self.trace.append(f"UNKNOWN opcode 0x{opcode:02X} at PC={self.pc}")
            self.flags.error = True
            self.halted = True
            self.halt_error = True
            self.pc += 1
            return

        size = FORMAT_SIZES[fmt]
        name = _OPCODE_NAMES.get(opcode, f"OP_0x{opcode:02X}")

        # Decode operands
        if fmt == "A":
            self._exec_a(opcode, name)
        elif fmt == "B":
            rd = self.program[self.pc + 1] if self.pc + 1 < len(self.program) else 0
            self._exec_b(opcode, name, rd)
        elif fmt == "C":
            imm8 = self.program[self.pc + 1] if self.pc + 1 < len(self.program) else 0
            self._exec_c(opcode, name, imm8)
        elif fmt == "D":
            rd = self.program[self.pc + 1] if self.pc + 1 < len(self.program) else 0
            imm8 = self.program[self.pc + 2] if self.pc + 2 < len(self.program) else 0
            self._exec_d(opcode, name, rd, imm8)
        elif fmt == "E":
            rd  = self.program[self.pc + 1] if self.pc + 1 < len(self.program) else 0
            rs1 = self.program[self.pc + 2] if self.pc + 2 < len(self.program) else 0
            rs2 = self.program[self.pc + 3] if self.pc + 3 < len(self.program) else 0
            self._exec_e(opcode, name, rd, rs1, rs2)
        elif fmt == "F":
            rd = self.program[self.pc + 1] if self.pc + 1 < len(self.program) else 0
            lo = self.program[self.pc + 2] if self.pc + 2 < len(self.program) else 0
            hi = self.program[self.pc + 3] if self.pc + 3 < len(self.program) else 0
            imm16 = lo | (hi << 8)
            # Sign extend 16-bit
            if imm16 >= 0x8000:
                imm16 -= 0x10000
            self._exec_f(opcode, name, rd, imm16)
        elif fmt == "G":
            rd  = self.program[self.pc + 1] if self.pc + 1 < len(self.program) else 0
            rs1 = self.program[self.pc + 2] if self.pc + 2 < len(self.program) else 0
            lo = self.program[self.pc + 3] if self.pc + 3 < len(self.program) else 0
            hi = self.program[self.pc + 4] if self.pc + 4 < len(self.program) else 0
            imm16 = lo | (hi << 8)
            if imm16 >= 0x8000:
                imm16 -= 0x10000
            self._exec_g(opcode, name, rd, rs1, imm16)

        self.cycle_count += 1

    # -- Format A: system / diagnostic opcodes --------------------------------

    def _exec_a(self, opcode: int, name: str) -> None:
        self.pc += 1

        if opcode == 0x00:  # HALT
            self.halted = True
            self.trace.append("HALT")
        elif opcode == 0x01:  # NOP
            self.trace.append("NOP")
        elif opcode == 0x02:  # RET
            if self.stack:
                self.pc = self.stack.pop()
                self.trace.append(f"RET -> {self.pc}")
            else:
                self.flags.error = True
                self.halted = True
                self.halt_error = True
                self.trace.append("RET: stack underflow")
        elif opcode == 0x03:  # IRET
            if len(self.stack) >= 2:
                self.pc = self.stack.pop()
                self.flags = Flags()  # simplified: clear flags
                self.trace.append(f"IRET -> {self.pc}")
            else:
                self.flags.error = True
                self.halted = True
                self.halt_error = True
                self.trace.append("IRET: stack underflow")
        elif opcode == 0x04:  # BRK
            self.trace.append(f"BRK at PC={self.pc - 1}")
        elif opcode == 0xF0:  # HALT_ERR
            self.halted = True
            self.halt_error = True
            self.flags.error = True
            self.trace.append("HALT_ERR")
        elif opcode == 0xF1:  # REBOOT
            self.reset()
            self.trace.append("REBOOT")
        elif opcode == 0xF2:  # DUMP
            self.trace.append(
                f"DUMP pc={self.pc} regs={list(self.registers)} "
                f"mem[:8]={list(self.memory[:8])} stack_depth={len(self.stack)}"
            )
        elif opcode == 0xF3:  # ASSERT (checks R0 != 0)
            if self.registers[0] == 0:
                self.halted = True
                self.halt_error = True
                self.flags.error = True
                self.trace.append("ASSERT FAILED (R0==0)")
            else:
                self.trace.append("ASSERT OK")
        elif opcode == 0xF4:  # ID
            self.registers[0] = 1
            self.trace.append("ID -> R0=1")
        elif opcode == 0xF5:  # VER
            self.registers[0] = 2
            self.trace.append("VER -> R0=2")
        elif opcode == 0xF6:  # CLK
            self.registers[0] = _s32(self.cycle_count & MASK32)
            self.trace.append(f"CLK -> R0={self.registers[0]}")
        elif opcode == 0xF7:  # PCLK
            self.registers[0] = _s32(self.cycle_count & MASK32)
            self.trace.append(f"PCLK -> R0={self.registers[0]}")
        elif opcode == 0xF8:  # WDOG
            self.trace.append("WDOG")
        elif opcode == 0xF9:  # SLEEP
            self.trace.append("SLEEP")
        elif opcode == 0xFA:  # PANIC
            self.halted = True
            self.halt_error = True
            self.flags.error = True
            self.trace.append("PANIC")
        elif opcode == 0xFF:  # ILLEGAL
            self.flags.error = True
            self.halted = True
            self.halt_error = True
            self.trace.append("ILLEGAL")
        else:
            # Unhandled Format A
            self.trace.append(f"UNHANDLED_A 0x{opcode:02X}")

    # -- Format B: register manipulation --------------------------------------

    def _exec_b(self, opcode: int, name: str, rd: int) -> None:
        self.pc += 2
        val = self.registers[rd]

        if opcode == 0x08:  # INC
            result = _s32(val + 1)
            self.flags.update_arithmetic(result, val, 1)
            self.registers[rd] = result
        elif opcode == 0x09:  # DEC
            result = _s32(val - 1)
            self.flags.update_arithmetic(result, val, 1, is_sub=True)
            self.registers[rd] = result
        elif opcode == 0x0A:  # NOT
            result = _s32(~val)
            self.flags.update_arithmetic(result, 0, 0)
            self.registers[rd] = result
        elif opcode == 0x0B:  # NEG
            result = _s32(-val)
            self.flags.update_arithmetic(result, 0, -val, is_sub=True)
            self.registers[rd] = result
        elif opcode == 0x0C:  # PUSH
            if len(self.stack) >= STACK_DEPTH:
                self.flags.error = True
                self.halted = True
                self.halt_error = True
                self.trace.append("PUSH: stack overflow")
                return
            self.stack.append(val)
        elif opcode == 0x0D:  # POP
            if not self.stack:
                self.flags.error = True
                self.halted = True
                self.halt_error = True
                self.trace.append("POP: stack underflow")
                return
            self.registers[rd] = self.stack.pop()
        elif opcode == 0x0E:  # CONF_LD
            self.registers[rd] = 0  # no-op config
        elif opcode == 0x0F:  # CONF_ST
            pass  # no-op config
        else:
            self.trace.append(f"UNHANDLED_B 0x{opcode:02X}")

    # -- Format C: system extensions ------------------------------------------

    def _exec_c(self, opcode: int, name: str, imm8: int) -> None:
        self.pc += 2

        if opcode == 0x10:  # SYS
            self.trace.append(f"SYS call={imm8}")
        elif opcode == 0x11:  # TRAP
            self.trace.append(f"TRAP code={imm8}")
        elif opcode == 0x12:  # DBG
            self.trace.append(f"DBG PC={self.pc - 2}")
        elif opcode == 0x13:  # CLF
            self.flags.clear()
            self.trace.append("CLF")
        elif opcode == 0x14:  # SEMA
            self.trace.append(f"SEMA op={imm8}")
        elif opcode == 0x15:  # YIELD
            self.trace.append("YIELD")
        elif opcode == 0x16:  # CACHE
            self.trace.append(f"CACHE hint={imm8}")
        elif opcode == 0x17:  # STRIPCF
            self.flags.carry = False
            self.trace.append("STRIPCF")
        else:
            self.trace.append(f"UNHANDLED_C 0x{opcode:02X}")

    # -- Format D: immediate operations ---------------------------------------

    def _exec_d(self, opcode: int, name: str, rd: int, imm8: int) -> None:
        self.pc += 3
        # Sign-extend imm8 to signed
        if imm8 >= 0x80:
            simm = imm8 - 0x100
        else:
            simm = imm8

        val = self.registers[rd]

        if opcode == 0x18:  # MOVI
            self.registers[rd] = simm
            self.flags.zero = (simm == 0)
            self.flags.negative = (simm < 0)
        elif opcode == 0x19:  # ADDI
            result = _s32(val + simm)
            self.flags.update_arithmetic(result, val, simm)
            self.registers[rd] = result
        elif opcode == 0x1A:  # SUBI
            result = _s32(val - simm)
            self.flags.update_arithmetic(result, val, simm, is_sub=True)
            self.registers[rd] = result
        elif opcode == 0x1B:  # ANDI
            result = _s32(_u32(val) & _u32(simm))
            self.flags.zero = (result == 0)
            self.flags.negative = (result < 0)
            self.registers[rd] = result
        elif opcode == 0x1C:  # ORI
            result = _s32(_u32(val) | _u32(simm))
            self.flags.zero = (result == 0)
            self.flags.negative = (result < 0)
            self.registers[rd] = result
        elif opcode == 0x1D:  # XORI
            result = _s32(_u32(val) ^ _u32(simm))
            self.flags.zero = (result == 0)
            self.flags.negative = (result < 0)
            self.registers[rd] = result
        elif opcode == 0x1E:  # SHLI
            shift = simm & 0x1F
            result = _s32(_u32(val) << shift)
            self.flags.zero = (result == 0)
            self.flags.negative = (result < 0)
            self.registers[rd] = result
        elif opcode == 0x1F:  # SHRI
            shift = simm & 0x1F
            result = _s32(_u32(val) >> shift)
            self.flags.zero = (result == 0)
            self.flags.negative = (result < 0)
            self.registers[rd] = result
        elif opcode == 0xA0:  # LEN
            self.registers[rd] = 0  # no-op for mini VM
        elif opcode == 0xA1:  # CAP
            self.registers[rd] = 0
        elif opcode == 0xB0:  # STRLEN
            self.registers[rd] = 0
        else:
            self.trace.append(f"UNHANDLED_D 0x{opcode:02X}")

    # -- Format E: register-register-register ---------------------------------

    def _exec_e(self, opcode: int, name: str, rd: int, rs1: int, rs2: int) -> None:
        # Handle jumps specially -- don't auto-advance PC
        if opcode in (0x3C, 0x3D, 0x3E, 0x3F):
            self._exec_e_jump(opcode, name, rd, rs1, rs2)
            return

        self.pc += 4
        v1 = self.registers[rs1]
        v2 = self.registers[rs2]

        # -- Arithmetic --
        if opcode == 0x20:  # ADD
            result = _s32(v1 + v2)
            self.flags.update_arithmetic(result, v1, v2)
            self.registers[rd] = result
        elif opcode == 0x21:  # SUB
            result = _s32(v1 - v2)
            self.flags.update_arithmetic(result, v1, v2, is_sub=True)
            self.registers[rd] = result
        elif opcode == 0x22:  # MUL
            result = _s32(v1 * v2)
            self.flags.update_arithmetic(result, v1, v2)
            self.registers[rd] = result
        elif opcode == 0x23:  # DIV
            if v2 == 0:
                self.flags.error = True
                self.registers[rd] = 0
                self.trace.append("DIV by zero")
            else:
                result = _s32(int(v1 / v2))  # truncation towards zero
                self.flags.update_arithmetic(result, v1, v2, is_sub=True)
                self.registers[rd] = result
        elif opcode == 0x24:  # MOD
            if v2 == 0:
                self.flags.error = True
                self.registers[rd] = 0
                self.trace.append("MOD by zero")
            else:
                # Python's % matches sign of divisor; use C-style
                result = _s32(v1 - int(v1 / v2) * v2)
                self.flags.update_arithmetic(result, v1, v2, is_sub=True)
                self.registers[rd] = result

        # -- Bitwise --
        elif opcode == 0x25:  # AND
            result = _s32(_u32(v1) & _u32(v2))
            self.flags.zero = (result == 0)
            self.flags.negative = (result < 0)
            self.registers[rd] = result
        elif opcode == 0x26:  # OR
            result = _s32(_u32(v1) | _u32(v2))
            self.flags.zero = (result == 0)
            self.flags.negative = (result < 0)
            self.registers[rd] = result
        elif opcode == 0x27:  # XOR
            result = _s32(_u32(v1) ^ _u32(v2))
            self.flags.zero = (result == 0)
            self.flags.negative = (result < 0)
            self.registers[rd] = result
        elif opcode == 0x28:  # SHL
            result = _s32(_u32(v1) << (v2 & 0x1F))
            self.flags.zero = (result == 0)
            self.flags.negative = (result < 0)
            self.registers[rd] = result
        elif opcode == 0x29:  # SHR (logical)
            result = _s32(_u32(v1) >> (v2 & 0x1F))
            self.flags.zero = (result == 0)
            self.flags.negative = (result < 0)
            self.registers[rd] = result

        # -- MIN / MAX --
        elif opcode == 0x2A:  # MIN
            result = min(v1, v2)
            self.flags.zero = (result == 0)
            self.flags.negative = (result < 0)
            self.registers[rd] = result
        elif opcode == 0x2B:  # MAX
            result = max(v1, v2)
            self.flags.zero = (result == 0)
            self.flags.negative = (result < 0)
            self.registers[rd] = result

        # -- Compare --
        elif opcode == 0x2C:  # CMP_EQ
            eq = 1 if v1 == v2 else 0
            self.registers[rd] = eq
            self.flags.zero = (v1 == v2)
            self.flags.negative = False
        elif opcode == 0x2D:  # CMP_LT
            lt = 1 if v1 < v2 else 0
            self.registers[rd] = lt
            self.flags.zero = (v1 >= v2)
            self.flags.negative = (v1 < v2)
        elif opcode == 0x2E:  # CMP_GT
            gt = 1 if v1 > v2 else 0
            self.registers[rd] = gt
            self.flags.zero = (v1 <= v2)
            self.flags.negative = False
        elif opcode == 0x2F:  # CMP_NE
            ne = 1 if v1 != v2 else 0
            self.registers[rd] = ne
            self.flags.zero = (v1 == v2)
            self.flags.negative = False

        # -- Float --
        elif opcode == 0x30:  # FADD
            f1, f2 = _reg_to_float(v1), _reg_to_float(v2)
            self.registers[rd] = _float_to_reg(f1 + f2)
        elif opcode == 0x31:  # FSUB
            f1, f2 = _reg_to_float(v1), _reg_to_float(v2)
            self.registers[rd] = _float_to_reg(f1 - f2)
        elif opcode == 0x32:  # FMUL
            f1, f2 = _reg_to_float(v1), _reg_to_float(v2)
            self.registers[rd] = _float_to_reg(f1 * f2)
        elif opcode == 0x33:  # FDIV
            f1, f2 = _reg_to_float(v1), _reg_to_float(v2)
            if f2 == 0.0:
                self.flags.error = True
                self.registers[rd] = 0
                self.trace.append("FDIV by zero")
            else:
                self.registers[rd] = _float_to_reg(f1 / f2)
        elif opcode == 0x34:  # FMIN
            f1, f2 = _reg_to_float(v1), _reg_to_float(v2)
            self.registers[rd] = _float_to_reg(min(f1, f2))
        elif opcode == 0x35:  # FMAX
            f1, f2 = _reg_to_float(v1), _reg_to_float(v2)
            self.registers[rd] = _float_to_reg(max(f1, f2))
        elif opcode == 0x36:  # FTOI
            self.registers[rd] = _s32(int(_reg_to_float(v1)))
        elif opcode == 0x37:  # ITOF
            self.registers[rd] = _float_to_reg(float(v1))

        # -- Memory --
        elif opcode == 0x38:  # LOAD
            addr = v1 & 0xFF
            self.registers[rd] = self.memory[addr]
        elif opcode == 0x39:  # STORE
            addr = v1 & 0xFF
            self.memory[addr] = self.registers[rd] & 0xFF
        elif opcode == 0x3A:  # MOV
            self.registers[rd] = v1
        elif opcode == 0x3B:  # SWP
            self.registers[rd], self.registers[rs1] = self.registers[rs1], self.registers[rd]

        # -- A2A opcodes (no-op, record trace) --
        elif 0x50 <= opcode <= 0x5F:
            self._exec_a2a(opcode, name, rd, rs1, rs2)

        # -- Confidence opcodes 0x60-0x6F (no-op) --
        elif 0x60 <= opcode <= 0x6F:
            self.trace.append(f"{name} rd={rd} rs1={rs1} rs2={rs2}")

        # -- Concurrency 0x70-0x7F (no-op) --
        elif 0x70 <= opcode <= 0x7F:
            self.trace.append(f"{name} rd={rd} rs1={rs1} rs2={rs2}")

        # -- I/O 0x80-0x8F (no-op) --
        elif 0x80 <= opcode <= 0x8F:
            self.trace.append(f"{name} rd={rd} rs1={rs1} rs2={rs2}")

        # -- Extended math 0x90-0x9F --
        elif opcode == 0x90:  # ABS
            self.registers[rd] = abs(v1)
            self.flags.zero = (self.registers[rd] == 0)
            self.flags.negative = False
        elif opcode == 0x91:  # SIGN
            if v1 < 0:
                self.registers[rd] = -1
            elif v1 > 0:
                self.registers[rd] = 1
            else:
                self.registers[rd] = 0
        elif opcode == 0x92:  # SQRT (integer)
            self.registers[rd] = _s32(int(math.isqrt(abs(v1))))
        elif opcode == 0x93:  # POW
            try:
                result = _s32(int(v1 ** v2))
            except (OverflowError, ValueError, ZeroDivisionError):
                result = 0
            self.registers[rd] = result
        elif opcode == 0x94:  # LOG2
            if v1 > 0:
                self.registers[rd] = int(math.log2(v1))
            else:
                self.registers[rd] = 0
        elif opcode == 0x95:  # CLZ
            u = _u32(v1)
            if u == 0:
                self.registers[rd] = 32
            else:
                self.registers[rd] = 32 - u.bit_length()
        elif opcode == 0x96:  # CTZ
            u = _u32(v1)
            if u == 0:
                self.registers[rd] = 32
            else:
                self.registers[rd] = (u & -u).bit_length() - 1
        elif opcode == 0x97:  # POPCNT
            self.registers[rd] = bin(_u32(v1)).count("1")
        elif opcode == 0x98:  # CRC32
            self.registers[rd] = 0  # stub
        elif opcode == 0x99:  # SHA256
            self.registers[rd] = 0  # stub
        elif opcode == 0x9A:  # RND
            self.registers[rd] = _s32(self._rng.getrandbits(32))
        elif opcode == 0x9B:  # SEED
            self._rng = random.Random(_u32(v1))
        elif opcode == 0x9C:  # FMOD
            f1, f2 = _reg_to_float(v1), _reg_to_float(v2)
            if f2 == 0.0:
                self.flags.error = True
                self.registers[rd] = 0
            else:
                self.registers[rd] = _float_to_reg(math.fmod(f1, f2))
        elif opcode == 0x9D:  # FSQRT
            f1 = _reg_to_float(v1)
            self.registers[rd] = _float_to_reg(math.sqrt(f1) if f1 >= 0 else 0.0)
        elif opcode == 0x9E:  # FSIN
            self.registers[rd] = _float_to_reg(math.sin(_reg_to_float(v1)))
        elif opcode == 0x9F:  # FCOS
            self.registers[rd] = _float_to_reg(math.cos(_reg_to_float(v1)))

        # -- Collection / Crypto / String (no-op stubs) 0xA2-0xBF --
        elif 0xA2 <= opcode <= 0xA9:
            self.trace.append(f"{name} rd={rd} rs1={rs1} rs2={rs2}")
        elif 0xAB <= opcode <= 0xAF:
            self.trace.append(f"{name} rd={rd} rs1={rs1} rs2={rs2}")
        elif 0xB1 <= opcode <= 0xBF:
            self.trace.append(f"{name} rd={rd} rs1={rs1} rs2={rs2}")

        else:
            self.trace.append(f"UNHANDLED_E 0x{opcode:02X}")

    # -- Format E: conditional jumps -----------------------------------------

    def _exec_e_jump(self, opcode: int, name: str, rd: int, rs1: int, rs2: int) -> None:
        """Handle conditional jumps: JZ, JNZ, JLT, JGT.

        Encoding: [opcode] [check_reg] [compare_reg or unused] [target_reg]
        For JZ/JNZ: jump to registers[target_reg] if registers[check_reg] == 0 / != 0
        For JLT/JGT: jump to registers[target_reg] if registers[check_reg] </> registers[compare_reg]
        """
        base_pc = self.pc + 4
        check_val = self.registers[rd]
        target = self.registers[rs2]

        do_jump = False
        if opcode == 0x3C:  # JZ
            do_jump = (check_val == 0)
        elif opcode == 0x3D:  # JNZ
            do_jump = (check_val != 0)
        elif opcode == 0x3E:  # JLT
            do_jump = (check_val < self.registers[rs1])
        elif opcode == 0x3F:  # JGT
            do_jump = (check_val > self.registers[rs1])

        if do_jump:
            self.pc = target & MASK32
        else:
            self.pc = base_pc

    # -- A2A helpers ---------------------------------------------------------

    def _exec_a2a(self, opcode: int, name: str, rd: int, rs1: int, rs2: int) -> None:
        """Execute A2A opcodes as no-ops that record the operation in the trace."""
        entry = {
            "opcode": opcode,
            "mnemonic": name,
            "rd": rd,
            "rs1": rs1,
            "rs2": rs2,
            "cycle": self.cycle_count,
        }
        self.a2a_log.append(entry)
        self.trace.append(f"A2A:{name} rd={rd} rs1={rs1} rs2={rs2}")

    # -- Format F: 16-bit immediate / control flow ---------------------------

    def _exec_f(self, opcode: int, name: str, rd: int, imm16: int) -> None:
        # Handle jumps specially
        if opcode == 0x43:  # JMP
            self.pc = imm16 & MASK32
            return
        if opcode == 0x44:  # JAL
            self.registers[rd] = self.pc + 4
            self.pc = imm16 & MASK32
            return
        if opcode == 0x45:  # CALL
            if len(self.stack) >= STACK_DEPTH:
                self.flags.error = True
                self.halted = True
                self.halt_error = True
                self.trace.append("CALL: stack overflow")
                return
            self.stack.append(self.pc + 4)
            self.pc = imm16 & MASK32
            return
        if opcode == 0x46:  # LOOP
            self.registers[rd] = _s32(self.registers[rd] - 1)
            if self.registers[rd] != 0:
                self.pc = imm16 & MASK32
            else:
                self.pc += 4
            return

        self.pc += 4

        if opcode == 0x40:  # MOVI16
            self.registers[rd] = imm16
            self.flags.zero = (imm16 == 0)
            self.flags.negative = (imm16 < 0)
        elif opcode == 0x41:  # ADDI16
            result = _s32(self.registers[rd] + imm16)
            self.flags.update_arithmetic(result, self.registers[rd], imm16)
            self.registers[rd] = result
        elif opcode == 0x42:  # SUBI16
            result = _s32(self.registers[rd] - imm16)
            self.flags.update_arithmetic(result, self.registers[rd], imm16, is_sub=True)
            self.registers[rd] = result
        elif opcode == 0x47:  # SELECT: rd = imm16 if negative flag set
            if self.flags.negative:
                self.registers[rd] = imm16
        else:
            self.trace.append(f"UNHANDLED_F 0x{opcode:02X}")

    # -- Format G: memory extensions -----------------------------------------

    def _exec_g(self, opcode: int, name: str, rd: int, rs1: int, imm16: int) -> None:
        # ENTER and LEAVE need special stack handling
        if opcode == 0x4C:  # ENTER
            if len(self.stack) >= STACK_DEPTH:
                self.flags.error = True
                self.halted = True
                self.halt_error = True
                self.trace.append("ENTER: stack overflow")
                return
            self.stack.append(self.registers[15])  # save frame pointer (R15)
            self.pc += 5
            self.trace.append(f"ENTER frame_size={imm16}")
            return
        if opcode == 0x4D:  # LEAVE
            if self.stack:
                self.registers[15] = self.stack.pop()
            # Then RET
            if self.stack:
                self.pc = self.stack.pop()
                self.trace.append(f"LEAVE+RET -> {self.pc}")
            else:
                self.pc += 5
                self.flags.error = True
                self.trace.append("LEAVE: stack underflow")
            return

        self.pc += 5

        if opcode == 0x48:  # LOADOFF
            addr = (self.registers[rs1] + imm16) & 0xFF
            self.registers[rd] = self.memory[addr]
        elif opcode == 0x49:  # STOREOFF
            addr = (self.registers[rs1] + imm16) & 0xFF
            self.memory[addr] = self.registers[rd] & 0xFF
        elif opcode == 0x4A:  # LOADI (indirect)
            addr = self.registers[rs1] & 0xFF
            self.registers[rd] = self.memory[addr]
        elif opcode == 0x4B:  # STOREI (indirect)
            addr = self.registers[rs1] & 0xFF
            self.memory[addr] = self.registers[rd] & 0xFF
        elif opcode == 0x4E:  # COPY
            # Copy imm16 bytes from memory[registers[rs1]] to memory[registers[rd]]
            src = self.registers[rs1] & 0xFF
            dst = self.registers[rd] & 0xFF
            count = imm16 & 0xFF
            for i in range(count):
                self.memory[(dst + i) & 0xFF] = self.memory[(src + i) & 0xFF]
        elif opcode == 0x4F:  # FILL
            # Fill imm16 bytes at memory[registers[rd]] with registers[rs1] & 0xFF
            addr = self.registers[rd] & 0xFF
            count = imm16 & 0xFF
            val = self.registers[rs1] & 0xFF
            for i in range(count):
                self.memory[(addr + i) & 0xFF] = val
        elif opcode == 0xAA:  # KEYGEN
            self.registers[rd] = 0  # stub
        else:
            self.trace.append(f"UNHANDLED_G 0x{opcode:02X}")


# ---------------------------------------------------------------------------
# Test Vector and Result
# ---------------------------------------------------------------------------

@dataclass
class TestVector:
    """Defines a conformance test case."""
    name: str
    bytecode: bytes
    expected_registers: dict[int, int] = field(default_factory=dict)
    expected_memory: dict[int, int] = field(default_factory=dict)
    expected_flags: dict[str, bool] = field(default_factory=dict)
    expected_halt: bool = True
    expected_error: bool = False
    description: str = ""


@dataclass
class ConformanceResult:
    """Result of executing a single test vector."""
    vector_name: str
    passed: bool
    actual_registers: dict[int, int] = field(default_factory=dict)
    actual_memory: dict[int, int] = field(default_factory=dict)
    actual_flags: dict[str, bool] = field(default_factory=dict)
    halted: bool = False
    halt_error: bool = False
    execution_trace: list[str] = field(default_factory=list)
    a2a_log: list[dict[str, Any]] = field(default_factory=list)
    error_message: str = ""


# ---------------------------------------------------------------------------
# VectorGenerator
# ---------------------------------------------------------------------------

class VectorGenerator:
    """Programmatically generates test vectors covering the converged ISA."""

    def __init__(self) -> None:
        self.vectors: list[TestVector] = []

    def generate_all(self) -> list[TestVector]:
        """Generate the full suite of test vectors."""
        self.vectors.clear()
        self._gen_system()
        self._gen_register_ops()
        self._gen_stack_ops()
        self._gen_immediate_ops()
        self._gen_arithmetic()
        self._gen_bitwise()
        self._gen_compare()
        self._gen_float()
        self._gen_memory()
        self._gen_control_flow()
        self._gen_format_f16()
        self._gen_format_g()
        self._gen_extended_math()
        self._gen_float_extended()
        self._gen_a2a()
        self._gen_diagnostics()
        self._gen_edge_cases()
        self._gen_combined()
        return list(self.vectors)

    def _add(self, v: TestVector) -> None:
        self.vectors.append(v)

    # -- System vectors ------------------------------------------------------

    def _gen_system(self) -> None:
        # HALT only
        self._add(TestVector(
            name="system/halt",
            bytecode=encode_a(0x00),
            expected_halt=True,
            expected_error=False,
            description="Simple HALT",
        ))
        # NOP then HALT
        self._add(TestVector(
            name="system/nop_halt",
            bytecode=encode_a(0x01) + encode_a(0x00),
            expected_halt=True,
            description="NOP followed by HALT",
        ))
        # VER sets R0=2
        self._add(TestVector(
            name="system/ver",
            bytecode=encode_a(0xF5) + encode_a(0x00),
            expected_registers={0: 2},
            expected_halt=True,
            description="VER sets R0 to version 2",
        ))
        # ID sets R0=1
        self._add(TestVector(
            name="system/id",
            bytecode=encode_a(0xF4) + encode_a(0x00),
            expected_registers={0: 1},
            description="ID sets R0 to 1",
        ))
        # DUMP does not halt
        self._add(TestVector(
            name="system/dump",
            bytecode=encode_a(0xF2) + encode_a(0x00),
            expected_halt=True,
            description="DUMP followed by HALT",
        ))
        # ASSERT pass (R0 != 0)
        self._add(TestVector(
            name="system/assert_pass",
            bytecode=encode_d(0x18, 0, 42) + encode_a(0xF3) + encode_a(0x00),
            expected_registers={0: 42},
            expected_halt=True,
            expected_error=False,
            description="ASSERT passes when R0 != 0",
        ))
        # ASSERT fail (R0 == 0)
        self._add(TestVector(
            name="system/assert_fail",
            bytecode=encode_a(0xF3),
            expected_halt=True,
            expected_error=True,
            expected_flags={"error": True},
            description="ASSERT fails when R0 == 0",
        ))
        # CLF
        self._add(TestVector(
            name="system/clf",
            bytecode=encode_c(0x13, 0) + encode_a(0x00),
            expected_halt=True,
            expected_flags={"zero": False, "negative": False},
            description="CLF clears all flags",
        ))

    # -- Register ops --------------------------------------------------------

    def _gen_register_ops(self) -> None:
        # INC
        self._add(TestVector(
            name="reg/inc",
            bytecode=encode_d(0x18, 1, 10) + encode_b(0x08, 1) + encode_a(0x00),
            expected_registers={1: 11},
            description="INC R1 (10 -> 11)",
        ))
        # DEC
        self._add(TestVector(
            name="reg/dec",
            bytecode=encode_d(0x18, 1, 10) + encode_b(0x09, 1) + encode_a(0x00),
            expected_registers={1: 9},
            description="DEC R1 (10 -> 9)",
        ))
        # NOT
        self._add(TestVector(
            name="reg/not_zero",
            bytecode=encode_d(0x18, 1, 0) + encode_b(0x0A, 1) + encode_a(0x00),
            expected_registers={1: -1},
            expected_flags={"zero": False, "negative": True},
            description="NOT 0 = -1",
        ))
        # NEG
        self._add(TestVector(
            name="reg/neg",
            bytecode=encode_d(0x18, 1, 5) + encode_b(0x0B, 1) + encode_a(0x00),
            expected_registers={1: -5},
            expected_flags={"negative": True},
            description="NEG R1 (5 -> -5)",
        ))
        # NEG zero
        self._add(TestVector(
            name="reg/neg_zero",
            bytecode=encode_d(0x18, 1, 0) + encode_b(0x0B, 1) + encode_a(0x00),
            expected_registers={1: 0},
            expected_flags={"zero": True},
            description="NEG 0 = 0",
        ))

    # -- Stack ops -----------------------------------------------------------

    def _gen_stack_ops(self) -> None:
        # PUSH + POP
        self._add(TestVector(
            name="stack/push_pop",
            bytecode=(
                encode_d(0x18, 1, 42)
                + encode_b(0x0C, 1)  # PUSH R1
                + encode_d(0x18, 2, 0)  # MOVI R2, 0
                + encode_b(0x0D, 2)  # POP R2
                + encode_a(0x00)
            ),
            expected_registers={1: 42, 2: 42},
            description="PUSH R1 then POP R2",
        ))
        # PUSH + POP multiple
        self._add(TestVector(
            name="stack/push_pop_multi",
            bytecode=(
                encode_d(0x18, 1, 10)
                + encode_b(0x0C, 1)
                + encode_d(0x18, 1, 20)
                + encode_b(0x0C, 1)
                + encode_b(0x0D, 2)
                + encode_b(0x0D, 3)
                + encode_a(0x00)
            ),
            expected_registers={1: 20, 2: 20, 3: 10},
            description="PUSH 10, PUSH 20, POP -> R2=20, POP -> R3=10",
        ))

    # -- Immediate ops -------------------------------------------------------

    def _gen_immediate_ops(self) -> None:
        for val, desc in [(0, "zero"), (1, "one"), (42, "positive"), (127, "max_pos8"),
                          (128, "neg_128"), (255, "neg_1")]:
            self._add(TestVector(
                name=f"imm/movi_{desc}",
                bytecode=encode_d(0x18, 1, val) + encode_a(0x00),
                expected_registers={1: val - 256 if val >= 128 else val},
                description=f"MOVI R1, {val}",
            ))
        # ADDI
        self._add(TestVector(
            name="imm/addi",
            bytecode=encode_d(0x18, 1, 10) + encode_d(0x19, 1, 20) + encode_a(0x00),
            expected_registers={1: 30},
            description="ADDI R1, 20 (10+20=30)",
        ))
        # SUBI
        self._add(TestVector(
            name="imm/subi",
            bytecode=encode_d(0x18, 1, 30) + encode_d(0x1A, 1, 10) + encode_a(0x00),
            expected_registers={1: 20},
            description="SUBI R1, 10 (30-10=20)",
        ))
        # ANDI
        self._add(TestVector(
            name="imm/andi",
            bytecode=encode_d(0x18, 1, 0x0F) + encode_d(0x1B, 1, 0x0F) + encode_a(0x00),
            expected_registers={1: 0x0F},
            description="ANDI R1, 0x0F",
        ))
        # ORI
        self._add(TestVector(
            name="imm/ori",
            bytecode=encode_d(0x18, 1, 0xF0) + encode_d(0x1C, 1, 0x0F) + encode_a(0x00),
            expected_registers={1: 0xFF},
            description="ORI R1, 0x0F",
        ))
        # XORI
        self._add(TestVector(
            name="imm/xori",
            bytecode=encode_d(0x18, 1, 0xFF) + encode_d(0x1D, 1, 0xFF) + encode_a(0x00),
            expected_registers={1: 0},
            expected_flags={"zero": True},
            description="XORI R1, 0xFF (0xFF^0xFF=0)",
        ))
        # SHLI
        self._add(TestVector(
            name="imm/shli",
            bytecode=encode_d(0x18, 1, 1) + encode_d(0x1E, 1, 4) + encode_a(0x00),
            expected_registers={1: 16},
            description="SHLI R1, 4 (1<<4=16)",
        ))
        # SHRI
        self._add(TestVector(
            name="imm/shri",
            bytecode=encode_d(0x18, 1, 16) + encode_d(0x1F, 1, 2) + encode_a(0x00),
            expected_registers={1: 4},
            description="SHRI R1, 2 (16>>2=4)",
        ))

    # -- Arithmetic ----------------------------------------------------------

    def _gen_arithmetic(self) -> None:
        cases = [
            ("add_basic", 0x20, 10, 20, 30),
            ("add_zero", 0x20, 0, 42, 42),
            ("add_neg", 0x20, -5, 3, -2),
            ("sub_basic", 0x21, 30, 10, 20),
            ("sub_neg", 0x21, 5, 10, -5),
            ("mul_basic", 0x22, 6, 7, 42),
            ("mul_zero", 0x22, 42, 0, 0),
            ("div_basic", 0x23, 42, 7, 6),
            ("div_neg", 0x23, -42, 7, -6),
            ("mod_basic", 0x24, 42, 10, 2),
        ]
        for name, op, a, b, expected in cases:
            self._add(TestVector(
                name=f"arith/{name}",
                bytecode=(
                    encode_d(0x18, 1, a & 0xFF if a >= 0 else (a + 256) & 0xFF)
                    + encode_d(0x18, 2, b & 0xFF if b >= 0 else (b + 256) & 0xFF)
                    + encode_e(op, 3, 1, 2)
                    + encode_a(0x00)
                ),
                expected_registers={3: expected},
                description=f"{_OPCODE_NAMES[op]} {a}, {b} = {expected}",
            ))
        # DIV by zero
        self._add(TestVector(
            name="arith/div_by_zero",
            bytecode=(
                encode_d(0x18, 1, 10)
                + encode_d(0x18, 2, 0)
                + encode_e(0x23, 3, 1, 2)
                + encode_a(0x00)
            ),
            expected_registers={3: 0},
            expected_flags={"error": True},
            description="DIV by zero sets error flag, stores 0",
        ))
        # MOD by zero
        self._add(TestVector(
            name="arith/mod_by_zero",
            bytecode=(
                encode_d(0x18, 1, 10)
                + encode_d(0x18, 2, 0)
                + encode_e(0x24, 3, 1, 2)
                + encode_a(0x00)
            ),
            expected_registers={3: 0},
            expected_flags={"error": True},
            description="MOD by zero sets error flag",
        ))

    # -- Bitwise -------------------------------------------------------------

    def _gen_bitwise(self) -> None:
        cases = [
            ("and", 0x25, 0xFF, 0x0F, 0x0F),
            ("or", 0x26, 0xF0, 0x0F, 0xFF),
            ("xor_same", 0x27, 42, 42, 0),
            ("xor_diff", 0x27, 0xFF, 0x00, 0xFF),
            ("shl", 0x28, 1, 8, 256),
            ("shr", 0x29, 256, 8, 1),
            ("min_ab", 0x2A, 3, 7, 3),
            ("min_ba", 0x2A, 7, 3, 3),
            ("max_ab", 0x2B, 3, 7, 7),
            ("max_ba", 0x2B, 7, 3, 7),
        ]
        for name, op, a, b, expected in cases:
            self._add(TestVector(
                name=f"bit/{name}",
                bytecode=(
                    encode_f(0x40, 1, a & 0xFFFF)
                    + encode_f(0x40, 2, b & 0xFFFF)
                    + encode_e(op, 3, 1, 2)
                    + encode_a(0x00)
                ),
                expected_registers={3: expected},
                description=f"{_OPCODE_NAMES[op]} {a}, {b} = {expected}",
            ))

    # -- Compare -------------------------------------------------------------

    def _gen_compare(self) -> None:
        # CMP_EQ equal
        self._add(TestVector(
            name="cmp/eq_true",
            bytecode=(
                encode_f(0x40, 1, 42) + encode_f(0x40, 2, 42)
                + encode_e(0x2C, 3, 1, 2) + encode_a(0x00)
            ),
            expected_registers={3: 1},
            expected_flags={"zero": True},
            description="CMP_EQ 42==42 -> 1",
        ))
        # CMP_EQ not equal
        self._add(TestVector(
            name="cmp/eq_false",
            bytecode=(
                encode_f(0x40, 1, 42) + encode_f(0x40, 2, 7)
                + encode_e(0x2C, 3, 1, 2) + encode_a(0x00)
            ),
            expected_registers={3: 0},
            expected_flags={"zero": False},
            description="CMP_EQ 42!=7 -> 0",
        ))
        # CMP_LT
        self._add(TestVector(
            name="cmp/lt_true",
            bytecode=(
                encode_f(0x40, 1, 3) + encode_f(0x40, 2, 7)
                + encode_e(0x2D, 3, 1, 2) + encode_a(0x00)
            ),
            expected_registers={3: 1},
            expected_flags={"negative": True},
            description="CMP_LT 3<7 -> 1",
        ))
        # CMP_LT false
        self._add(TestVector(
            name="cmp/lt_false",
            bytecode=(
                encode_f(0x40, 1, 7) + encode_f(0x40, 2, 3)
                + encode_e(0x2D, 3, 1, 2) + encode_a(0x00)
            ),
            expected_registers={3: 0},
            description="CMP_LT 7<3 -> 0",
        ))
        # CMP_GT
        self._add(TestVector(
            name="cmp/gt_true",
            bytecode=(
                encode_f(0x40, 1, 7) + encode_f(0x40, 2, 3)
                + encode_e(0x2E, 3, 1, 2) + encode_a(0x00)
            ),
            expected_registers={3: 1},
            description="CMP_GT 7>3 -> 1",
        ))
        # CMP_NE
        self._add(TestVector(
            name="cmp/ne_true",
            bytecode=(
                encode_f(0x40, 1, 42) + encode_f(0x40, 2, 7)
                + encode_e(0x2F, 3, 1, 2) + encode_a(0x00)
            ),
            expected_registers={3: 1},
            description="CMP_NE 42!=7 -> 1",
        ))
        # CMP_NE false
        self._add(TestVector(
            name="cmp/ne_false",
            bytecode=(
                encode_f(0x40, 1, 42) + encode_f(0x40, 2, 42)
                + encode_e(0x2F, 3, 1, 2) + encode_a(0x00)
            ),
            expected_registers={3: 0},
            expected_flags={"zero": True},
            description="CMP_NE 42==42 -> 0",
        ))

    # -- Float ---------------------------------------------------------------

    def _gen_float(self) -> None:
        # FADD: 1.0 + 2.0 = 3.0
        fa1 = _float_to_reg(1.0)
        fa2 = _float_to_reg(2.0)
        fa3 = _float_to_reg(3.0)
        self._add(TestVector(
            name="float/fadd",
            bytecode=(
                encode_f(0x40, 1, fa1 & 0xFFFF)
                + encode_d(0x18, 2, (fa1 >> 16) & 0xFF)
                + encode_e(0x37, 1, 1, 0)  # ITOF R1
                + encode_f(0x40, 2, fa2 & 0xFFFF)
                + encode_d(0x18, 3, (fa2 >> 16) & 0xFF)
                + encode_e(0x37, 2, 2, 0)  # ITOF R2
                + encode_e(0x30, 1, 1, 2)  # FADD R1, R1, R2
                + encode_a(0x00)
            ),
            expected_registers={1: fa3},
            description="FADD 1.0 + 2.0 = 3.0",
        ))
        # ITOF and FTOI round-trip
        self._add(TestVector(
            name="float/itof_ftoi_roundtrip",
            bytecode=(
                encode_f(0x40, 1, 42)
                + encode_e(0x37, 2, 1, 0)  # ITOF R2, R1
                + encode_e(0x36, 3, 2, 0)  # FTOI R3, R2
                + encode_a(0x00)
            ),
            expected_registers={1: 42, 3: 42},
            description="ITOF then FTOI round-trip preserves value",
        ))

    # -- Memory --------------------------------------------------------------

    def _gen_memory(self) -> None:
        # STORE + LOAD round-trip
        self._add(TestVector(
            name="mem/store_load",
            bytecode=(
                encode_d(0x18, 1, 42)  # MOVI R1, 42
                + encode_d(0x18, 2, 10)  # MOVI R2, 10 (address)
                + encode_e(0x39, 1, 2, 0)  # STORE R1 -> mem[R2]
                + encode_d(0x18, 3, 0)  # MOVI R3, 0
                + encode_e(0x38, 3, 2, 0)  # LOAD R3 <- mem[R2]
                + encode_a(0x00)
            ),
            expected_registers={1: 42, 3: 42},
            expected_memory={10: 42},
            description="STORE then LOAD round-trip",
        ))
        # MOV
        self._add(TestVector(
            name="mem/mov",
            bytecode=encode_d(0x18, 1, 99) + encode_e(0x3A, 2, 1, 0) + encode_a(0x00),
            expected_registers={1: 99, 2: 99},
            description="MOV R2, R1",
        ))
        # SWP
        self._add(TestVector(
            name="mem/swp",
            bytecode=(
                encode_d(0x18, 1, 10) + encode_d(0x18, 2, 20)
                + encode_e(0x3B, 1, 2, 0) + encode_a(0x00)
            ),
            expected_registers={1: 20, 2: 10},
            description="SWP R1, R2",
        ))

    # -- Control flow --------------------------------------------------------

    def _gen_control_flow(self) -> None:
        # JZ taken (skip over MOVI)
        # MOVI R1, 0; MOVI R3, 1; JZ R1, _, R4(R4=addr_of_skip); MOVI R1, 99; skip: HALT
        # Let's compute addresses carefully
        # byte 0-2: MOVI R1, 0 (3 bytes)
        # byte 3-5: MOVI R3, 1 (3 bytes) -- unused, just filler
        # byte 6-9: JZ R1, _, R4 (4 bytes)
        # byte 10-12: MOVI R1, 99 (3 bytes) -- should be skipped
        # byte 13: HALT -- target for R4
        # R4 should point to byte 13
        self._add(TestVector(
            name="ctrl/jz_taken",
            bytecode=(
                encode_d(0x18, 1, 0)          # 0-2: MOVI R1, 0
                + encode_d(0x18, 3, 0)        # 3-5: MOVI R3, 0 (filler)
                + encode_f(0x40, 4, 13)       # 6-9: MOVI16 R4, 13 (HALT addr)
                + encode_e(0x3C, 1, 0, 4)     # 10-13: JZ R1, _, R4 -> jump to 13
                + encode_d(0x18, 1, 99)       # 14-16: MOVI R1, 99 (skipped)
                + encode_a(0x00)              # 17: HALT (not reached from JZ)
                + encode_a(0x00)              # 18: HALT (extra)
            ),
            expected_registers={1: 0, 4: 13},
            expected_halt=True,
            description="JZ taken when R1==0",
        ))
        # JNZ not taken (R1==0, so don't jump)
        self._add(TestVector(
            name="ctrl/jnz_not_taken",
            bytecode=(
                encode_d(0x18, 1, 0)          # MOVI R1, 0
                + encode_f(0x40, 4, 100)      # MOVI16 R4, 100 (far away)
                + encode_e(0x3D, 1, 0, 4)     # JNZ R1, _, R4 (not taken)
                + encode_d(0x18, 2, 77)       # MOVI R2, 77
                + encode_a(0x00)              # HALT
            ),
            expected_registers={1: 0, 2: 77},
            expected_halt=True,
            description="JNZ not taken when R1==0",
        ))
        # JNZ taken
        self._add(TestVector(
            name="ctrl/jnz_taken",
            bytecode=(
                encode_d(0x18, 1, 42)         # MOVI R1, 42
                + encode_f(0x40, 4, 11)       # MOVI16 R4, 11
                + encode_e(0x3D, 1, 0, 4)     # JNZ R1, _, R4 (taken -> PC=11)
                + encode_d(0x18, 1, 0)        # MOVI R1, 0 (skipped)
                + encode_a(0x00)              # HALT (skipped)
                + encode_a(0x00)              # byte 11: HALT (target)
            ),
            expected_registers={1: 42},
            expected_halt=True,
            description="JNZ taken when R1!=0",
        ))
        # JMP
        self._add(TestVector(
            name="ctrl/jmp",
            bytecode=(
                encode_f(0x43, 0, 3)  # JMP to addr 3
                + encode_a(0x00)      # byte 1: skipped
                + encode_a(0x00)      # byte 2: skipped
                + encode_a(0x00)      # byte 3: HALT (target)
            ),
            expected_halt=True,
            description="JMP to HALT",
        ))
        # CALL + RET
        self._add(TestVector(
            name="ctrl/call_ret",
            bytecode=(
                encode_d(0x18, 1, 10)         # 0-2: MOVI R1, 10
                + encode_f(0x45, 0, 6)        # 3-6: CALL addr 6
                + encode_a(0x00)              # 7: HALT (shouldn't reach here from call path)
                + encode_d(0x1A, 1, 5)        # 7-9: SUBI R1, 5 (actually at byte 7.. wait)
                + encode_a(0x02)              # RET
            ),
            expected_registers={1: 5},
            expected_halt=True,
            description="CALL subroutine, modify R1, RET",
        ))
        # JAL
        self._add(TestVector(
            name="ctrl/jal",
            bytecode=(
                encode_f(0x44, 15, 6)         # JAL R15, addr 6
                + encode_d(0x18, 0, 0)        # MOVI R0, 0 (should be skipped by jump)
                + encode_a(0x00)              # HALT
                + encode_d(0x18, 1, 99)       # MOVI R1, 99 (at addr 6)
                + encode_e(0x3A, 0, 15, 0)    # MOV R0, R15 (restore)
                + encode_a(0x00)              # HALT
            ),
            expected_registers={0: 4, 1: 99},
            expected_halt=True,
            description="JAL saves return addr in R15, jumps, returns via MOV",
        ))
        # LOOP
        self._add(TestVector(
            name="ctrl/loop",
            bytecode=(
                encode_d(0x18, 1, 3)          # MOVI R1, 3 (loop counter)
                + encode_f(0x40, 2, 0)        # MOVI16 R2, 0 (accumulator)
                # Loop body: INC R2, LOOP R1, back_to_loop_start
                # addr 6: INC R2
                + encode_b(0x08, 2)           # 6-7: INC R2
                # addr 8: LOOP R1, addr 6
                + encode_f(0x46, 1, 6)        # 8-11: LOOP R1, 6
                + encode_a(0x00)              # HALT
            ),
            expected_registers={1: 0, 2: 3},
            expected_halt=True,
            description="LOOP decrements R1 from 3 to 0, R2 incremented 3 times",
        ))

    # -- Format F 16-bit immediate -------------------------------------------

    def _gen_format_f16(self) -> None:
        self._add(TestVector(
            name="f16/movi16",
            bytecode=encode_f(0x40, 1, 1000) + encode_a(0x00),
            expected_registers={1: 1000},
            description="MOVI16 R1, 1000",
        ))
        self._add(TestVector(
            name="f16/movi16_neg",
            bytecode=encode_f(0x40, 1, (-1000) & 0xFFFF) + encode_a(0x00),
            expected_registers={1: -1000},
            description="MOVI16 R1, -1000",
        ))
        self._add(TestVector(
            name="f16/movi16_max",
            bytecode=encode_f(0x40, 1, 0x7FFF) + encode_a(0x00),
            expected_registers={1: 0x7FFF},
            description="MOVI16 R1, 32767",
        ))
        self._add(TestVector(
            name="f16/movi16_min",
            bytecode=encode_f(0x40, 1, 0x8000) + encode_a(0x00),
            expected_registers={1: -0x8000},
            expected_flags={"negative": True},
            description="MOVI16 R1, -32768",
        ))
        self._add(TestVector(
            name="f16/addi16",
            bytecode=encode_f(0x40, 1, 100) + encode_f(0x41, 1, 200) + encode_a(0x00),
            expected_registers={1: 300},
            description="ADDI16 R1, 200 (100+200=300)",
        ))
        self._add(TestVector(
            name="f16/subi16",
            bytecode=encode_f(0x40, 1, 300) + encode_f(0x42, 1, 100) + encode_a(0x00),
            expected_registers={1: 200},
            description="SUBI16 R1, 100 (300-100=200)",
        ))

    # -- Format G ------------------------------------------------------------

    def _gen_format_g(self) -> None:
        # LOADOFF
        self._add(TestVector(
            name="g/loadoff",
            bytecode=(
                encode_d(0x18, 1, 42)          # MOVI R1, 42
                + encode_d(0x18, 2, 5)         # MOVI R2, 5
                + encode_e(0x39, 1, 2, 0)      # STORE R1 -> mem[R2]
                + encode_g(0x48, 3, 2, 0)      # LOADOFF R3, R2, offset=0
                + encode_a(0x00)
            ),
            expected_registers={1: 42, 3: 42},
            expected_memory={5: 42},
            description="LOADOFF with offset 0",
        ))
        # STOREOFF
        self._add(TestVector(
            name="g/storeoff",
            bytecode=(
                encode_d(0x18, 1, 77)          # MOVI R1, 77
                + encode_d(0x18, 2, 10)        # MOVI R2, 10
                + encode_g(0x49, 1, 2, 0)      # STOREOFF R1, R2, offset=0
                + encode_a(0x00)
            ),
            expected_registers={1: 77},
            expected_memory={10: 77},
            description="STOREOFF with offset 0",
        ))
        # LOADI (indirect)
        self._add(TestVector(
            name="g/loadi",
            bytecode=(
                encode_d(0x18, 1, 55)          # MOVI R1, 55
                + encode_d(0x18, 2, 8)         # MOVI R2, 8 (address)
                + encode_e(0x39, 1, 2, 0)      # STORE R1 -> mem[R2]
                + encode_g(0x4A, 3, 2, 0)      # LOADI R3, [R2]
                + encode_a(0x00)
            ),
            expected_registers={3: 55},
            expected_memory={8: 55},
            description="LOADI indirect load",
        ))
        # FILL
        self._add(TestVector(
            name="g/fill",
            bytecode=(
                encode_d(0x18, 1, 0xAB)        # MOVI R1, 0xAB
                + encode_d(0x18, 2, 20)        # MOVI R2, 20 (start addr)
                + encode_g(0x4F, 2, 1, 4)      # FILL addr=R2, val=R1, count=4
                + encode_a(0x00)
            ),
            expected_memory={20: 0xAB, 21: 0xAB, 22: 0xAB, 23: 0xAB},
            description="FILL 4 bytes with 0xAB",
        ))
        # COPY
        self._add(TestVector(
            name="g/copy",
            bytecode=(
                encode_d(0x18, 1, 0xCC)        # MOVI R1, 0xCC
                + encode_d(0x18, 2, 10)        # MOVI R2, 10 (src)
                + encode_e(0x39, 1, 2, 0)      # STORE R1 -> mem[10]
                + encode_g(0x4E, 3, 2, 1)      # COPY dst=R3(=0), src=R2(=10), count=1
                + encode_a(0x00)
            ),
            expected_memory={0: 0xCC, 10: 0xCC},
            description="COPY 1 byte from addr 10 to addr 0",
        ))

    # -- Extended math -------------------------------------------------------

    def _gen_extended_math(self) -> None:
        # ABS
        self._add(TestVector(
            name="ext/abs_neg",
            bytecode=encode_f(0x40, 1, (-42) & 0xFFFF) + encode_e(0x90, 2, 1, 0) + encode_a(0x00),
            expected_registers={1: -42, 2: 42},
            description="ABS(-42) = 42",
        ))
        self._add(TestVector(
            name="ext/abs_pos",
            bytecode=encode_d(0x18, 1, 42) + encode_e(0x90, 2, 1, 0) + encode_a(0x00),
            expected_registers={2: 42},
            description="ABS(42) = 42",
        ))
        # SIGN
        self._add(TestVector(
            name="ext/sign_neg",
            bytecode=encode_f(0x40, 1, (-5) & 0xFFFF) + encode_e(0x91, 2, 1, 0) + encode_a(0x00),
            expected_registers={2: -1},
            description="SIGN(-5) = -1",
        ))
        self._add(TestVector(
            name="ext/sign_zero",
            bytecode=encode_d(0x18, 1, 0) + encode_e(0x91, 2, 1, 0) + encode_a(0x00),
            expected_registers={2: 0},
            description="SIGN(0) = 0",
        ))
        self._add(TestVector(
            name="ext/sign_pos",
            bytecode=encode_d(0x18, 1, 7) + encode_e(0x91, 2, 1, 0) + encode_a(0x00),
            expected_registers={2: 1},
            description="SIGN(7) = 1",
        ))
        # SQRT
        self._add(TestVector(
            name="ext/sqrt",
            bytecode=encode_d(0x18, 1, 16) + encode_e(0x92, 2, 1, 0) + encode_a(0x00),
            expected_registers={2: 4},
            description="SQRT(16) = 4",
        ))
        # CLZ
        self._add(TestVector(
            name="ext/clz_1",
            bytecode=encode_d(0x18, 1, 1) + encode_e(0x95, 2, 1, 0) + encode_a(0x00),
            expected_registers={2: 31},
            description="CLZ(1) = 31",
        ))
        # CTZ
        self._add(TestVector(
            name="ext/ctz_8",
            bytecode=encode_d(0x18, 1, 8) + encode_e(0x96, 2, 1, 0) + encode_a(0x00),
            expected_registers={2: 3},
            description="CTZ(8) = 3",
        ))
        # POPCNT
        self._add(TestVector(
            name="ext/popcnt_ff",
            bytecode=encode_d(0x18, 1, 0xFF) + encode_e(0x97, 2, 1, 0) + encode_a(0x00),
            expected_registers={2: 8},
            description="POPCNT(0xFF) = 8",
        ))
        # SEED + RND (deterministic)
        self._add(TestVector(
            name="ext/seed_rnd",
            bytecode=(
                encode_f(0x40, 1, 12345)       # MOVI16 R1, 12345
                + encode_e(0x9B, 0, 1, 0)     # SEED R0, R1
                + encode_e(0x9A, 2, 0, 0)     # RND R2
                + encode_a(0x00)
            ),
            description="SEED then RND produces deterministic value",
        ))

    # -- Float extended ------------------------------------------------------

    def _gen_float_extended(self) -> None:
        # FSQRT
        f4 = _float_to_reg(4.0)
        f2 = _float_to_reg(2.0)
        self._add(TestVector(
            name="fext/fsqrt",
            bytecode=(
                encode_f(0x40, 1, f4 & 0xFFFF)
                + encode_d(0x18, 2, (f4 >> 16) & 0xFF)
                + encode_e(0x37, 1, 1, 0)  # ITOF R1
                + encode_e(0x9D, 2, 1, 0)  # FSQRT R2, R1
                + encode_a(0x00)
            ),
            expected_registers={2: f2},
            description="FSQRT(4.0) = 2.0",
        ))

    # -- A2A -----------------------------------------------------------------

    def _gen_a2a(self) -> None:
        a2a_ops = [0x50, 0x51, 0x52, 0x53, 0x54, 0x55, 0x56, 0x57,
                    0x58, 0x59, 0x5A, 0x5B, 0x5C, 0x5D, 0x5E, 0x5F]
        for op in a2a_ops:
            name = _OPCODE_NAMES.get(op, f"OP_0x{op:02X}")
            self._add(TestVector(
                name=f"a2a/{name.lower()}",
                bytecode=encode_e(op, 1, 2, 3) + encode_a(0x00),
                expected_halt=True,
                expected_error=False,
                description=f"{name} is a no-op that logs to a2a trace",
            ))

    # -- Diagnostics ---------------------------------------------------------

    def _gen_diagnostics(self) -> None:
        # HALT_ERR
        self._add(TestVector(
            name="diag/halt_err",
            bytecode=encode_a(0xF0),
            expected_halt=True,
            expected_error=True,
            expected_flags={"error": True},
            description="HALT_ERR halts with error",
        ))
        # ILLEGAL
        self._add(TestVector(
            name="diag/illegal",
            bytecode=encode_a(0xFF),
            expected_halt=True,
            expected_error=True,
            expected_flags={"error": True},
            description="ILLEGAL halts with error",
        ))

    # -- Edge cases ----------------------------------------------------------

    def _gen_edge_cases(self) -> None:
        # Overflow: ADD max + 1
        self._add(TestVector(
            name="edge/add_overflow",
            bytecode=(
                encode_f(0x40, 1, 0x7FFF)       # MOVI16 R1, 32767
                + encode_f(0x40, 2, 0x7FFF)     # MOVI16 R2, 32767
                + encode_e(0x20, 3, 1, 2)       # ADD R3 = R1 + R2
                + encode_a(0x00)
            ),
            expected_registers={3: -2},  # 65534 as signed 32-bit = 65534, but 0x7FFF + 0x7FFF = 0xFFFE
            description="ADD overflow wraps around",
        ))
        # Negative immediate
        self._add(TestVector(
            name="edge/neg_immediate",
            bytecode=encode_d(0x18, 1, 0x80) + encode_a(0x00),
            expected_registers={1: -128},
            expected_flags={"negative": True},
            description="MOVI R1, 0x80 (-128 sign-extended)",
        ))

    # -- Combined / multi-step programs --------------------------------------

    def _gen_combined(self) -> None:
        # Compute factorial of 5 iteratively
        # R1 = 5, R2 = 1 (result), loop: R2 *= R1, R1--, if R1 > 0 goto loop
        # Using LOOP for the decrement-and-branch:
        # MOVI16 R1, 5; MOVI16 R2, 1;
        # loop: MUL R2, R2, R1; LOOP R1, loop;
        self._add(TestVector(
            name="combined/factorial5",
            bytecode=(
                encode_f(0x40, 1, 5)           # 0-3: MOVI16 R1, 5
                + encode_f(0x40, 2, 1)         # 4-7: MOVI16 R2, 1
                # loop at byte 8:
                + encode_e(0x22, 2, 2, 1)      # 8-11: MUL R2, R2, R1
                + encode_f(0x46, 1, 8)         # 12-15: LOOP R1, 8
                + encode_a(0x00)               # 16: HALT
            ),
            expected_registers={1: 0, 2: 120},
            expected_halt=True,
            description="Factorial of 5 = 120 using LOOP",
        ))
        # Sum 1..10
        # R1 = 10, R2 = 0, loop: ADD R2, R2, R1, DEC R1, JNZ R1, _, loop
        self._add(TestVector(
            name="combined/sum_1_to_10",
            bytecode=(
                encode_f(0x40, 1, 10)          # MOVI16 R1, 10
                + encode_d(0x18, 2, 0)         # MOVI R2, 0
                # loop at byte 7:
                + encode_e(0x20, 2, 2, 1)      # ADD R2, R2, R1
                + encode_b(0x09, 1)            # DEC R1
                + encode_f(0x40, 3, 7)         # MOVI16 R3, 7 (loop start)
                + encode_e(0x3D, 1, 0, 3)      # JNZ R1, _, R3
                + encode_a(0x00)               # HALT
            ),
            expected_registers={1: 0, 2: 55},
            expected_halt=True,
            description="Sum 1..10 = 55",
        ))
        # Memory copy and verify
        self._add(TestVector(
            name="combined/mem_copy_verify",
            bytecode=(
                encode_d(0x18, 1, 0xAA)        # MOVI R1, 0xAA
                + encode_d(0x18, 2, 50)        # MOVI R2, 50 (src)
                + encode_e(0x39, 1, 2, 0)      # STORE R1 -> mem[50]
                + encode_d(0x18, 3, 100)       # MOVI R3, 100 (dst)
                + encode_g(0x4E, 3, 2, 1)      # COPY 1 byte from 50 to 100
                + encode_g(0x48, 4, 3, 0)      # LOADOFF R4, [R3+0]
                + encode_e(0x2C, 5, 1, 4)      # CMP_EQ R5, R1, R4
                + encode_a(0x00)
            ),
            expected_registers={1: 0xAA, 4: 0xAA, 5: 1},
            expected_memory={50: 0xAA, 100: 0xAA},
            expected_flags={"zero": True},
            description="Copy byte in memory and verify equality",
        ))


# ---------------------------------------------------------------------------
# ConformanceRunner
# ---------------------------------------------------------------------------

class ConformanceRunner:
    """Executes test vectors against MiniVM and produces conformance results."""

    def __init__(self) -> None:
        self.vm = MiniVM()

    def run_vector(self, vector: TestVector) -> ConformanceResult:
        """Execute a single test vector and return the result."""
        self.vm.reset()
        self.vm.load(vector.bytecode)
        self.vm.run()

        actual_regs: dict[int, int] = {i: self.vm.registers[i] for i in range(NUM_REGISTERS)}
        actual_mem: dict[int, int] = {i: self.vm.memory[i] for i in range(MEMORY_SIZE)}
        actual_flags: dict[str, bool] = {
            "zero": self.vm.flags.zero,
            "negative": self.vm.flags.negative,
            "overflow": self.vm.flags.overflow,
            "carry": self.vm.flags.carry,
            "error": self.vm.flags.error,
        }

        passed = True
        errors: list[str] = []

        # Check halt state
        if vector.expected_halt and not self.vm.halted:
            passed = False
            errors.append("Expected halt but VM did not halt")
        if not vector.expected_halt and self.vm.halted:
            passed = False
            errors.append("Expected no halt but VM halted")

        # Check error state
        if vector.expected_error and not self.vm.halt_error:
            passed = False
            errors.append("Expected halt_error but VM halted normally")
        if not vector.expected_error and self.vm.halt_error:
            passed = False
            errors.append(f"Expected normal halt but VM had error")

        # Check registers (partial match)
        for reg_idx, expected_val in vector.expected_registers.items():
            if actual_regs[reg_idx] != expected_val:
                passed = False
                errors.append(
                    f"Register R{reg_idx}: expected {expected_val}, got {actual_regs[reg_idx]}"
                )

        # Check memory (partial match)
        for addr, expected_byte in vector.expected_memory.items():
            if actual_mem[addr] != expected_byte:
                passed = False
                errors.append(
                    f"Memory[{addr}]: expected {expected_byte}, got {actual_mem[addr]}"
                )

        # Check flags (partial match)
        for flag_name, expected_val in vector.expected_flags.items():
            if actual_flags.get(flag_name) != expected_val:
                passed = False
                errors.append(
                    f"Flag {flag_name}: expected {expected_val}, got {actual_flags.get(flag_name)}"
                )

        return ConformanceResult(
            vector_name=vector.name,
            passed=passed,
            actual_registers=actual_regs,
            actual_memory=actual_mem,
            actual_flags=actual_flags,
            halted=self.vm.halted,
            halt_error=self.vm.halt_error,
            execution_trace=list(self.vm.trace),
            a2a_log=list(self.vm.a2a_log),
            error_message="; ".join(errors),
        )

    def run_all(self, vectors: list[TestVector]) -> list[ConformanceResult]:
        """Execute all test vectors and return results."""
        return [self.run_vector(v) for v in vectors]


# ---------------------------------------------------------------------------
# ConformanceReporter
# ---------------------------------------------------------------------------

class ConformanceReporter:
    """Formats conformance test results into human-readable reports."""

    @staticmethod
    def summary(results: list[ConformanceResult]) -> dict[str, Any]:
        """Generate a summary of test results."""
        total = len(results)
        passed = sum(1 for r in results if r.passed)
        failed = total - passed

        # Per-category breakdown
        categories: dict[str, dict[str, int]] = {}
        for r in results:
            cat = r.vector_name.split("/")[0] if "/" in r.vector_name else "unknown"
            if cat not in categories:
                categories[cat] = {"total": 0, "passed": 0, "failed": 0}
            categories[cat]["total"] += 1
            if r.passed:
                categories[cat]["passed"] += 1
            else:
                categories[cat]["failed"] += 1

        return {
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": round(passed / total, 4) if total else 0.0,
            "categories": categories,
        }

    @staticmethod
    def to_markdown(results: list[ConformanceResult]) -> str:
        """Generate a Markdown report."""
        summ = ConformanceReporter.summary(results)
        lines: list[str] = []
        lines.append("# FLUX Conformance Test Report")
        lines.append("")
        lines.append(f"**Total:** {summ['total']}  ")
        lines.append(f"**Passed:** {summ['passed']}  ")
        lines.append(f"**Failed:** {summ['failed']}  ")
        lines.append(f"**Pass Rate:** {summ['pass_rate']:.1%}")
        lines.append("")
        lines.append("## Category Breakdown")
        lines.append("")
        lines.append("| Category | Total | Passed | Failed | Rate |")
        lines.append("|----------|-------|--------|--------|------|")
        for cat, stats in sorted(summ["categories"].items()):
            rate = stats["passed"] / stats["total"] if stats["total"] else 0
            lines.append(f"| {cat} | {stats['total']} | {stats['passed']} | {stats['failed']} | {rate:.1%} |")
        lines.append("")

        # Failed tests detail
        failed = [r for r in results if not r.passed]
        if failed:
            lines.append("## Failed Tests")
            lines.append("")
            for r in failed:
                lines.append(f"### `{r.vector_name}`")
                lines.append(f"- **Error:** {r.error_message}")
                if r.execution_trace:
                    lines.append(f"- **Last trace:** {r.execution_trace[-1] if r.execution_trace else 'N/A'}")
                lines.append("")

        return "\n".join(lines)

    @staticmethod
    def to_json(results: list[ConformanceResult]) -> str:
        """Generate a JSON report."""
        import json
        summ = ConformanceReporter.summary(results)
        data = {
            "summary": summ,
            "results": [
                {
                    "name": r.vector_name,
                    "passed": r.passed,
                    "halted": r.halted,
                    "halt_error": r.halt_error,
                    "error_message": r.error_message,
                    "registers": {f"R{k}": v for k, v in r.actual_registers.items() if v != 0},
                    "flags": r.actual_flags,
                }
                for r in results
            ],
        }
        return json.dumps(data, indent=2)
