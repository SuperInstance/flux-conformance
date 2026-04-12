"""Cross-Language Conformance Matrix for FLUX VM implementations.

Tracks which opcodes are implemented across Python, Go, C, and TypeScript VMs,
with format support, test coverage, and gap analysis.
"""

from __future__ import annotations

import csv
import io
import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

class Format(str, Enum):
    """FLUX instruction encoding formats."""
    A = "A"
    B = "B"
    C = "C"
    D = "D"
    E = "E"
    F = "F"
    G = "G"


class Category(str, Enum):
    """Opcode functional categories."""
    SYSTEM = "system"
    ARITHMETIC = "arithmetic"
    MEMORY = "memory"
    CONTROL = "control"
    A2A = "a2a"
    CONFIDENCE = "confidence"
    COLLECTION = "collection"
    CRYPTO = "crypto"
    EXTENDED = "extended"
    DEBUG = "debug"
    FLOAT = "float"
    BITWISE = "bitwise"
    COMPARE = "compare"
    SYNC = "sync"
    CONCURRENCY = "concurrency"
    AGENT = "agent"


@dataclass(frozen=True)
class OpcodeDef:
    """Definition of a single opcode."""
    code: int
    mnemonic: str
    format: Format
    category: Category
    description: str = ""


@dataclass
class ImplementationDef:
    """Metadata for a single VM implementation."""
    name: str
    language: str
    repo: str = ""
    version: str = "0.0.0"
    opcode_codes: set[int] = field(default_factory=set)
    supported_formats: set[Format] = field(default_factory=set)
    supported_categories: set[Category] = field(default_factory=set)


@dataclass(frozen=True)
class TestCoverageEntry:
    """Record that a specific opcode is tested in a specific implementation."""
    implementation_name: str
    opcode_code: int
    test_file: str = ""
    test_function: str = ""
    passed: bool = True


# ---------------------------------------------------------------------------
# Seed data: Python VM (flux-runtime) — full ISA
# ---------------------------------------------------------------------------

