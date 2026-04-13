"""
FLUX Canonical Opcode Translation Shim

Provides bidirectional bytecode translation between each runtime's internal
opcode numbering and the canonical ISA numbering from flux-spec/ISA.md.

Usage:
    from canonical_opcode_shim import translate

    # Python bytecode -> Canonical bytecode
    canonical_bc = translate.python_to_canonical(python_bytecode)

    # Canonical bytecode -> Rust bytecode
    rust_bc = translate.canonical_to_rust(canonical_bytecode)

    # Or chain: Python -> Canonical -> Rust
    rust_bc = translate.canonical_to_rust(translate.python_to_canonical(python_bc))

The canonical ISA follows flux-spec/ISA.md (v1.0) numbering:
    0x00=HALT, 0x01=NOP, 0x02=RET, 0x08=INC, 0x09=DEC, 0x0E=PUSH, 0x0F=POP,
    0x18=MOVI, 0x20=ADD, 0x21=SUB, 0x22=MUL, 0x23=DIV, 0x38=LOAD, 0x39=STORE,
    0x3A=MOV, 0x3C=JZ, 0x3D=JNZ, 0x44=JMP, 0x50=TELL, 0x51=ASK, ...
"""

from __future__ import annotations


# ─── Canonical ISA (flux-spec/ISA.md v1.0) ────────────────────────────
# Only non-0xFF opcodes are translated. 0xFF is the escape prefix for
# v3 extensions and passes through unchanged.

# ─── Python Runtime -> Canonical ──────────────────────────────────────
# Maps Python opcode byte -> Canonical opcode byte.
# Source: flux-runtime/src/flux/bytecode/opcodes.py

_PYTHON_TO_CANONICAL = bytearray(256)

# Python runtime opcode assignments (from opcodes.py Op class)
_PythonOp = {
    "NOP": 0x00, "MOV": 0x01, "LOAD": 0x02, "STORE": 0x03,
    "JMP": 0x04, "JZ": 0x05, "JNZ": 0x06, "CALL": 0x07,
    "IADD": 0x08, "ISUB": 0x09, "IMUL": 0x0A, "IDIV": 0x0B,
    "IMOD": 0x0C, "INEG": 0x0D, "INC": 0x0E, "DEC": 0x0F,
    "IAND": 0x10, "IOR": 0x11, "IXOR": 0x12, "INOT": 0x13,
    "ISHL": 0x14, "ISHR": 0x15, "ROTL": 0x16, "ROTR": 0x17,
    "ICMP": 0x18, "IEQ": 0x19, "ILT": 0x1A, "ILE": 0x1B,
    "IGT": 0x1C, "IGE": 0x1D, "TEST": 0x1E, "SETCC": 0x1F,
    "PUSH": 0x20, "POP": 0x21, "DUP": 0x22, "SWAP": 0x23,
    "ROT": 0x24, "ENTER": 0x25, "LEAVE": 0x26, "ALLOCA": 0x27,
    "RET": 0x28, "CALL_IND": 0x29, "TAILCALL": 0x2A, "MOVI": 0x2B,
    "IREM": 0x2C, "CMP": 0x2D, "JE": 0x2E, "JNE": 0x2F,
    "REGION_CREATE": 0x30, "REGION_DESTROY": 0x31, "REGION_TRANSFER": 0x32,
    "MEMCOPY": 0x33, "MEMSET": 0x34, "MEMCMP": 0x35,
    "JL": 0x36, "JGE": 0x37,
    "CAST": 0x38, "BOX": 0x39, "UNBOX": 0x3A, "CHECK_TYPE": 0x3B,
    "CHECK_BOUNDS": 0x3C, "CONF": 0x3D, "MERGE": 0x3E, "RESTORE": 0x3F,
    "FADD": 0x40, "FSUB": 0x41, "FMUL": 0x42, "FDIV": 0x43,
    "FNEG": 0x44, "FABS": 0x45, "FMIN": 0x46, "FMAX": 0x47,
    "FEQ": 0x48, "FLT": 0x49, "FLE": 0x4A, "FGT": 0x4B, "FGE": 0x4C,
    "JG": 0x4D, "JLE": 0x4E, "LOAD8": 0x4F,
    "VLOAD": 0x50, "VSTORE": 0x51, "VADD": 0x52, "VSUB": 0x53,
    "VMUL": 0x54, "VDIV": 0x55, "VFMA": 0x56, "STORE8": 0x57,
    "TELL": 0x60, "ASK": 0x61, "DELEGATE": 0x62, "DELEGATE_RESULT": 0x63,
    "REPORT_STATUS": 0x64, "REQUEST_OVERRIDE": 0x65, "BROADCAST": 0x66,
    "REDUCE": 0x67, "DECLARE_INTENT": 0x68, "ASSERT_GOAL": 0x69,
    "VERIFY_OUTCOME": 0x6A, "EXPLAIN_FAILURE": 0x6B, "SET_PRIORITY": 0x6C,
    "TRUST_CHECK": 0x70, "TRUST_UPDATE": 0x71, "TRUST_QUERY": 0x72,
    "REVOKE_TRUST": 0x73, "CAP_REQUIRE": 0x74, "CAP_REQUEST": 0x75,
    "CAP_GRANT": 0x76, "CAP_REVOKE": 0x77,
    "BARRIER": 0x78, "SYNC_CLOCK": 0x79, "FORMATION_UPDATE": 0x7A,
    "EMERGENCY_STOP": 0x7B, "EVOLVE": 0x7C, "INSTINCT": 0x7D,
    "WITNESS": 0x7E, "SNAPSHOT": 0x7F,
    "HALT": 0x80, "YIELD": 0x81, "RESOURCE_ACQUIRE": 0x82,
    "RESOURCE_RELEASE": 0x83, "DEBUG_BREAK": 0x84,
}

