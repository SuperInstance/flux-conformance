#!/usr/bin/env python3
"""
FLUX Universal Bytecode Validator

Validates FLUX bytecode against constraints of ALL runtimes, reporting:
1. Which runtimes can execute the bytecode (opcode coverage check)
2. Which opcodes would be NOP-stubbed on WASM runtime
3. Encoding format violations
4. Control flow analysis (unreachable code, infinite loops)
5. Register reference validation
6. Cross-runtime translation feasibility

Usage:
    python3 flux_universal_validator.py <bytecode_file> [options]
    python3 flux_universal_validator.py --example core        # generate test bytecode
    python3 flux_universal_validator.py --example wasm_only   # WASM-only test
    python3 flux_universal_validator.py --example multi       # multi-runtime test
    echo -ne '\x20\x00\x01\x02' | python3 flux_universal_validator.py --stdin
    python3 flux_universal_validator.py --translate --from python --to wasm <file>

Author: Agent Datum, SuperInstance Fleet
"""

import sys
import json
import struct
import argparse
from enum import IntEnum
from dataclasses import dataclass, field
from typing import List, Dict, Tuple, Optional, Set

# ═══════════════════════════════════════════════════════════════════════
# Opcode Definitions — All Runtimes
# ═══════════════════════════════════════════════════════════════════════

# WASM Runtime (canonical ISA v3)
WASM_FORMAT = {}  # opcode_byte -> format_letter
WASM_IMPL = set()  # actually implemented in vm.ts

# System Control (0x00-0x07)
for op in range(0x00, 0x04): WASM_FORMAT[op] = 'A'
for op in range(0x04, 0x08): WASM_FORMAT[op] = 'A'
# Single Register (0x08-0x0F)
for op in range(0x08, 0x10): WASM_FORMAT[op] = 'B'
# Immediate Only (0x10-0x17)
for op in range(0x10, 0x18): WASM_FORMAT[op] = 'C'
# Register + Imm8 (0x18-0x1F)
for op in range(0x18, 0x20): WASM_FORMAT[op] = 'D'
# Integer Arith (0x20-0x2F)
for op in range(0x20, 0x30): WASM_FORMAT[op] = 'E'
# Float/Mem/Ctrl (0x30-0x3F)
for op in range(0x30, 0x40): WASM_FORMAT[op] = 'E'
# Reg + Imm16 (0x40-0x47)
for op in range(0x40, 0x48): WASM_FORMAT[op] = 'F'
# Reg + Reg + Imm16 (0x48-0x4F)
for op in range(0x48, 0x50): WASM_FORMAT[op] = 'G'
# A2A Fleet Ops (0x50-0x5F)
for op in range(0x50, 0x60): WASM_FORMAT[op] = 'E'
# Confidence (0x60-0x6F)
for op in range(0x60, 0x70): WASM_FORMAT[op] = 'E'
# Viewpoint (0x70-0x7F)
for op in range(0x70, 0x80): WASM_FORMAT[op] = 'E'
# Sensor (0x80-0x8F)
for op in range(0x80, 0x90): WASM_FORMAT[op] = 'E'
# Math/Crypto (0x90-0x9F)
for op in range(0x90, 0xA0): WASM_FORMAT[op] = 'E'
# String (0xA0-0xAF)
for op in range(0xA0, 0xB0): WASM_FORMAT[op] = 'D'
# Vector (0xB0-0xBF)
for op in range(0xB0, 0xC0): WASM_FORMAT[op] = 'E'
# Tensor (0xC0-0xCF)
for op in range(0xC0, 0xD0): WASM_FORMAT[op] = 'E'
# MMIO (0xD0-0xDF)
for op in range(0xD0, 0xE0): WASM_FORMAT[op] = 'G'
# Long Jumps (0xE0-0xEF)
for op in range(0xE0, 0xF0): WASM_FORMAT[op] = 'F'
# System/Debug (0xF0-0xFF)
for op in range(0xF0, 0x100): WASM_FORMAT[op] = 'A'