def _build_python_opcodes() -> list[OpcodeDef]:
    """Build the full ~200 opcode table for the Python reference VM."""
    ops: list[OpcodeDef] = []

    # 0x00-0x03: System basics (Format A)
    ops += [
        OpcodeDef(0x00, "HALT",    Format.A, Category.SYSTEM,     "Halt execution"),
        OpcodeDef(0x01, "NOP",     Format.A, Category.SYSTEM,     "No operation"),
        OpcodeDef(0x02, "RET",     Format.A, Category.SYSTEM,     "Return from subroutine"),
        OpcodeDef(0x03, "IRET",    Format.A, Category.SYSTEM,     "Interrupt return"),
    ]

    # 0x08-0x0F: Register manipulation (Format B)
    ops += [
        OpcodeDef(0x08, "INC",     Format.B, Category.ARITHMETIC,  "Increment register"),
        OpcodeDef(0x09, "DEC",     Format.B, Category.ARITHMETIC,  "Decrement register"),
        OpcodeDef(0x0A, "NOT",     Format.B, Category.BITWISE,     "Bitwise NOT"),
        OpcodeDef(0x0B, "NEG",     Format.B, Category.ARITHMETIC,  "Negate register"),
        OpcodeDef(0x0C, "PUSH",    Format.B, Category.MEMORY,      "Push register onto stack"),
        OpcodeDef(0x0D, "POP",     Format.B, Category.MEMORY,      "Pop stack into register"),
        OpcodeDef(0x0E, "CONF_LD", Format.B, Category.SYSTEM,      "Load configuration register"),
        OpcodeDef(0x0F, "CONF_ST", Format.B, Category.SYSTEM,      "Store configuration register"),
    ]

    # 0x10-0x17: System extensions (Format C)
    ops += [
        OpcodeDef(0x10, "SYS",      Format.C, Category.SYSTEM,      "System call"),
        OpcodeDef(0x11, "TRAP",     Format.C, Category.SYSTEM,      "Trap / exception"),
        OpcodeDef(0x12, "DBG",      Format.C, Category.DEBUG,       "Debug breakpoint"),
        OpcodeDef(0x13, "CLF",      Format.C, Category.SYSTEM,      "Clear flags"),
        OpcodeDef(0x14, "SEMA",     Format.C, Category.SYNC,        "Semaphore operation"),
        OpcodeDef(0x15, "YIELD",    Format.C, Category.CONCURRENCY, "Yield to scheduler"),
        OpcodeDef(0x16, "CACHE",    Format.C, Category.MEMORY,      "Cache hint"),
        OpcodeDef(0x17, "STRIPCF",  Format.C, Category.SYSTEM,      "Strip carry flag"),
    ]

    # 0x18-0x1F: Immediate arithmetic (Format D)
    ops += [
        OpcodeDef(0x18, "MOVI",  Format.D, Category.ARITHMETIC, "Move immediate"),
        OpcodeDef(0x19, "ADDI",  Format.D, Category.ARITHMETIC, "Add immediate"),
        OpcodeDef(0x1A, "SUBI",  Format.D, Category.ARITHMETIC, "Subtract immediate"),
        OpcodeDef(0x1B, "ANDI",  Format.D, Category.BITWISE,    "AND immediate"),
        OpcodeDef(0x1C, "ORI",   Format.D, Category.BITWISE,    "OR immediate"),
        OpcodeDef(0x1D, "XORI",  Format.D, Category.BITWISE,    "XOR immediate"),
        OpcodeDef(0x1E, "SHLI",  Format.D, Category.BITWISE,    "Shift left immediate"),
        OpcodeDef(0x1F, "SHRI",  Format.D, Category.BITWISE,    "Shift right immediate"),
    ]

    # 0x20-0x2F: Register arithmetic / compare (Format E)
    ops += [
        OpcodeDef(0x20, "ADD",     Format.E, Category.ARITHMETIC, "Add registers"),
        OpcodeDef(0x21, "SUB",     Format.E, Category.ARITHMETIC, "Subtract registers"),
        OpcodeDef(0x22, "MUL",     Format.E, Category.ARITHMETIC, "Multiply registers"),
        OpcodeDef(0x23, "DIV",     Format.E, Category.ARITHMETIC, "Divide registers"),
        OpcodeDef(0x24, "MOD",     Format.E, Category.ARITHMETIC, "Modulo registers"),
        OpcodeDef(0x25, "AND",     Format.E, Category.BITWISE,    "Bitwise AND"),
        OpcodeDef(0x26, "OR",      Format.E, Category.BITWISE,    "Bitwise OR"),
        OpcodeDef(0x27, "XOR",     Format.E, Category.BITWISE,    "Bitwise XOR"),
        OpcodeDef(0x28, "SHL",     Format.E, Category.BITWISE,    "Shift left"),
        OpcodeDef(0x29, "SHR",     Format.E, Category.BITWISE,    "Shift right"),
        OpcodeDef(0x2A, "MIN",     Format.E, Category.ARITHMETIC, "Minimum of two registers"),
        OpcodeDef(0x2B, "MAX",     Format.E, Category.ARITHMETIC, "Maximum of two registers"),
        OpcodeDef(0x2C, "CMP_EQ",  Format.E, Category.COMPARE,    "Compare equal"),
        OpcodeDef(0x2D, "CMP_LT",  Format.E, Category.COMPARE,    "Compare less-than"),
        OpcodeDef(0x2E, "CMP_GT",  Format.E, Category.COMPARE,    "Compare greater-than"),
        OpcodeDef(0x2F, "CMP_NE",  Format.E, Category.COMPARE,    "Compare not-equal"),
    ]

    # 0x30-0x3F: Float / memory / control (Format E)
    ops += [
        OpcodeDef(0x30, "FADD",  Format.E, Category.FLOAT,   "Float add"),
        OpcodeDef(0x31, "FSUB",  Format.E, Category.FLOAT,   "Float subtract"),
        OpcodeDef(0x32, "FMUL",  Format.E, Category.FLOAT,   "Float multiply"),
        OpcodeDef(0x33, "FDIV",  Format.E, Category.FLOAT,   "Float divide"),
        OpcodeDef(0x34, "FMIN",  Format.E, Category.FLOAT,   "Float minimum"),
        OpcodeDef(0x35, "FMAX",  Format.E, Category.FLOAT,   "Float maximum"),
        OpcodeDef(0x36, "FTOI",  Format.E, Category.FLOAT,   "Float to integer"),
        OpcodeDef(0x37, "ITOF",  Format.E, Category.FLOAT,   "Integer to float"),
        OpcodeDef(0x38, "LOAD",  Format.E, Category.MEMORY,  "Load from memory"),
        OpcodeDef(0x39, "STORE", Format.E, Category.MEMORY,  "Store to memory"),
        OpcodeDef(0x3A, "MOV",   Format.E, Category.MEMORY,  "Move between registers"),
        OpcodeDef(0x3B, "SWP",   Format.E, Category.MEMORY,  "Swap two registers"),
        OpcodeDef(0x3C, "JZ",    Format.E, Category.CONTROL, "Jump if zero"),
        OpcodeDef(0x3D, "JNZ",   Format.E, Category.CONTROL, "Jump if not zero"),
        OpcodeDef(0x3E, "JLT",   Format.E, Category.CONTROL, "Jump if less-than"),
        OpcodeDef(0x3F, "JGT",   Format.E, Category.CONTROL, "Jump if greater-than"),
    ]

    # 0x40-0x47: Control-flow extensions (Format F)
    ops += [
        OpcodeDef(0x40, "MOVI16", Format.F, Category.ARITHMETIC, "Move 16-bit immediate"),
        OpcodeDef(0x41, "ADDI16", Format.F, Category.ARITHMETIC, "Add 16-bit immediate"),
        OpcodeDef(0x42, "SUBI16", Format.F, Category.ARITHMETIC, "Subtract 16-bit immediate"),
        OpcodeDef(0x43, "JMP",    Format.F, Category.CONTROL,    "Unconditional jump"),
        OpcodeDef(0x44, "JAL",    Format.F, Category.CONTROL,    "Jump and link"),
        OpcodeDef(0x45, "CALL",   Format.F, Category.CONTROL,    "Call subroutine"),
        OpcodeDef(0x46, "LOOP",   Format.F, Category.CONTROL,    "Loop (decrement and branch)"),
        OpcodeDef(0x47, "SELECT", Format.F, Category.CONTROL,    "Conditional select"),
    ]

    # 0x48-0x4F: Memory / stack extensions (Format G)
    ops += [
        OpcodeDef(0x48, "LOADOFF",  Format.G, Category.MEMORY,  "Load with offset"),
        OpcodeDef(0x49, "STOREOFF", Format.G, Category.MEMORY,  "Store with offset"),
        OpcodeDef(0x4A, "LOADI",    Format.G, Category.MEMORY,  "Load indirect"),
        OpcodeDef(0x4B, "STOREI",   Format.G, Category.MEMORY,  "Store indirect"),
        OpcodeDef(0x4C, "ENTER",    Format.G, Category.CONTROL, "Enter stack frame"),
        OpcodeDef(0x4D, "LEAVE",    Format.G, Category.CONTROL, "Leave stack frame"),
        OpcodeDef(0x4E, "COPY",     Format.G, Category.MEMORY,  "Block copy"),
        OpcodeDef(0x4F, "FILL",     Format.G, Category.MEMORY,  "Block fill"),
    ]

    # 0x50-0x5F: Agent-to-agent (Format E)
    ops += [
        OpcodeDef(0x50, "TELL",    Format.E, Category.A2A,    "Send message"),
        OpcodeDef(0x51, "ASK",     Format.E, Category.A2A,    "Request response"),
        OpcodeDef(0x52, "DELEG",   Format.E, Category.A2A,    "Delegate task"),
        OpcodeDef(0x53, "BCAST",   Format.E, Category.A2A,    "Broadcast message"),
        OpcodeDef(0x54, "ACCEPT",  Format.E, Category.A2A,    "Accept request"),
        OpcodeDef(0x55, "DECLINE", Format.E, Category.A2A,    "Decline request"),
        OpcodeDef(0x56, "REPORT",  Format.E, Category.A2A,    "Report status"),
        OpcodeDef(0x57, "MERGE",   Format.E, Category.A2A,    "Merge results"),
        OpcodeDef(0x58, "FORK",    Format.E, Category.A2A,    "Fork agent"),
        OpcodeDef(0x59, "JOIN",    Format.E, Category.A2A,    "Join agents"),
        OpcodeDef(0x5A, "SIGNAL",  Format.E, Category.A2A,    "Signal event"),
        OpcodeDef(0x5B, "AWAIT",   Format.E, Category.A2A,    "Await event"),
        OpcodeDef(0x5C, "TRUST",   Format.E, Category.A2A,    "Trust metric"),
        OpcodeDef(0x5D, "DISCOV",  Format.E, Category.A2A,    "Discover agents"),
        OpcodeDef(0x5E, "STATUS",  Format.E, Category.A2A,    "Query status"),
        OpcodeDef(0x5F, "HEARTBT", Format.E, Category.A2A,    "Heartbeat"),
    ]

    # 0x60-0x6F: Confidence opcodes (Format E)
    _conf = [
        "C_ADD", "C_SUB", "C_MUL", "C_DIV", "C_AVG", "C_WAVG",
        "C_MAX", "C_MIN", "C_MEDIAN", "C_STDEV", "C_RANK",
        "C_VOTE", "C_CONSENSUS", "C_WEIGHT", "C_QUORUM", "C_SLATE",
    ]
    for i, name in enumerate(_conf):
        ops.append(OpcodeDef(0x60 + i, name, Format.E, Category.CONFIDENCE,
                             f"Confidence operation: {name}"))

    # 0x90-0x9F: Extended math (Format E)
    ops += [
        OpcodeDef(0x90, "ABS",     Format.E, Category.EXTENDED, "Absolute value"),
        OpcodeDef(0x91, "SIGN",    Format.E, Category.EXTENDED, "Signum"),
        OpcodeDef(0x92, "SQRT",    Format.E, Category.EXTENDED, "Integer square root"),
        OpcodeDef(0x93, "POW",     Format.E, Category.EXTENDED, "Power"),
        OpcodeDef(0x94, "LOG2",    Format.E, Category.EXTENDED, "Log base 2"),
        OpcodeDef(0x95, "CLZ",     Format.E, Category.BITWISE,   "Count leading zeros"),
        OpcodeDef(0x96, "CTZ",     Format.E, Category.BITWISE,   "Count trailing zeros"),
        OpcodeDef(0x97, "POPCNT",  Format.E, Category.BITWISE,   "Population count"),
        OpcodeDef(0x98, "CRC32",   Format.E, Category.EXTENDED, "CRC-32 checksum"),
        OpcodeDef(0x99, "SHA256",  Format.E, Category.CRYPTO,    "SHA-256 hash"),
        OpcodeDef(0x9A, "RND",     Format.E, Category.EXTENDED, "Random number"),
        OpcodeDef(0x9B, "SEED",    Format.E, Category.EXTENDED, "Seed RNG"),
        OpcodeDef(0x9C, "FMOD",    Format.E, Category.FLOAT,    "Float modulo"),
        OpcodeDef(0x9D, "FSQRT",   Format.E, Category.FLOAT,    "Float square root"),
        OpcodeDef(0x9E, "FSIN",    Format.E, Category.FLOAT,    "Float sine"),
        OpcodeDef(0x9F, "FCOS",    Format.E, Category.FLOAT,    "Float cosine"),
    ]

    # 0xA0-0xAF: Collection / crypto
    ops += [
        OpcodeDef(0xA0, "LEN",     Format.D, Category.COLLECTION, "Collection length"),
        OpcodeDef(0xA1, "CAP",     Format.D, Category.COLLECTION, "Collection capacity"),
        OpcodeDef(0xA2, "APPEND",  Format.E, Category.COLLECTION, "Append element"),
        OpcodeDef(0xA3, "REMOVE",  Format.E, Category.COLLECTION, "Remove element"),
        OpcodeDef(0xA4, "INDEX",   Format.E, Category.COLLECTION, "Index into collection"),
        OpcodeDef(0xA5, "SLICE",   Format.E, Category.COLLECTION, "Slice collection"),
        OpcodeDef(0xA6, "MAP",     Format.E, Category.COLLECTION, "Map over collection"),
        OpcodeDef(0xA7, "FILTER",  Format.E, Category.COLLECTION, "Filter collection"),
        OpcodeDef(0xA8, "REDUCE",  Format.E, Category.COLLECTION, "Reduce collection"),
        OpcodeDef(0xA9, "SORT",    Format.E, Category.COLLECTION, "Sort collection"),
        OpcodeDef(0xAA, "KEYGEN",  Format.G, Category.CRYPTO,    "Generate key pair"),
        OpcodeDef(0xAB, "SIGN_D",  Format.E, Category.CRYPTO,    "Digital sign"),
        OpcodeDef(0xAC, "VERIFY",  Format.E, Category.CRYPTO,    "Verify signature"),
        OpcodeDef(0xAD, "ENCRYPT", Format.E, Category.CRYPTO,    "Encrypt data"),
        OpcodeDef(0xAE, "DECRYPT", Format.E, Category.CRYPTO,    "Decrypt data"),
        OpcodeDef(0xAF, "HASH",    Format.E, Category.CRYPTO,    "Hash data"),
    ]

    # 0xF0-0xFF: Diagnostics (Format A)
    ops += [
        OpcodeDef(0xF0, "HALT_ERR", Format.A, Category.SYSTEM,  "Halt with error"),
        OpcodeDef(0xF1, "REBOOT",   Format.A, Category.SYSTEM,  "Reboot VM"),
        OpcodeDef(0xF2, "DUMP",     Format.A, Category.DEBUG,   "Dump state"),
        OpcodeDef(0xF3, "ASSERT",   Format.A, Category.DEBUG,   "Assert condition"),
        OpcodeDef(0xF4, "ID",       Format.A, Category.SYSTEM,  "VM identifier"),
        OpcodeDef(0xF5, "VER",      Format.A, Category.SYSTEM,  "Version query"),
        OpcodeDef(0xF6, "CLK",      Format.A, Category.SYSTEM,  "Clock cycles"),
        OpcodeDef(0xF7, "PCLK",     Format.A, Category.SYSTEM,  "Process clock"),
        OpcodeDef(0xF8, "WDOG",     Format.A, Category.SYSTEM,  "Watchdog reset"),
        OpcodeDef(0xF9, "SLEEP",    Format.A, Category.SYSTEM,  "Sleep N cycles"),
        OpcodeDef(0xFF, "ILLEGAL",  Format.A, Category.SYSTEM,  "Illegal instruction"),
    ]

    return ops