# Canonical ISA opcode assignments (from flux-spec/ISA.md)
_CanonicalOp = {
    "HALT": 0x00, "NOP": 0x01, "RET": 0x02, "IRET": 0x03,
    "BRK": 0x04, "WFI": 0x05, "RESET": 0x06, "SYN": 0x07,
    "INC": 0x08, "DEC": 0x09, "NOT": 0x0A, "NEG": 0x0B,
    "PUSH": 0x0C, "POP": 0x0D, "CONF_LD": 0x0E, "CONF_ST": 0x0F,
    "SYS": 0x10, "TRAP": 0x11, "DBG": 0x12, "CLF": 0x13,
    "SEMA": 0x14, "YIELD": 0x15, "CACHE": 0x16, "STRIPCF": 0x17,
    "MOVI": 0x18, "ADDI": 0x19, "SUBI": 0x1A, "ANDI": 0x1B,
    "ORI": 0x1C, "XORI": 0x1D, "SHLI": 0x1E, "SHRI": 0x1F,
    "ADD": 0x20, "SUB": 0x21, "MUL": 0x22, "DIV": 0x23,
    "MOD": 0x24, "AND": 0x25, "OR": 0x26, "XOR": 0x27,
    "SHL": 0x28, "SHR": 0x29, "MIN": 0x2A, "MAX": 0x2B,
    "CMP_EQ": 0x2C, "CMP_LT": 0x2D, "CMP_GT": 0x2E, "CMP_NE": 0x2F,
    "FADD": 0x30, "FSUB": 0x31, "FMUL": 0x32, "FDIV": 0x33,
    "FMIN": 0x34, "FMAX": 0x35, "FTOI": 0x36, "ITOF": 0x37,
    "LOAD": 0x38, "STORE": 0x39, "MOV": 0x3A, "SWP": 0x3B,
    "JZ": 0x3C, "JNZ": 0x3D, "JLT": 0x3E, "JGT": 0x3F,
    "MOVI16": 0x40, "ADDI16": 0x41, "SUBI16": 0x42, "JMP": 0x43,
    "JAL": 0x44, "CALL": 0x45, "LOOP": 0x46, "SELECT": 0x47,
    "TELL": 0x50, "ASK": 0x51, "DELEG": 0x52, "BCAST": 0x53,
    "VLOAD": 0xB0, "VSTORE": 0xB1, "VADD": 0xB2, "VMUL": 0xB3,
    "VDOT": 0xB4,
}