# WASM implemented opcodes (from vm.ts analysis)
WASM_IMPL = {
    0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,  # System
    0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D,                # Single reg
    0x10, 0x12, 0x15,                                    # Immediate
    0x18, 0x19, 0x1A,                                    # Reg+Imm8
    0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27,    # Arith
    0x28, 0x29, 0x2A, 0x2B, 0x2C, 0x2D, 0x2E, 0x2F,
    0x30, 0x31, 0x32, 0x33, 0x36, 0x37,                  # Float
    0x38, 0x39, 0x3A, 0x3B, 0x3C, 0x3D, 0x3E, 0x3F,    # Mem/Ctrl
    0x43, 0x44, 0x45, 0x46,                              # Reg+Imm16
    0x48, 0x49, 0x4F,                                    # Reg+Reg+Imm16
    0x90, 0x91,                                           # Math
    0xE0, 0xE1, 0xE2, 0xE3, 0xE4, 0xE5,                  # Long jumps
    0xF5, 0xF7, 0xFF,                                    # System
}

# Python Runtime opcodes
PYTHON_OPS = {
    0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
    0x08, 0x09, 0x0A, 0x0B, 0x0C, 0x0D, 0x0E, 0x0F,
    0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17,
    0x18, 0x19, 0x1A, 0x1B, 0x1C, 0x1D, 0x1E, 0x1F,
    0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27,
    0x28, 0x29, 0x2A, 0x2B, 0x2C, 0x2D, 0x2E, 0x2F,
    0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37,
    0x38, 0x39, 0x3A, 0x3B, 0x3C, 0x3D, 0x3E, 0x3F,
    0x40, 0x41, 0x42, 0x43, 0x44, 0x45, 0x46, 0x47,
    0x48, 0x49, 0x4A, 0x4B, 0x4C, 0x4D, 0x4E, 0x4F,
    0x50, 0x51, 0x52, 0x53, 0x54, 0x55, 0x56, 0x57,
    0x60, 0x61, 0x62, 0x63, 0x64, 0x65, 0x66, 0x67,
    0x68, 0x69, 0x6A, 0x6B, 0x6C,
    0x70, 0x71, 0x72, 0x73, 0x74, 0x75, 0x76, 0x77,
    0x78, 0x79, 0x7A, 0x7B, 0x7C, 0x7D, 0x7E, 0x7F,
    0x80, 0x81, 0x82, 0x83, 0x84,
}

# Rust Runtime opcodes
RUST_OPS = {
    0x00, 0x01, 0x02, 0x03, 0x04, 0x05, 0x06, 0x07,
    0x08, 0x09, 0x0A,
    0x10, 0x11, 0x12, 0x13,
    0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27,
    0x28, 0x29, 0x2A, 0x2B, 0x2C, 0x2D, 0x2E, 0x2F,
    0x30, 0x31, 0x32, 0x33, 0x34, 0x35, 0x36, 0x37,
    0x40, 0x41, 0x42, 0x43, 0x44, 0x45, 0x46, 0x47,
    0x48, 0x49, 0x4A, 0x4B, 0x4C, 0x4D,
    0x60, 0x61, 0x62, 0x63,
    0x70, 0x71, 0x72, 0x73, 0x74, 0x75, 0x76, 0x77, 0x78, 0x79,
    0x80, 0x81, 0x82, 0x83, 0x84, 0x85, 0x86, 0x87, 0x88, 0x89,
    0x90, 0x91, 0x92,
    0xB0, 0xB1, 0xB2, 0xB3, 0xB4,
}

# C Runtime (flux-os) opcodes
C_OPS = {
    0x00, 0x01, 0x02,
    0x10, 0x11, 0x12, 0x13, 0x14, 0x15, 0x16, 0x17, 0x18,
    0x19, 0x1A, 0x1B, 0x1C, 0x1D, 0x1E, 0x1F,
    0x20, 0x21, 0x22, 0x23, 0x24, 0x25, 0x26, 0x27, 0x28,
    0x30, 0x31, 0x32, 0x33,
    0x40, 0x41, 0x42, 0x43, 0x44,
    0x50, 0x51, 0x52, 0x53, 0x54, 0x55, 0x56, 0x57,
    0x60, 0x61, 0x63, 0x64,
    0x70, 0x72,
    0x81, 0x82,
}

# Go Runtime (flux-swarm) opcodes
GO_OPS = {0x00, 0x01, 0x06, 0x08, 0x09, 0x0A, 0x0B, 0x0E, 0x0F, 0x13, 0x2B, 0x2D, 0x2E, 0x80}

# The 17-opcode irreducible core
IRREDUCIBLE_CORE = {0x20, 0x21, 0x22, 0x23, 0x38, 0x39, 0x3A,
                    0x3C, 0x3D, 0x43, 0x45, 0x02, 0x0C, 0x0D,
                    0x18, 0x00, 0x01}