PYTHON_OPCODES = _build_python_opcodes()
PYTHON_OPCODE_MAP = {op.code: op for op in PYTHON_OPCODES}


# ---------------------------------------------------------------------------
# Seed data: Go VM (greenhorn-runtime)
# ---------------------------------------------------------------------------

def _build_go_opcodes() -> tuple[list[OpcodeDef], set[int], set[Format], set[Category]]:
    codes = {
        0x00, 0x01, 0x02, 0x03,          # HALT, NOP, RET, IRET
        0x08, 0x09, 0x0A, 0x0B,           # INC, DEC, NOT, NEG
        0x18, 0x19, 0x1A,                 # MOVI, ADDI, SUBI
        0x20, 0x21, 0x22, 0x23, 0x24,     # ADD, SUB, MUL, DIV, MOD
        0x2C, 0x2D, 0x2E,                 # CMP_EQ, CMP_LT, CMP_GT
        0x38, 0x39, 0x3A,                  # LOAD, STORE, MOV
        0x50, 0x51, 0x52,                  # TELL, ASK, DELEG
        0x53, 0x54, 0x55,                  # BCAST, ACCEPT, DECLINE
        0x56, 0x57, 0x58, 0x59,            # REPORT, MERGE, FORK, JOIN
        0x40, 0x43, 0x45,                  # MOVI16, JMP, CALL
    }
    ops = [PYTHON_OPCODE_MAP[c] for c in sorted(codes) if c in PYTHON_OPCODE_MAP]
    formats = {Format.A, Format.B, Format.D, Format.E, Format.G}
    categories = {Category.SYSTEM, Category.ARITHMETIC, Category.MEMORY, Category.A2A}
    return ops, codes, formats, categories