def _build_translation_table(
    src_opcodes: dict[str, int],
    dst_opcodes: dict[str, int],
    unmapped: int = 0xFE,
) -> bytearray:
    """Build a 256-byte translation table: src_byte -> dst_byte.

    For each opcode name that exists in both source and destination,
    the table maps the source's hex value to the destination's hex value.
    Unmapped bytes map to ``unmapped`` (default 0xFE = RESERVED).
    """
    table = bytearray([unmapped] * 256)

    # Build reverse lookup: src_byte -> name
    src_by_name: dict[str, int] = {n.lower(): v for n, v in src_opcodes.items()}
    src_by_val: dict[int, str] = {v: n for n, v in src_opcodes.items()}

    # Map matching names
    for name, dst_val in dst_opcodes.items():
        src_val = src_by_name.get(name.lower())
        if src_val is not None:
            table[src_val] = dst_val

    # Map Python-specific names to canonical equivalents
    _aliases = {
        # Python name -> Canonical name
        "IADD": "ADD", "ISUB": "SUB", "IMUL": "MUL", "IDIV": "DIV",
        "IMOD": "MOD", "INEG": "NEG", "INOT": "NOT",
        "IAND": "AND", "IOR": "OR", "IXOR": "XOR",
        "ISHL": "SHL", "ISHR": "SHR",
        "IEQ": "CMP_EQ", "ILT": "CMP_LT", "IGT": "CMP_GT",
        "ILE": "CMP_EQ",  # approximate
        "IGE": "CMP_GT",  # approximate
        "BROADCAST": "BCAST",
        "DELEGATE": "DELEG",
        "ROTL": None, "ROTR": None,  # canonical has no direct equivalent
        "ICMP": "CMP_EQ",  # approximate
        "CMP": "CMP_EQ",  # approximate
        "ALLOCA": None,   # no canonical equivalent
        "TEST": None, "SETCC": None,
        "ENTER": None, "LEAVE": None,  # canonical uses different mechanism
    }

    for py_name, canon_name in _aliases.items():
        if canon_name is None:
            continue
        py_val = _PythonOp.get(py_name)
        canon_val = _CanonicalOp.get(canon_name)
        if py_val is not None and canon_val is not None:
            table[py_val] = canon_val

    # 0xFF escape prefix passes through
    table[0xFF] = 0xFF
    return table


def _invert_table(table: bytearray, unmapped: int = 0xFE) -> bytearray:
    """Invert a translation table (dst -> src from src -> dst)."""
    inv = bytearray([unmapped] * 256)
    for src, dst in enumerate(table):
        if dst != unmapped:
            inv[dst] = src
    return inv


# ─── Build all translation tables ─────────────────────────────────────

# Python Runtime <-> Canonical
_PY_TO_CAN = _build_translation_table(_PythonOp, _CanonicalOp)
_CAN_TO_PY = _invert_table(_PY_TO_CAN)


# ─── Rust Runtime ─────────────────────────────────────────────────────
# Source: flux/crates/flux-bytecode/src/opcodes.rs

_RustOp = {
    "Halt": 0x00, "Nop": 0x01, "Ret": 0x02, "Jump": 0x03,
    "JumpIf": 0x04, "JumpIfNot": 0x05, "Call": 0x06, "CallIndirect": 0x07,
    "Yield": 0x08, "Panic": 0x09, "Unreachable": 0x0A,
    "Push": 0x10, "Pop": 0x11, "Dup": 0x12, "Swap": 0x13,
    "IMov": 0x20, "IAdd": 0x21, "ISub": 0x22, "IMul": 0x23,
    "IDiv": 0x24, "IMod": 0x25, "INeg": 0x26, "IAbs": 0x27,
    "IInc": 0x28, "IDec": 0x29, "IMin": 0x2A, "IMax": 0x2B,
    "IAnd": 0x2C, "IOr": 0x2D, "IXor": 0x2E, "IShl": 0x2F,
    "IShr": 0x30, "INot": 0x31,
    "ICmpEq": 0x32, "ICmpNe": 0x33, "ICmpLt": 0x34, "ICmpLe": 0x35,
    "ICmpGt": 0x36, "ICmpGe": 0x37,
    "FMov": 0x40, "FAdd": 0x41, "FSub": 0x42, "FMul": 0x43,
    "FDiv": 0x44, "FMod": 0x45, "FNeg": 0x46, "FAbs": 0x47,
    "FSqrt": 0x48, "FFloor": 0x49, "FCeil": 0x4A, "FRound": 0x4B,
    "FMin": 0x4C, "FMax": 0x4D,
    "IToF": 0x60, "FToI": 0x61, "BToI": 0x62, "IToB": 0x63,
    "Load8": 0x70, "Load16": 0x71, "Load32": 0x72, "Load64": 0x73,
    "Store8": 0x74, "Store16": 0x75, "Store32": 0x76, "Store64": 0x77,
    "LoadAddr": 0x78, "StackAlloc": 0x79,
    "ASend": 0x80, "ARecv": 0x81, "AAsk": 0x82, "ATell": 0x83,
    "ADelegate": 0x84, "ABroadcast": 0x85, "ASubscribe": 0x86,
    "AWait": 0x87, "ATrust": 0x88, "AVerify": 0x89,
    "Cast": 0x90, "SizeOf": 0x91, "TypeOf": 0x92,
    "VLoad": 0xB0, "VStore": 0xB1, "VAdd": 0xB2, "VMul": 0xB3, "VDot": 0xB4,
}