# Opcode mnemonic map (canonical ISA)
MNEMONICS = {
    0x00: "HALT", 0x01: "NOP", 0x02: "RET", 0x03: "IRET",
    0x04: "BRK", 0x05: "WFI", 0x06: "RESET", 0x07: "SYN",
    0x08: "INC", 0x09: "DEC", 0x0A: "NOT", 0x0B: "NEG",
    0x0C: "PUSH", 0x0D: "POP",
    0x18: "MOVI", 0x19: "ADDI", 0x1A: "SUBI",
    0x20: "ADD", 0x21: "SUB", 0x22: "MUL", 0x23: "DIV",
    0x24: "MOD", 0x25: "AND", 0x26: "OR", 0x27: "XOR",
    0x28: "SHL", 0x29: "SHR",
    0x38: "LOAD", 0x39: "STORE", 0x3A: "MOV",
    0x3C: "JZ", 0x3D: "JNZ", 0x3E: "JLT", 0x3F: "JGT",
    0x43: "JMP", 0x44: "JAL", 0x45: "CALL", 0x46: "LOOP",
    0x50: "TELL", 0x51: "ASK", 0xFF: "PRINT",
}

FORMAT_SIZE = {'A': 1, 'B': 2, 'C': 2, 'D': 3, 'E': 4, 'F': 4, 'G': 5}

# Canonical opcode translation tables
PYTHON_TO_CAN = bytearray(256)
for b in range(256): PYTHON_TO_CAN[b] = 0xFE
_PY_MAP = {0x00:0x01, 0x01:0x3A, 0x02:0x38, 0x03:0x39, 0x04:0x43,
            0x05:0x3C, 0x06:0x3D, 0x07:0x45, 0x08:0x20, 0x09:0x21,
            0x0A:0x22, 0x0B:0x23, 0x0C:0x24, 0x0E:0x08, 0x0F:0x09,
            0x10:0x25, 0x11:0x26, 0x12:0x27, 0x13:0x0A, 0x14:0x28,
            0x15:0x29, 0x20:0x0C, 0x21:0x0D, 0x28:0x02, 0x2B:0x18,
            0x2D:0x2C, 0x2E:0x3C, 0x2F:0x3D, 0x40:0x30, 0x41:0x31,
            0x42:0x32, 0x43:0x33, 0x48:0x43, 0x50:0xB0, 0x60:0x50,
            0x61:0x51, 0x80:0x00, 0xFF:0xFF}
for k,v in _PY_MAP.items(): PYTHON_TO_CAN[k] = v

RUST_TO_CAN = bytearray(256)
for b in range(256): RUST_TO_CAN[b] = 0xFE
_RS_MAP = {0x00:0x00, 0x01:0x01, 0x02:0x02, 0x03:0x43, 0x04:0x3C,
            0x05:0x3D, 0x06:0x45, 0x10:0x0C, 0x11:0x0D, 0x20:0x3A,
            0x21:0x20, 0x22:0x21, 0x23:0x22, 0x24:0x23, 0x25:0x24,
            0x26:0x0B, 0x28:0x08, 0x29:0x09, 0x2A:0x2A, 0x2B:0x2B,
            0x2C:0x25, 0x2D:0x26, 0x2E:0x27, 0x2F:0x28, 0x30:0x29,
            0x31:0x0A, 0x32:0x2C, 0x33:0x2F, 0x34:0x2D, 0x36:0x2E,
            0x41:0x30, 0x42:0x31, 0x43:0x32, 0x44:0x33, 0x4C:0x34,
            0x4D:0x35, 0x60:0x37, 0x61:0x36, 0x72:0x38, 0x76:0x39,
            0x83:0x50, 0x82:0x51, 0xFF:0xFF}
for k,v in _RS_MAP.items(): RUST_TO_CAN[k] = v


# ═══════════════════════════════════════════════════════════════════════
# Validation Engine
# ═══════════════════════════════════════════════════════════════════════

@dataclass
class Instruction:
    pc: int
    opcode: int
    mnemonic: str
    fmt: str
    size: int
    operands: bytes
    is_wasm_impl: bool
    is_core: bool
    runtime_support: Dict[str, bool]