# ---------------------------------------------------------------------------
# Seed data: C VM (flux-runtime-c)
# ---------------------------------------------------------------------------

def _build_c_opcodes() -> tuple[list[OpcodeDef], set[int], set[Format], set[Category]]:
    codes = {
        0x00, 0x01, 0x02, 0x03,          # HALT, NOP, RET, IRET
        0x08, 0x09, 0x0A, 0x0B,           # INC, DEC, NOT, NEG
        0x0C, 0x0D,                        # PUSH, POP
        0x18, 0x19, 0x1A, 0x1B, 0x1C,     # MOVI, ADDI, SUBI, ANDI, ORI
        0x20, 0x21, 0x22, 0x23, 0x24,     # ADD, SUB, MUL, DIV, MOD
        0x25, 0x26, 0x27,                  # AND, OR, XOR
        0x28, 0x29,                        # SHL, SHR
        0x2C, 0x2D, 0x2E, 0x2F,           # CMP_EQ, CMP_LT, CMP_GT, CMP_NE
        0x38, 0x39, 0x3A, 0x3B,           # LOAD, STORE, MOV, SWP
        0x3C, 0x3D, 0x3E, 0x3F,           # JZ, JNZ, JLT, JGT
        0x30, 0x31,                        # FADD, FSUB
        0x36, 0x37,                        # FTOI, ITOF
    }
    ops = [PYTHON_OPCODE_MAP[c] for c in sorted(codes) if c in PYTHON_OPCODE_MAP]
    formats = {Format.A, Format.B, Format.D, Format.E}
    categories = {Category.SYSTEM, Category.ARITHMETIC, Category.MEMORY, Category.CONTROL}
    return ops, codes, formats, categories


# ---------------------------------------------------------------------------
# Seed data: TypeScript VM (flux-vm-ts)
# ---------------------------------------------------------------------------

def _build_ts_opcodes() -> tuple[list[OpcodeDef], set[int], set[Format], set[Category]]:
    codes = {
        0x00, 0x01, 0x02, 0x03,          # HALT, NOP, RET, IRET
        0x08, 0x09,                        # INC, DEC
        0x18, 0x19,                        # MOVI, ADDI
        0x20, 0x21, 0x22, 0x23,           # ADD, SUB, MUL, DIV
        0x2C, 0x2D, 0x2E,                 # CMP_EQ, CMP_LT, CMP_GT
        0x38, 0x39, 0x3A,                 # LOAD, STORE, MOV
        0x3C, 0x3D,                        # JZ, JNZ
        0x40, 0x43, 0x45,                  # MOVI16, JMP, CALL
        0x30,                              # FADD
        0x0A, 0x0B, 0x0C, 0x0D,           # NOT, NEG, PUSH, POP
        0x1A, 0x1B,                        # SUBI, ANDI
    }
    ops = [PYTHON_OPCODE_MAP[c] for c in sorted(codes) if c in PYTHON_OPCODE_MAP]
    formats = {Format.A, Format.B, Format.D, Format.E}
    categories = {Category.SYSTEM, Category.ARITHMETIC, Category.MEMORY, Category.CONTROL}
    return ops, codes, formats, categories


# ---------------------------------------------------------------------------
# 1. Implementation Registry
# ---------------------------------------------------------------------------

class ImplementationRegistry:
    """Registry of all known VM implementations."""

    def __init__(self) -> None:
        self._implementations: dict[str, ImplementationDef] = {}
        self._opcode_table: dict[int, OpcodeDef] = dict(PYTHON_OPCODE_MAP)
        self._coverage: list[TestCoverageEntry] = []

    # -- registration --------------------------------------------------------

    def register(self, impl: ImplementationDef) -> None:
        """Register a VM implementation."""
        if impl.name in self._implementations:
            raise ValueError(f"Implementation '{impl.name}' already registered")
        self._implementations[impl.name] = impl

    def register_coverage(self, entry: TestCoverageEntry) -> None:
        """Register a test coverage record."""
        self._coverage.append(entry)

    def register_coverage_batch(self, entries: list[TestCoverageEntry]) -> None:
        """Register multiple test coverage records."""
        self._coverage.extend(entries)

    # -- queries -------------------------------------------------------------

    @property
    def implementations(self) -> dict[str, ImplementationDef]:
        return dict(self._implementations)

    @property
    def implementation_names(self) -> list[str]:
        return list(self._implementations.keys())

    @property
    def opcode_table(self) -> dict[int, OpcodeDef]:
        return dict(self._opcode_table)

    @property
    def coverage(self) -> list[TestCoverageEntry]:
        return list(self._coverage)

    def get(self, name: str) -> ImplementationDef | None:
        return self._implementations.get(name)

    def get_opcode(self, code: int) -> OpcodeDef | None:
        return self._opcode_table.get(code)

    @property
    def total_opcodes(self) -> int:
        return len(self._opcode_table)

    def opcodes_by_category(self, category: Category) -> list[OpcodeDef]:
        return [op for op in self._opcode_table.values() if op.category == category]

    def opcodes_by_format(self, fmt: Format) -> list[OpcodeDef]:
        return [op for op in self._opcode_table.values() if op.format == fmt]

    @staticmethod
    def seed_default() -> "ImplementationRegistry":
        """Create a registry pre-populated with all 4 VM implementations."""
        reg = ImplementationRegistry()

        # Python VM — full ISA
        py_codes = set(op.code for op in PYTHON_OPCODES)
        py_formats = {f for f in Format}
        py_categories = {c for c in Category}
        reg.register(ImplementationDef(
            name="flux-runtime",
            language="Python",
            repo="github.com/flux-lang/flux-runtime",
            version="2.1.0",
            opcode_codes=py_codes,
            supported_formats=py_formats,
            supported_categories=py_categories,
        ))

        # Go VM
        go_ops, go_codes, go_fmts, go_cats = _build_go_opcodes()
        reg.register(ImplementationDef(
            name="greenhorn-runtime",
            language="Go",
            repo="github.com/flux-lang/greenhorn-runtime",
            version="0.4.0",
            opcode_codes=go_codes,
            supported_formats=go_fmts,
            supported_categories=go_cats,
        ))

        # C VM
        c_ops, c_codes, c_fmts, c_cats = _build_c_opcodes()
        reg.register(ImplementationDef(
            name="flux-runtime-c",
            language="C",
            repo="github.com/flux-lang/flux-runtime-c",
            version="0.3.0",
            opcode_codes=c_codes,
            supported_formats=c_fmts,
            supported_categories=c_cats,
        ))

        # TypeScript VM
        ts_ops, ts_codes, ts_fmts, ts_cats = _build_ts_opcodes()
        reg.register(ImplementationDef(
            name="flux-vm-ts",
            language="TypeScript",
            repo="github.com/flux-lang/flux-vm-ts",
            version="0.2.0",
            opcode_codes=ts_codes,
            supported_formats=ts_fmts,
            supported_categories=ts_cats,
        ))

        # Seed some test coverage
        _seed_default_coverage(reg)
        return reg