# Rust-specific aliases for canonical mapping
_RustAliases = {
    "IMov": "MOV", "IAdd": "ADD", "ISub": "SUB", "IMul": "MUL",
    "IDiv": "DIV", "IMod": "MOD", "INeg": "NEG", "INot": "NOT",
    "IAnd": "AND", "IOr": "OR", "IXor": "XOR",
    "IShl": "SHL", "IShr": "SHR",
    "ICmpEq": "CMP_EQ", "ICmpNe": "CMP_NE", "ICmpLt": "CMP_LT",
    "ICmpGt": "CMP_GT", "ICmpLe": "CMP_EQ", "ICmpGe": "CMP_GT",
    "IAbs": None, "IInc": None, "IDec": None, "IMin": "MIN", "IMax": "MAX",
    "FAdd": "FADD", "FSub": "FSUB", "FMul": "FMUL", "FDiv": "FDIV",
    "FNeg": None, "FAbs": None, "FMin": "FMIN", "FMax": "FMAX",
    "IToF": "ITOF", "FToI": "FTOI",
    "ATell": "TELL", "AAsk": "ASK", "ADelegate": "DELEG",
    "ABroadcast": "BCAST", "ATrust": None, "AVerify": None,
    "Jump": "JMP", "JumpIf": "JZ", "JumpIfNot": "JNZ",
}

_RUST_TO_CAN = _build_translation_table(_RustOp, _CanonicalOp)
# Apply Rust-specific aliases
for rust_name, canon_name in _RustAliases.items():
    if canon_name is None:
        continue
    rust_val = _RustOp.get(rust_name)
    canon_val = _CanonicalOp.get(canon_name)
    if rust_val is not None and canon_val is not None:
        _RUST_TO_CAN[rust_val] = canon_val

_CAN_TO_RUST = _invert_table(_RUST_TO_CAN)


# ─── C Runtime (flux-os) ─────────────────────────────────────────────
# Source: flux-os/vm/opcodes.c

_COSOp = {
    "NOP": 0x00, "HALT": 0x01, "TRAP": 0x02, "INVALID": 0x03,
    "IADD": 0x10, "ISUB": 0x11, "IMUL": 0x12, "IDIV": 0x13,
    "IMOD": 0x14, "INEG": 0x15, "IABS": 0x16, "INC": 0x17,
    "DEC": 0x18, "FADD": 0x19, "FSUB": 0x1A, "FMUL": 0x1B, "FDIV": 0x1C,
    "FNEG": 0x1D, "I2F": 0x1E, "F2I": 0x1F,
    "IAND": 0x20, "IOR": 0x21, "IXOR": 0x22, "INOT": 0x23,
    "ISHL": 0x24, "ISHR": 0x25, "USHR": 0x26,
    "ROTATE_L": 0x27, "ROTATE_R": 0x28,
    "CMP": 0x30, "CMPI": 0x31, "FCMP": 0x32, "TEST": 0x33,
    "JMP": 0x40, "JZ": 0x41, "JNZ": 0x42, "JE": 0x43, "JNE": 0x44,
    "LOAD": 0x50, "LOAD8": 0x51, "LOAD16": 0x52, "LOAD32": 0x53,
    "STORE": 0x54, "STORE8": 0x55, "STORE16": 0x56, "STORE32": 0x57,
    "PUSH": 0x60, "POP": 0x61, "DUP": 0x63, "SWAP": 0x64,
    "CALL": 0x70, "RET": 0x72,
    "TELL": 0x81, "ASK": 0x82,
}

_COSAliases = {
    "IADD": "ADD", "ISUB": "SUB", "IMUL": "MUL", "IDIV": "DIV",
    "IMOD": "MOD", "INEG": "NEG", "INOT": "NOT",
    "IAND": "AND", "IOR": "OR", "IXOR": "XOR",
    "ISHL": "SHL", "ISHR": "SHR",
    "FADD": "FADD", "FSUB": "FSUB", "FMUL": "FMUL", "FDIV": "FDIV",
    "CMP": "CMP_EQ", "JE": "CMP_EQ", "JNE": "CMP_NE",
}

_COS_TO_CAN = _build_translation_table(_COSOp, _CanonicalOp)
for cos_name, canon_name in _COSAliases.items():
    if canon_name is None:
        continue
    cos_val = _COSOp.get(cos_name)
    canon_val = _CanonicalOp.get(canon_name)
    if cos_val is not None and canon_val is not None:
        _COS_TO_CAN[cos_val] = canon_val

_CAN_TO_COS = _invert_table(_COS_TO_CAN)


# ─── Go Runtime (flux-swarm) ─────────────────────────────────────────
# Source: flux-swarm/flux.go