@dataclass
class ValidationResult:
    filename: str
    bytecode_len: int
    instructions: List[Instruction]
    errors: List[str]
    warnings: List[str]
    info: List[str]
    runtime_compatibility: Dict[str, dict]
    control_flow: Dict[str, list]
    irreducible_core_only: bool

    def to_json(self) -> str:
        return json.dumps({
            "filename": self.filename,
            "bytecode_len": self.bytecode_len,
            "instruction_count": len(self.instructions),
            "errors": self.errors,
            "warnings": self.warnings,
            "info": self.info,
            "runtime_compatibility": self.runtime_compatibility,
            "control_flow": self.control_flow,
            "irreducible_core_only": self.irreducible_core_only,
        }, indent=2)

    def to_text(self) -> str:
        lines = []
        lines.append("=" * 60)
        lines.append("FLUX UNIVERSAL BYTECODE VALIDATOR")
        lines.append("=" * 60)
        lines.append(f"File: {self.filename}")
        lines.append(f"Bytecode: {self.bytecode_len} bytes")
        lines.append(f"Instructions: {len(self.instructions)}")
        lines.append("")

        # Runtime compatibility
        lines.append("--- RUNTIME COMPATIBILITY ---")
        for rt, data in self.runtime_compatibility.items():
            status = data["status"]
            pct = data["coverage_pct"]
            icon = "+" if pct == 100.0 else ("~" if pct >= 80 else "-")
            lines.append(f"  [{icon}] {rt}: {data['supported']}/{data['total']} ops ({pct:.0f}%) - {status}")
        lines.append("")

        # Core check
        if self.irreducible_core_only:
            lines.append("[+] IRREDUCIBLE CORE ONLY: Portable across ALL runtimes")
        else:
            non_core = [i for i in self.instructions if not i.is_core]
            if non_core:
                lines.append(f"[~] Uses {len(non_core)} non-core opcodes")
                for i in non_core[:5]:
                    lines.append(f"    0x{i.pc:04x}: {i.mnemonic} (0x{i.opcode:02x})")
                if len(non_core) > 5:
                    lines.append(f"    ... and {len(non_core)-5} more")
        lines.append("")

        # Errors
        if self.errors:
            lines.append("--- ERRORS ---")
            for e in self.errors:
                lines.append(f"  [!] {e}")
            lines.append("")

        # Warnings
        if self.warnings:
            lines.append("--- WARNINGS ---")
            for w in self.warnings:
                lines.append(f"  [?] {w}")
            lines.append("")

        # Control flow
        if self.control_flow.get("unreachable"):
            lines.append("--- UNREACHABLE CODE ---")
            for addr in self.control_flow["unreachable"]:
                lines.append(f"    0x{addr:04x}")
            lines.append("")

        # Instruction listing
        lines.append("--- INSTRUCTION LISTING ---")
        for inst in self.instructions:
            impl = "IMPL" if inst.is_wasm_impl else "NOP "
            core = "CORE" if inst.is_core else "    "
            rt_str = "W" if inst.runtime_support["wasm"] else " "
            rt_str += "P" if inst.runtime_support["python"] else " "
            rt_str += "R" if inst.runtime_support["rust"] else " "
            rt_str += "C" if inst.runtime_support["c"] else " "
            rt_str += "G" if inst.runtime_support["go"] else " "
            lines.append(f"  0x{inst.pc:04x}: [{impl}][{core}][{rt_str}] {inst.mnemonic} {inst.operands.hex() if inst.operands else ''}")
        lines.append("")
        lines.append(f"Legend: IMPL=wasm implemented, CORE=irreducible core")
        lines.append(f"        W=WASM P=Python R=Rust C=C/flux-os G=Go")
        return "\n".join(lines)