def _seed_default_coverage(reg: ImplementationRegistry) -> None:
    """Seed realistic test coverage for all implementations."""
    entries: list[TestCoverageEntry] = []

    # Python — comprehensive coverage (95%+)
    for op in PYTHON_OPCODES:
        if op.code not in (0xFF, 0xF0, 0xF8, 0x17, 0x13):
            entries.append(TestCoverageEntry(
                implementation_name="flux-runtime",
                opcode_code=op.code,
                test_file="tests/test_opcodes.py",
                test_function=f"test_{op.mnemonic.lower()}",
                passed=True,
            ))

    # Go — partial coverage
    go_tested = {0x00, 0x01, 0x02, 0x20, 0x21, 0x22, 0x23, 0x38, 0x39, 0x3A, 0x50, 0x51}
    for code in go_tested:
        op = PYTHON_OPCODE_MAP.get(code)
        if op:
            entries.append(TestCoverageEntry(
                implementation_name="greenhorn-runtime",
                opcode_code=code,
                test_file="greenhorn_test.go",
                test_function=f"Test{op.mnemonic}",
                passed=True,
            ))

    # C — moderate coverage
    c_tested = {0x00, 0x01, 0x02, 0x03, 0x20, 0x21, 0x22, 0x23, 0x24,
                0x38, 0x39, 0x3A, 0x3C, 0x3D, 0x3E, 0x3F, 0x30, 0x31, 0x36}
    for code in c_tested:
        op = PYTHON_OPCODE_MAP.get(code)
        if op:
            entries.append(TestCoverageEntry(
                implementation_name="flux-runtime-c",
                opcode_code=code,
                test_file="tests/test_vm.c",
                test_function=f"test_{op.mnemonic.lower()}",
                passed=True,
            ))

    # TypeScript — basic coverage
    ts_tested = {0x00, 0x01, 0x20, 0x21, 0x22, 0x38, 0x39}
    for code in ts_tested:
        op = PYTHON_OPCODE_MAP.get(code)
        if op:
            entries.append(TestCoverageEntry(
                implementation_name="flux-vm-ts",
                opcode_code=code,
                test_file="tests/vm.test.ts",
                test_function=f"test_{op.mnemonic.lower()}",
                passed=True,
            ))

    # A couple of failing tests for realism
    entries.append(TestCoverageEntry(
        implementation_name="flux-runtime-c",
        opcode_code=0x37,
        test_file="tests/test_vm.c",
        test_function="test_itof_edge",
        passed=False,
    ))
    entries.append(TestCoverageEntry(
        implementation_name="flux-vm-ts",
        opcode_code=0x30,
        test_file="tests/vm.test.ts",
        test_function="test_fadd_nan",
        passed=False,
    ))

    reg.register_coverage_batch(entries)


# ---------------------------------------------------------------------------
# 2. Conformance Matrix
# ---------------------------------------------------------------------------

class ConformanceMatrix:
    """N×M matrix of opcodes × implementations."""

    def __init__(self, registry: ImplementationRegistry) -> None:
        self._reg = registry

    def build(self) -> dict[str, dict[int, bool]]:
        """Build a matrix: {impl_name: {opcode_code: implemented}}."""
        matrix: dict[str, dict[int, bool]] = {}
        for name, impl in self._reg.implementations.items():
            matrix[name] = {}
            for code in self._reg.opcode_table:
                matrix[name][code] = code in impl.opcode_codes
        return matrix

    def build_detailed(self) -> dict[str, dict[int, dict[str, Any]]]:
        """Build a detailed matrix with opcode metadata."""
        matrix: dict[str, dict[int, dict[str, Any]]] = {}
        for name, impl in self._reg.implementations.items():
            matrix[name] = {}
            for code, op in self._reg.opcode_table.items():
                matrix[name][code] = {
                    "implemented": code in impl.opcode_codes,
                    "mnemonic": op.mnemonic,
                    "format": op.format.value,
                    "category": op.category.value,
                    "description": op.description,
                }
        return matrix

    def filter_by_category(self, category: Category) -> dict[str, dict[int, bool]]:
        """Build matrix filtered to a specific category."""
        opcodes = self._reg.opcodes_by_category(category)
        codes = {op.code for op in opcodes}
        matrix: dict[str, dict[int, bool]] = {}
        for name, impl in self._reg.implementations.items():
            matrix[name] = {c: c in impl.opcode_codes for c in sorted(codes)}
        return matrix

    def filter_by_format(self, fmt: Format) -> dict[str, dict[int, bool]]:
        """Build matrix filtered to a specific format."""
        opcodes = self._reg.opcodes_by_format(fmt)
        codes = {op.code for op in opcodes}
        matrix: dict[str, dict[int, bool]] = {}
        for name, impl in self._reg.implementations.items():
            matrix[name] = {c: c in impl.opcode_codes for c in sorted(codes)}
        return matrix

    def get_implemented_count(self, impl_name: str) -> int:
        """Get the number of opcodes implemented by a specific implementation."""
        impl = self._reg.get(impl_name)
        if impl is None:
            raise KeyError(f"Unknown implementation: {impl_name}")
        return len(impl.opcode_codes & set(self._reg.opcode_table.keys()))

    def get_missing_opcodes(self, impl_name: str) -> list[OpcodeDef]:
        """Get opcodes NOT implemented by a specific implementation."""
        impl = self._reg.get(impl_name)
        if impl is None:
            raise KeyError(f"Unknown implementation: {impl_name}")
        return [
            op for code, op in self._reg.opcode_table.items()
            if code not in impl.opcode_codes
        ]

    def cross_implementation_opcodes(self) -> set[int]:
        """Get opcodes implemented by ALL implementations."""
        if not self._reg.implementations:
            return set()
        all_codes = [impl.opcode_codes & set(self._reg.opcode_table.keys())
                     for impl in self._reg.implementations.values()]
        result = all_codes[0]
        for s in all_codes[1:]:
            result &= s
        return result

    def unique_opcodes(self, impl_name: str) -> set[int]:
        """Get opcodes unique to a specific implementation (not in any other)."""
        impl = self._reg.get(impl_name)
        if impl is None:
            raise KeyError(f"Unknown implementation: {impl_name}")
        my_codes = impl.opcode_codes & set(self._reg.opcode_table.keys())
        others_codes: set[int] = set()
        for name, other in self._reg.implementations.items():
            if name != impl_name:
                others_codes |= other.opcode_codes
        return my_codes - others_codes