_GoOp = {
    "NOP": 0x00, "MOV": 0x01, "JNZ": 0x06, "IADD": 0x08,
    "ISUB": 0x09, "IMUL": 0x0A, "IDIV": 0x0B, "INC": 0x0E,
    "DEC": 0x0F, "JMP": 0x13, "MOVI": 0x2B, "CMP": 0x2D,
    "JZ": 0x2E, "HALT": 0x80,
}

_GoAliases = {
    "IADD": "ADD", "ISUB": "SUB", "IMUL": "MUL", "IDIV": "DIV",
    "CMP": "CMP_EQ",
}

_GO_TO_CAN = _build_translation_table(_GoOp, _CanonicalOp)
for go_name, canon_name in _GoAliases.items():
    if canon_name is None:
        continue
    go_val = _GoOp.get(go_name)
    canon_val = _CanonicalOp.get(canon_name)
    if go_val is not None and canon_val is not None:
        _GO_TO_CAN[go_val] = canon_val

_CAN_TO_GO = _invert_table(_GO_TO_CAN)


# ─── Translation functions ────────────────────────────────────────────

def python_to_canonical(bytecode: bytes) -> bytes:
    """Translate Python runtime bytecode to canonical ISA bytecode."""
    return bytes(_PY_TO_CAN[b] for b in bytecode)

def canonical_to_python(bytecode: bytes) -> bytes:
    """Translate canonical ISA bytecode to Python runtime bytecode."""
    return bytes(_CAN_TO_PY[b] for b in bytecode)

def rust_to_canonical(bytecode: bytes) -> bytes:
    """Translate Rust runtime bytecode to canonical ISA bytecode."""
    return bytes(_RUST_TO_CAN[b] for b in bytecode)

def canonical_to_rust(bytecode: bytes) -> bytes:
    """Translate canonical ISA bytecode to Rust runtime bytecode."""
    return bytes(_CAN_TO_RUST[b] for b in bytecode)

def cos_to_canonical(bytecode: bytes) -> bytes:
    """Translate flux-os (C) runtime bytecode to canonical ISA bytecode."""
    return bytes(_COS_TO_CAN[b] for b in bytecode)

def canonical_to_cos(bytecode: bytes) -> bytes:
    """Translate canonical ISA bytecode to flux-os (C) runtime bytecode."""
    return bytes(_CAN_TO_COS[b] for b in bytecode)

def go_to_canonical(bytecode: bytes) -> bytes:
    """Translate Go (flux-swarm) runtime bytecode to canonical ISA bytecode."""
    return bytes(_GO_TO_CAN[b] for b in bytecode)

def canonical_to_go(bytecode: bytes) -> bytes:
    """Translate canonical ISA bytecode to Go (flux-swarm) runtime bytecode."""
    return bytes(_CAN_TO_GO[b] for b in bytecode)


# ─── Cross-runtime direct translation ─────────────────────────────────

def python_to_rust(bytecode: bytes) -> bytes:
    """Translate Python bytecode -> Canonical -> Rust bytecode."""
    return canonical_to_rust(python_to_canonical(bytecode))

def rust_to_python(bytecode: bytes) -> bytes:
    """Translate Rust bytecode -> Canonical -> Python bytecode."""
    return canonical_to_python(rust_to_canonical(bytecode))

def python_to_go(bytecode: bytes) -> bytes:
    """Translate Python bytecode -> Canonical -> Go bytecode."""
    return canonical_to_go(python_to_canonical(bytecode))

def go_to_python(bytecode: bytes) -> bytes:
    """Translate Go bytecode -> Canonical -> Python bytecode."""
    return canonical_to_python(go_to_canonical(bytecode))


# ─── Coverage report ──────────────────────────────────────────────────

def coverage_report() -> str:
    """Generate a coverage report showing how many opcodes translate successfully."""
    lines = ["FLUX Canonical Opcode Translation Coverage Report", "=" * 50, ""]

    for name, table in [
        ("Python Runtime", _PY_TO_CAN),
        ("Rust Runtime", _RUST_TO_CAN),
        ("C Runtime (flux-os)", _COS_TO_CAN),
        ("Go Runtime (flux-swarm)", _GO_TO_CAN),
    ]:
        mapped = sum(1 for b in table if b != 0xFE and b != 0xFF)
        escape = sum(1 for b in table if b == 0xFF)
        unmapped = 256 - mapped - escape
        lines.append(f"{name}:")
        lines.append(f"  Translatable: {mapped}/256")
        lines.append(f"  Escape prefix (passthrough): {escape}")
        lines.append(f"  Unmapped: {unmapped}")
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    print(coverage_report())