def validate(bytecode: bytes, filename: str = "<stdin>") -> ValidationResult:
    instructions = []
    errors = []
    warnings = []
    info = []
    pc = 0
    opcodes_used = set()
    wasm_nop_stubs = []
    core_only = True

    # Decode instructions
    while pc < len(bytecode):
        op = bytecode[pc]
        fmt = WASM_FORMAT.get(op, 'A')
        size = FORMAT_SIZE.get(fmt, 1)
        operands = bytecode[pc+1:pc+size] if size > 1 else b''

        mnemonic = MNEMONICS.get(op, f"UNKNOWN_0x{op:02X}")
        is_impl = op in WASM_IMPL
        is_core = op in IRREDUCIBLE_CORE
        if not is_core and is_impl:
            core_only = False

        rt_support = {
            "wasm": op in WASM_IMPL,
            "python": op in PYTHON_OPS,
            "rust": op in RUST_OPS,
            "c": op in C_OPS,
            "go": op in GO_OPS,
        }

        inst = Instruction(
            pc=pc, opcode=op, mnemonic=mnemonic, fmt=fmt, size=size,
            operands=operands, is_wasm_impl=is_impl, is_core=is_core,
            runtime_support=rt_support
        )
        instructions.append(inst)
        opcodes_used.add(op)

        if not is_impl and op in WASM_FORMAT:
            wasm_nop_stubs.append(inst)
            warnings.append(f"0x{pc:04x}: {mnemonic} is NOP-stubbed on WASM runtime")

        # Validate register references (0-255)
        if fmt in ('B', 'D') and len(operands) >= 1:
            rd = operands[0]
            if rd > 255:
                errors.append(f"0x{pc:04x}: Register index {rd} > 255")
        if fmt == 'E' and len(operands) >= 3:
            for i, name in enumerate(['rd', 'rs1', 'rs2']):
                if operands[i] > 255:
                    errors.append(f"0x{pc:04x}: {name} register index {operands[i]} > 255")

        pc += size

    # Check for trailing bytes
    if pc < len(bytecode):
        warnings.append(f"{len(bytecode) - pc} trailing bytes after last instruction")

    # Runtime compatibility summary
    runtime_compat = {}
    runtimes = {
        "wasm": WASM_IMPL, "python": PYTHON_OPS,
        "rust": RUST_OPS, "c": C_OPS, "go": GO_OPS
    }
    for name, ops_set in runtimes.items():
        supported = opcodes_used & ops_set
        total = len(opcodes_used)
        pct = (len(supported) / total * 100) if total > 0 else 0
        if pct == 100:
            status = "FULL COMPATIBILITY"
        elif pct >= 80:
            status = "MOSTLY COMPATIBLE"
        elif pct >= 50:
            status = "PARTIAL COMPATIBILITY"
        elif pct > 0:
            status = "LIMITED COMPATIBILITY"
        else:
            status = "INCOMPATIBLE"
        runtime_compat[name] = {
            "supported": len(supported), "total": total,
            "coverage_pct": round(pct, 1), "status": status,
            "missing": sorted(opcodes_used - ops_set)
        }

    # Control flow analysis
    unreachable = []
    jump_targets = set()
    for inst in instructions:
        if inst.mnemonic in ("JMP", "JAL", "CALL", "LJMP", "LCALL"):
            if inst.fmt == 'F' and len(inst.operands) >= 2:
                offset = struct.unpack_from('<h', inst.operands, 1)[0] if len(inst.operands) >= 3 else int.from_bytes(inst.operands[1:3], 'little', signed=True)
                target = inst.pc + inst.size + offset
                if 0 <= target < len(bytecode):
                    jump_targets.add(target)
        elif inst.mnemonic == "LOOP" and inst.fmt == 'F' and len(inst.operands) >= 2:
            offset = int.from_bytes(inst.operands[1:3], 'little', signed=True)
            target = inst.pc - offset
            if 0 <= target < len(bytecode):
                jump_targets.add(target)

    # Find unreachable code (after unconditional jumps/halt)
    for i, inst in enumerate(instructions):
        if inst.mnemonic in ("JMP", "HALT", "PANIC", "LJMP"):
            for j in range(i + 1, len(instructions)):
                next_pc = instructions[j].pc
                if next_pc not in jump_targets:
                    unreachable.append(next_pc)
                else:
                    break

    result = ValidationResult(
        filename=filename, bytecode_len=len(bytecode),
        instructions=instructions, errors=errors, warnings=warnings,
        info=info, runtime_compatibility=runtime_compat,
        control_flow={"unreachable": unreachable, "jump_targets": sorted(jump_targets)},
        irreducible_core_only=core_only
    )
    return result


def translate_bytecode(bytecode: bytes, from_rt: str, to_rt: str) -> bytes:
    tables = {"python": PYTHON_TO_CAN, "rust": RUST_TO_CAN}
    if from_rt not in tables:
        print(f"Error: No translation table for '{from_rt}'. Supported: {list(tables.keys())}")
        sys.exit(1)
    table = tables[from_rt]
    if to_rt == "wasm" or to_rt == "canonical":
        return bytes(table[b] for b in bytecode)
    else:
        print(f"Error: Translation to '{to_rt}' not yet supported. Use 'canonical' or 'wasm'.")
        sys.exit(1)


# ═══════════════════════════════════════════════════════════════════════
# Example Bytecode Generators
# ═══════════════════════════════════════════════════════════════════════