# ---------------------------------------------------------------------------
# 3. Coverage Analyzer
# ---------------------------------------------------------------------------

class CoverageAnalyzer:
    """Analyze test coverage across implementations."""

    def __init__(self, registry: ImplementationRegistry) -> None:
        self._reg = registry

    def coverage_by_implementation(self) -> dict[str, dict[str, Any]]:
        """Get coverage stats per implementation."""
        result: dict[str, dict[str, Any]] = {}
        for name, impl in self._reg.implementations.items():
            impl_coverage = [
                e for e in self._reg.coverage if e.implementation_name == name
            ]
            tested_codes = {e.opcode_code for e in impl_coverage}
            passing_codes = {e.opcode_code for e in impl_coverage if e.passed}
            failing_codes = {e.opcode_code for e in impl_coverage if not e.passed}

            implemented = impl.opcode_codes & set(self._reg.opcode_table.keys())

            result[name] = {
                "total_tests": len(impl_coverage),
                "passed": len(passing_codes),
                "failed": len(failing_codes),
                "tested_opcodes": len(tested_codes),
                "implemented_opcodes": len(implemented),
                "coverage_rate": len(tested_codes) / len(implemented) if implemented else 0.0,
                "pass_rate": len(passing_codes) / len(impl_coverage) if impl_coverage else 0.0,
            }
        return result

    def coverage_for_opcode(self, opcode_code: int) -> dict[str, bool]:
        """Check which implementations have test coverage for a specific opcode."""
        result: dict[str, bool] = {}
        for name in self._reg.implementation_names:
            covered = any(
                e.opcode_code == opcode_code
                for e in self._reg.coverage
                if e.implementation_name == name
            )
            result[name] = covered
        return result

    def untested_opcodes(self, impl_name: str) -> list[OpcodeDef]:
        """Get implemented but untested opcodes for an implementation."""
        impl = self._reg.get(impl_name)
        if impl is None:
            raise KeyError(f"Unknown implementation: {impl_name}")
        tested_codes = {
            e.opcode_code for e in self._reg.coverage
            if e.implementation_name == impl_name
        }
        implemented = impl.opcode_codes & set(self._reg.opcode_table.keys())
        untested = implemented - tested_codes
        return [self._reg.opcode_table[c] for c in sorted(untested) if c in self._reg.opcode_table]

    def failing_tests(self, impl_name: str) -> list[TestCoverageEntry]:
        """Get all failing test entries for an implementation."""
        return [
            e for e in self._reg.coverage
            if e.implementation_name == impl_name and not e.passed
        ]

    def overall_coverage_summary(self) -> dict[str, Any]:
        """Get a high-level coverage summary across all implementations."""
        stats = self.coverage_by_implementation()
        total_impl = len(stats)
        if total_impl == 0:
            return {"implementations": 0}

        avg_coverage = sum(s["coverage_rate"] for s in stats.values()) / total_impl
        avg_pass = sum(s["pass_rate"] for s in stats.values()) / total_impl

        return {
            "implementations": total_impl,
            "avg_coverage_rate": round(avg_coverage, 4),
            "avg_pass_rate": round(avg_pass, 4),
            "per_implementation": stats,
        }

    def fully_covered_opcodes(self) -> set[int]:
        """Get opcodes that have test coverage in ALL implementations that implement them."""
        result: set[int] = set()
        for code, op in self._reg.opcode_table.items():
            impls_with_opcode = [
                name for name, impl in self._reg.implementations.items()
                if code in impl.opcode_codes
            ]
            if not impls_with_opcode:
                continue
            all_covered = all(
                any(e.opcode_code == code and e.implementation_name == name
                    for e in self._reg.coverage)
                for name in impls_with_opcode
            )
            if all_covered:
                result.add(code)
        return result


# ---------------------------------------------------------------------------
# 4. Gap Reporter
# ---------------------------------------------------------------------------

class GapReporter:
    """Identify gaps in opcode implementation and test coverage."""

    def __init__(self, registry: ImplementationRegistry) -> None:
        self._reg = registry
        self._matrix = ConformanceMatrix(registry)
        self._coverage = CoverageAnalyzer(registry)

    def implementation_gaps(self, impl_name: str) -> dict[str, Any]:
        """Report all gaps for a specific implementation."""
        impl = self._reg.get(impl_name)
        if impl is None:
            raise KeyError(f"Unknown implementation: {impl_name}")

        missing_ops = self._matrix.get_missing_opcodes(impl_name)
        missing_by_category: dict[str, list[str]] = {}
        for op in missing_ops:
            cat = op.category.value
            missing_by_category.setdefault(cat, []).append(op.mnemonic)

        untested = self._coverage.untested_opcodes(impl_name)
        failing = self._coverage.failing_tests(impl_name)

        missing_formats = set(Format) - impl.supported_formats
        missing_categories = set(Category) - impl.supported_categories

        return {
            "implementation": impl_name,
            "language": impl.language,
            "total_opcodes_in_isa": self._reg.total_opcodes,
            "implemented": len(impl.opcode_codes),
            "missing_count": len(missing_ops),
            "missing_opcodes": [op.mnemonic for op in missing_ops],
            "missing_by_category": missing_by_category,
            "untested_opcodes": [op.mnemonic for op in untested],
            "failing_opcodes": [self._reg.get_opcode(e.opcode_code).mnemonic
                                if self._reg.get_opcode(e.opcode_code) else f"0x{e.opcode_code:02x}"
                                for e in failing],
            "missing_formats": [f.value for f in sorted(missing_formats)],
            "missing_categories": [c.value for c in sorted(missing_categories)],
        }

    def category_gaps(self) -> dict[str, dict[str, Any]]:
        """Report implementation gaps by category."""
        result: dict[str, dict[str, Any]] = {}
        for cat in Category:
            cat_opcodes = self._reg.opcodes_by_category(cat)
            if not cat_opcodes:
                continue
            cat_name = cat.value
            per_impl: dict[str, dict[str, Any]] = {}
            for name, impl in self._reg.implementations.items():
                impl_codes = impl.opcode_codes & {op.code for op in cat_opcodes}
                total = len(cat_opcodes)
                implemented = len(impl_codes)
                per_impl[name] = {
                    "implemented": implemented,
                    "total": total,
                    "rate": implemented / total if total else 0.0,
                    "missing": [op.mnemonic for op in cat_opcodes if op.code not in impl_codes],
                }
            result[cat_name] = per_impl
        return result

    def format_gaps(self) -> dict[str, dict[str, Any]]:
        """Report format support gaps."""
        result: dict[str, dict[str, Any]] = {}
        for fmt in Format:
            fmt_name = fmt.value
            per_impl: dict[str, bool] = {}
            for name, impl in self._reg.implementations.items():
                per_impl[name] = fmt in impl.supported_formats
            result[fmt_name] = per_impl
        return result

    def cross_implementation_summary(self) -> dict[str, Any]:
        """Generate a cross-implementation gap summary."""
        all_codes = set(self._reg.opcode_table.keys())
        common = self._matrix.cross_implementation_opcodes()

        per_impl: dict[str, dict[str, Any]] = {}
        for name in self._reg.implementation_names:
            gaps = self.implementation_gaps(name)
            per_impl[name] = {
                "implemented": gaps["implemented"],
                "missing_count": gaps["missing_count"],
                "untested_count": len(gaps["untested_opcodes"]),
                "failing_count": len(gaps["failing_opcodes"]),
            }

        return {
            "isa_size": len(all_codes),
            "common_opcodes": len(common),
            "common_opcode_names": [
                self._reg.opcode_table[c].mnemonic for c in sorted(common)
                if c in self._reg.opcode_table
            ],
            "per_implementation": per_impl,
        }

    def priority_gaps(self, top_n: int = 10) -> list[dict[str, Any]]:
        """Return gaps prioritized by number of implementations missing an opcode."""
        all_codes = set(self._reg.opcode_table.keys())
        gap_list: list[dict[str, Any]] = []

        for code in sorted(all_codes):
            op = self._reg.opcode_table[code]
            impl_count = sum(
                1 for impl in self._reg.implementations.values()
                if code in impl.opcode_codes
            )
            if impl_count < len(self._reg.implementations):
                gap_list.append({
                    "opcode": op.mnemonic,
                    "code": f"0x{code:02X}",
                    "format": op.format.value,
                    "category": op.category.value,
                    "implemented_in": impl_count,
                    "missing_from": len(self._reg.implementations) - impl_count,
                    "implementations": [
                        name for name, impl in self._reg.implementations.items()
                        if code in impl.opcode_codes
                    ],
                })

        # Sort by missing_from descending (most critical first)
        gap_list.sort(key=lambda x: x["missing_from"], reverse=True)
        return gap_list[:top_n]


# ---------------------------------------------------------------------------
# 5. Conformance Score
# ---------------------------------------------------------------------------

class ConformanceScore:
    """Compute 0.0-1.0 conformance scores for implementations."""

    def __init__(self, registry: ImplementationRegistry) -> None:
        self._reg = registry
        self._matrix = ConformanceMatrix(registry)
        self._coverage_analyzer = CoverageAnalyzer(registry)

    def isa_coverage_score(self, impl_name: str) -> float:
        """0.0-1.0 score: fraction of ISA opcodes implemented."""
        total = self._reg.total_opcodes
        if total == 0:
            return 0.0
        implemented = self._matrix.get_implemented_count(impl_name)
        return round(implemented / total, 4)

    def category_coverage_score(self, impl_name: str) -> float:
        """0.0-1.0 score: fraction of categories that have at least one opcode."""
        impl = self._reg.get(impl_name)
        if impl is None:
            raise KeyError(f"Unknown implementation: {impl_name}")
        all_cats = {op.category for op in self._reg.opcode_table.values()}
        if not all_cats:
            return 0.0
        covered_cats = all_cats & impl.supported_categories
        return round(len(covered_cats) / len(all_cats), 4)

    def format_coverage_score(self, impl_name: str) -> float:
        """0.0-1.0 score: fraction of formats supported."""
        impl = self._reg.get(impl_name)
        if impl is None:
            raise KeyError(f"Unknown implementation: {impl_name}")
        all_formats = {op.format for op in self._reg.opcode_table.values()}
        if not all_formats:
            return 0.0
        covered = all_formats & impl.supported_formats
        return round(len(covered) / len(all_formats), 4)

    def test_coverage_score(self, impl_name: str) -> float:
        """0.0-1.0 score: fraction of implemented opcodes that are tested."""
        stats = self._coverage_analyzer.coverage_by_implementation()
        if impl_name not in stats:
            raise KeyError(f"Unknown implementation: {impl_name}")
        return round(stats[impl_name]["coverage_rate"], 4)

    def composite_score(self, impl_name: str) -> dict[str, float]:
        """Composite conformance score with weighted components."""
        isa = self.isa_coverage_score(impl_name)
        cat = self.category_coverage_score(impl_name)
        fmt = self.format_coverage_score(impl_name)
        test = self.test_coverage_score(impl_name)

        # Weighted composite: ISA is most important
        composite = round(0.40 * isa + 0.20 * cat + 0.15 * fmt + 0.25 * test, 4)

        return {
            "isa_coverage": isa,
            "category_coverage": cat,
            "format_coverage": fmt,
            "test_coverage": test,
            "composite": composite,
        }

    def ranking(self) -> list[tuple[str, float]]:
        """Rank all implementations by composite score (descending)."""
        scores = []
        for name in self._reg.implementation_names:
            comp = self.composite_score(name)
            scores.append((name, comp["composite"]))
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores

    def format_support_matrix(self) -> dict[str, dict[str, bool]]:
        """Matrix of which implementations support which formats."""
        result: dict[str, dict[str, bool]] = {}
        for fmt in sorted(Format, key=lambda f: f.value):
            result[fmt.value] = {}
            for name, impl in self._reg.implementations.items():
                result[fmt.value][name] = fmt in impl.supported_formats
        return result