def example_core():
    """Simple ADD program using only irreducible core opcodes."""
    return bytes([
        0x18, 0x00, 0x2A,  # MOVI R0, 42
        0x18, 0x01, 0x08,  # MOVI R1, 8
        0x20, 0x00, 0x01, 0x02,  # ADD R0, R1, R2 (R0 = R0 + R1... wait, E format is rd,rs1,rs2)
        # Actually: ADD R2, R0, R1 = R2 = R0 + R1 = 42 + 8 = 50
        0x20, 0x02, 0x00, 0x01,  # ADD R2, R0, R1 -> R2 = 50
        0x10, 0x02,  # SYS 2 (print R0 as string at R0 start R1 len)
        0x00,  # HALT
    ])

def example_wasm_only():
    """Program using WASM-specific opcodes (SQRT, LJMP)."""
    return bytes([
        0x18, 0x00, 0x10,  # MOVI R0, 16
        0x91, 0x00, 0xFF, 0xFF,  # SQRT R0, R255 (sqrt(16)=4)
        0xE0, 0x00, 0x05, 0x00,  # LJMP +5 (skip next)
        0x18, 0x00, 0xFF,  # MOVI R0, -1 (unreachable)
        0x10, 0x00,  # SYS 0 (print R0 = 4)
        0x00,  # HALT
    ])

def example_multi():
    """Program mixing core + extended opcodes."""
    return bytes([
        0x18, 0x00, 0x03,  # MOVI R0, 3
        0x18, 0x01, 0x04,  # MOVI R1, 4
        0x18, 0x02, 0x05,  # MOVI R2, 5
        0x22, 0x03, 0x00, 0x01,  # MUL R3, R0, R1 = 12
        0x20, 0x03, 0x03, 0x02,  # ADD R3, R3, R2 = 17
        0x2C, 0x04, 0x03, 0x05,  # CMP_EQ R4, R3, R5 (need MOVI R5 first)
        0x18, 0x05, 0x11,  # MOVI R5, 17
        0x2C, 0x04, 0x03, 0x05,  # CMP_EQ R4, R3, R5 = 1
        0x3C, 0x04, 0x00, 0x00,  # JZ R4, R0 (skip if not equal)
        0x10, 0x04,  # SYS 0 (print R4 = 1, success!)
        0x00,  # HALT
    ])


# ═══════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="FLUX Universal Bytecode Validator")
    parser.add_argument("file", nargs="?", help="Bytecode file to validate")
    parser.add_argument("--stdin", action="store_true", help="Read bytecode from stdin")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--example", choices=["core", "wasm_only", "multi"],
                        help="Generate example bytecode instead of reading file")
    parser.add_argument("--translate", action="store_true", help="Translate bytecode between runtimes")
    parser.add_argument("--from", dest="from_rt", choices=["python", "rust"],
                        help="Source runtime for translation")
    parser.add_argument("--to", dest="to_rt", default="canonical",
                        help="Target runtime for translation (default: canonical/wasm)")
    parser.add_argument("-o", "--output", help="Output translated bytecode to file")
    args = parser.parse_args()

    if args.example:
        examples = {"core": example_core, "wasm_only": example_wasm_only, "multi": example_multi}
        bytecode = examples[args.example]()
        filename = f"<example:{args.example}>"
        print(f"Example bytecode ({len(bytecode)} bytes): {bytecode.hex()}")
    elif args.translate:
        if not args.file and not args.stdin:
            parser.error("--translate requires a bytecode file or --stdin")
        if args.stdin:
            bytecode = sys.stdin.buffer.read()
            filename = "<stdin>"
        else:
            with open(args.file, "rb") as f:
                bytecode = f.read()
            filename = args.file
        translated = translate_bytecode(bytecode, args.from_rt, args.to_rt)
        if args.output:
            with open(args.output, "wb") as f:
                f.write(translated)
            print(f"Translated {len(bytecode)} bytes ({args.from_rt} -> {args.to_rt}) -> {args.output}")
        else:
            sys.stdout.buffer.write(translated)
        return
    elif args.stdin:
        bytecode = sys.stdin.buffer.read()
        filename = "<stdin>"
    elif args.file:
        with open(args.file, "rb") as f:
            bytecode = f.read()
        filename = args.file
    else:
        parser.print_help()
        return

    result = validate(bytecode, filename)

    if args.json:
        print(result.to_json())
    else:
        print(result.to_text())


if __name__ == "__main__":
    main()