# ---------------------------------------------------------------------------
# 6. Matrix Exporter
# ---------------------------------------------------------------------------

class MatrixExporter:
    """Export conformance matrix in various formats."""

    def __init__(self, registry: ImplementationRegistry) -> None:
        self._reg = registry
        self._matrix = ConformanceMatrix(registry)
        self._scores = ConformanceScore(registry)
        self._gaps = GapReporter(registry)
        self._coverage = CoverageAnalyzer(registry)

    def to_markdown(self) -> str:
        """Export full conformance matrix as Markdown table."""
        lines: list[str] = []
        lines.append("# FLUX VM Cross-Language Conformance Matrix")
        lines.append("")
        lines.append(f"**ISA Size:** {self._reg.total_opcodes} opcodes")
        lines.append(f"**Implementations:** {len(self._reg.implementations)}")
        lines.append("")

        # Conformance scores table
        lines.append("## Conformance Scores")
        lines.append("")
        header = "| Implementation | Language | ISA Coverage | Category | Format | Test | Composite |"
        sep = "|---|---|---|---|---|---|---|"
        lines.append(header)
        lines.append(sep)
        for name in self._reg.implementation_names:
            impl = self._reg.get(name)
            assert impl is not None
            scores = self._scores.composite_score(name)
            lines.append(
                f"| {name} | {impl.language} "
                f"| {scores['isa_coverage']:.1%} "
                f"| {scores['category_coverage']:.1%} "
                f"| {scores['format_coverage']:.1%} "
                f"| {scores['test_coverage']:.1%} "
                f"| {scores['composite']:.1%} |"
            )
        lines.append("")

        # Format support table
        lines.append("## Format Support")
        lines.append("")
        impl_names = self._reg.implementation_names
        fmt_header = "| Format | " + " | ".join(impl_names) + " |"
        fmt_sep = "|---|" + "|".join("---" for _ in impl_names) + "|"
        lines.append(fmt_header)
        lines.append(fmt_sep)
        fmt_matrix = self._scores.format_support_matrix()
        for fmt_name in sorted(fmt_matrix.keys()):
            cells = ["✅" if fmt_matrix[fmt_name][name] else "❌" for name in impl_names]
            lines.append(f"| {fmt_name} | " + " | ".join(cells) + " |")
        lines.append("")

        # Opcode matrix (abbreviated — show by category)
        lines.append("## Opcode Matrix by Category")
        lines.append("")
        cat_gaps = self._gaps.category_gaps()
        for cat_name, per_impl in cat_gaps.items():
            lines.append(f"### {cat_name.capitalize()}")
            lines.append("")
            cat_header = "| Implementation | Implemented | Total | Rate |"
            cat_sep = "|---|---|---|---|"
            lines.append(cat_header)
            lines.append(cat_sep)
            for impl_name, stats in per_impl.items():
                lines.append(
                    f"| {impl_name} | {stats['implemented']} "
                    f"| {stats['total']} | {stats['rate']:.1%} |"
                )
            lines.append("")

        # Priority gaps
        lines.append("## Top Priority Gaps")
        lines.append("")
        priority = self._gaps.priority_gaps(top_n=10)
        pg_header = "| Opcode | Code | Format | Category | In | Missing |"
        pg_sep = "|---|---|---|---|---|---|"
        lines.append(pg_header)
        lines.append(pg_sep)
        for gap in priority:
            lines.append(
                f"| {gap['opcode']} | {gap['code']} "
                f"| {gap['format']} | {gap['category']} "
                f"| {gap['implemented_in']} | {gap['missing_from']} |"
            )
        lines.append("")

        return "\n".join(lines)

    def to_json(self) -> str:
        """Export conformance data as JSON."""
        data: dict[str, Any] = {
            "isa_size": self._reg.total_opcodes,
            "implementations": {},
            "matrix": {},
            "scores": {},
            "coverage": self._coverage.coverage_by_implementation(),
            "category_gaps": self._gaps.category_gaps(),
            "format_support": self._scores.format_support_matrix(),
            "priority_gaps": self._gaps.priority_gaps(top_n=20),
        }

        for name, impl in self._reg.implementations.items():
            data["implementations"][name] = {
                "language": impl.language,
                "version": impl.version,
                "repo": impl.repo,
                "opcode_count": len(impl.opcode_codes),
                "formats": [f.value for f in sorted(impl.supported_formats, key=lambda x: x.value)],
                "categories": [c.value for c in sorted(impl.supported_categories, key=lambda x: x.value)],
            }

        matrix = self._matrix.build()
        for name, opcode_map in matrix.items():
            data["matrix"][name] = {
                f"0x{code:02X}": implemented for code, implemented in sorted(opcode_map.items())
            }

        for name in self._reg.implementation_names:
            data["scores"][name] = self._scores.composite_score(name)

        return json.dumps(data, indent=2)

    def to_csv(self) -> str:
        """Export conformance matrix as CSV."""
        output = io.StringIO()
        writer = csv.writer(output)

        # Header
        impl_names = self._reg.implementation_names
        header = ["Opcode", "Code", "Format", "Category", "Description"] + impl_names
        writer.writerow(header)

        # Rows
        for code, op in sorted(self._reg.opcode_table.items()):
            row = [
                op.mnemonic,
                f"0x{code:02X}",
                op.format.value,
                op.category.value,
                op.description,
            ]
            for name in impl_names:
                impl = self._reg.get(name)
                assert impl is not None
                row.append("✓" if code in impl.opcode_codes else "✗")
            writer.writerow(row)

        # Summary rows
        writer.writerow([])
        writer.writerow(["--- SUMMARY ---", "", "", "", ""] + [""] * len(impl_names))
        for name in impl_names:
            impl = self._reg.get(name)
            assert impl is not None
            scores = self._scores.composite_score(name)
            writer.writerow([
                name, "", impl.language, "",
                f"Opcodes: {len(impl.opcode_codes)}",
                f"Composite: {scores['composite']:.1%}",
            ] + [""] * (len(impl_names) - 1))

        return output.getvalue()

    def to_dict(self) -> dict[str, Any]:
        """Export conformance data as a Python dictionary."""
        return json.loads(self.to_json())
