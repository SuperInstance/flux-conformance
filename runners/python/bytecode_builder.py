#!/usr/bin/env python3
"""
flux-conformance BytecodeBuilder — Construct FLUX bytecode programmatically.

This builder uses the ACTUAL VM opcode values from flux.bytecode.opcodes.Op
(the system that the Interpreter executes), NOT the isa_unified.py spec values.

Encoding Formats (as implemented by the VM):
  Format A (1B):  [opcode]
  Format B (2B):  [opcode][reg:u8]
  Format C (3B):  [opcode][rd:u8][rs1:u8]
  Format D (4B):  [opcode][reg:u8][lo:u8][hi:u8]  (i16 little-endian)
  Format E (4B):  [opcode][rd:u8][rs1:u8][rs2:u8]
  Format G (var): [opcode][len:u16_LE][payload:len bytes]
"""

import struct
from typing import List, Optional, Union


class BytecodeBuilder:
    """Build FLUX bytecode for conformance tests."""

    # Opcode values matching flux.bytecode.opcodes.Op (what the VM executes)
    NOP = 0x00
    MOV = 0x01
    LOAD = 0x02
    STORE = 0x03
    JMP = 0x04
    JZ = 0x05
    JNZ = 0x06
    CALL = 0x07
    IADD = 0x08
    ISUB = 0x09
    IMUL = 0x0A
    IDIV = 0x0B
    IMOD = 0x0C
    INEG = 0x0D
    INC = 0x0E
    DEC = 0x0F
    IAND = 0x10
    IOR = 0x11
    IXOR = 0x12
    INOT = 0x13
    ISHL = 0x14
    ISHR = 0x15
    ROTL = 0x16
    ROTR = 0x17
    ICMP = 0x18
    IEQ = 0x19
    ILT = 0x1A
    ILE = 0x1B
    IGT = 0x1C
    IGE = 0x1D
    TEST = 0x1E
    SETCC = 0x1F
    PUSH = 0x20
    POP = 0x21
    DUP = 0x22
    SWAP = 0x23
    ROT = 0x24
    ENTER = 0x25
    LEAVE = 0x26
    ALLOCA = 0x27
    RET = 0x28
    CALL_IND = 0x29
    TAILCALL = 0x2A
    MOVI = 0x2B
    IREM = 0x2C
    CMP = 0x2D
    JE = 0x2E
    JNE = 0x2F
    REGION_CREATE = 0x30
    REGION_DESTROY = 0x31
    REGION_TRANSFER = 0x32
    MEMCOPY = 0x33
    MEMSET = 0x34
    MEMCMP = 0x35
    JL = 0x36
    JGE = 0x37
    CAST = 0x38
    BOX = 0x39
    UNBOX = 0x3A
    CHECK_TYPE = 0x3B
    CHECK_BOUNDS = 0x3C
    FADD = 0x40
    FSUB = 0x41
    FMUL = 0x42
    FDIV = 0x43
    FNEG = 0x44
    FABS = 0x45
    FMIN = 0x46
    FMAX = 0x47
    FEQ = 0x48
    FLT = 0x49
    FLE = 0x4A
    FGT = 0x4B
    FGE = 0x4C
    JG = 0x4D
    JLE = 0x4E
    LOAD8 = 0x4F
    VLOAD = 0x50
    VSTORE = 0x51
    VADD = 0x52
    VSUB = 0x53
    VMUL = 0x54
    VDIV = 0x55
    VFMA = 0x56
    STORE8 = 0x57
    TELL = 0x60
    ASK = 0x61
    DELEGATE = 0x62
    DELEGATE_RESULT = 0x63
    REPORT_STATUS = 0x64
    REQUEST_OVERRIDE = 0x65
    BROADCAST = 0x66
    REDUCE = 0x67
    DECLARE_INTENT = 0x68
    ASSERT_GOAL = 0x69
    VERIFY_OUTCOME = 0x6A
    EXPLAIN_FAILURE = 0x6B
    SET_PRIORITY = 0x6C
    TRUST_CHECK = 0x70
    TRUST_UPDATE = 0x71
    TRUST_QUERY = 0x72
    REVOKE_TRUST = 0x73
    CAP_REQUIRE = 0x74
    CAP_REQUEST = 0x75
    CAP_GRANT = 0x76
    CAP_REVOKE = 0x77
    BARRIER = 0x78
    SYNC_CLOCK = 0x79
    FORMATION_UPDATE = 0x7A
    EMERGENCY_STOP = 0x7B
    HALT = 0x80
    YIELD = 0x81
    RESOURCE_ACQUIRE = 0x82
    RESOURCE_RELEASE = 0x83
    DEBUG_BREAK = 0x84

    # ICMP condition codes
    EQ = 0x00
    NE = 0x01
    LT = 0x02
    LE = 0x03
    GT = 0x04
    GE = 0x05

    def __init__(self):
        self._buf: List[int] = []
        self._labels: dict = {}
        self._fixups: List[tuple] = []  # (position, label_name)

    # --- Low-level encoding helpers ---

    @staticmethod
    def _i16(val: int) -> bytes:
        """Encode signed 16-bit integer (little-endian)."""
        val = val & 0xFFFF
        if val >= 0x8000:
            val -= 0x10000
        return struct.pack('<h', val)

    @staticmethod
    def _u16(val: int) -> bytes:
        """Encode unsigned 16-bit integer (little-endian)."""
        return struct.pack('<H', val)

    @staticmethod
    def _var_data(payload: bytes) -> bytes:
        """Encode Format G variable-length payload."""
        return struct.pack('<H', len(payload)) + payload

    def _emit(self, *args: int):
        """Emit raw bytes."""
        for a in args:
            if isinstance(a, (bytes, bytearray)):
                self._buf.extend(a)
            else:
                self._buf.append(a & 0xFF)

    def _pos(self) -> int:
        """Current byte position."""
        return len(self._buf)

    # --- Format A: [opcode] (1 byte) ---

    def nop(self):
        self._emit(self.NOP)
        return self

    def dup(self):
        self._emit(self.DUP)
        return self

    def swap(self):
        self._emit(self.SWAP)
        return self

    def rot(self):
        self._emit(self.ROT)
        return self

    def halt(self):
        self._emit(self.HALT)
        return self

    def yield_(self):
        self._emit(self.YIELD)
        return self

    def debug_break(self):
        self._emit(self.DEBUG_BREAK)
        return self

    def emergency_stop(self):
        self._emit(self.EMERGENCY_STOP)
        return self

    # --- Format B: [opcode][reg:u8] (2 bytes) ---

    def inc(self, reg: int):
        self._emit(self.INC, reg)
        return self

    def dec(self, reg: int):
        self._emit(self.DEC, reg)
        return self

    def push(self, reg: int):
        self._emit(self.PUSH, reg)
        return self

    def pop(self, reg: int):
        self._emit(self.POP, reg)
        return self

    def enter(self, frame_size: int):
        self._emit(self.ENTER, frame_size)
        return self

    def leave(self):
        self._emit(self.LEAVE, 0)
        return self

    # --- Format C: [opcode][rd:u8][rs1:u8] (3 bytes) ---

    def mov(self, rd: int, rs1: int):
        self._emit(self.MOV, rd, rs1)
        return self

    def load(self, rd: int, rs1: int):
        self._emit(self.LOAD, rd, rs1)
        return self

    def store(self, rd: int, rs1: int):
        self._emit(self.STORE, rd, rs1)
        return self

    def ineg(self, rd: int, rs1: int):
        self._emit(self.INEG, rd, rs1)
        return self

    def inot(self, rd: int, rs1: int):
        self._emit(self.INOT, rd, rs1)
        return self

    def test(self, rd: int, rs1: int):
        self._emit(self.TEST, rd, rs1)
        return self

    def ret(self, rd: int = 0, rs1: int = 0):
        self._emit(self.RET, rd, rs1)
        return self

    def cmp(self, rd: int, rs1: int):
        self._emit(self.CMP, rd, rs1)
        return self

    # Float ops (Format E: 3 FP register operands)
    def fadd(self, fd: int, fs1: int, fs2: int):
        self._emit(self.FADD, fd, fs1, fs2)
        return self

    def fsub(self, fd: int, fs1: int, fs2: int):
        self._emit(self.FSUB, fd, fs1, fs2)
        return self

    def fmul(self, fd: int, fs1: int, fs2: int):
        self._emit(self.FMUL, fd, fs1, fs2)
        return self

    def fdiv(self, fd: int, fs1: int, fs2: int):
        self._emit(self.FDIV, fd, fs1, fs2)
        return self

    def fneg(self, fd: int, fs1: int):
        self._emit(self.FNEG, fd, fs1)
        return self

    def fabs(self, fd: int, fs1: int):
        self._emit(self.FABS, fd, fs1)
        return self

    def fmin(self, fd: int, fs1: int):
        self._emit(self.FMIN, fd, fs1)
        return self

    def fmax(self, fd: int, fs1: int):
        self._emit(self.FMAX, fd, fs1)
        return self

    def feq(self, rd: int, rs1: int):
        self._emit(self.FEQ, rd, rs1)
        return self

    def flt(self, rd: int, rs1: int):
        self._emit(self.FLT, rd, rs1)
        return self

    def fle(self, rd: int, rs1: int):
        self._emit(self.FLE, rd, rs1)
        return self

    def fgt(self, rd: int, rs1: int):
        self._emit(self.FGT, rd, rs1)
        return self

    def fge(self, rd: int, rs1: int):
        self._emit(self.FGE, rd, rs1)
        return self

    def load8(self, rd: int, rs1: int):
        self._emit(self.LOAD8, rd, rs1)
        return self

    def store8(self, rd: int, rs1: int):
        self._emit(self.STORE8, rd, rs1)
        return self

    def check_bounds(self, idx_reg: int, len_reg: int):
        self._emit(self.CHECK_BOUNDS, idx_reg, len_reg)
        return self

    # --- Format D: [opcode][reg:u8][lo:u8][hi:u8] (4 bytes, i16 LE) ---

    def jmp(self, offset: int, reg: int = 0):
        self._emit(self.JMP, reg, *self._i16(offset))
        return self

    def jz(self, reg: int, offset: int):
        self._emit(self.JZ, reg, *self._i16(offset))
        return self

    def jnz(self, reg: int, offset: int):
        self._emit(self.JNZ, reg, *self._i16(offset))
        return self

    def call(self, offset: int, reg: int = 0):
        self._emit(self.CALL, reg, *self._i16(offset))
        return self

    def je(self, offset: int, reg: int = 0):
        self._emit(self.JE, reg, *self._i16(offset))
        return self

    def jne(self, offset: int, reg: int = 0):
        self._emit(self.JNE, reg, *self._i16(offset))
        return self

    def jg(self, offset: int, reg: int = 0):
        self._emit(self.JG, reg, *self._i16(offset))
        return self

    def jl(self, offset: int, reg: int = 0):
        self._emit(self.JL, reg, *self._i16(offset))
        return self

    def jge(self, offset: int, reg: int = 0):
        self._emit(self.JGE, reg, *self._i16(offset))
        return self

    def jle(self, offset: int, reg: int = 0):
        self._emit(self.JLE, reg, *self._i16(offset))
        return self

    def movi(self, reg: int, imm: int):
        """Load immediate i16 into register."""
        self._emit(self.MOVI, reg, *self._i16(imm))
        return self

    def tailcall(self, offset: int, reg: int = 0):
        self._emit(self.TAILCALL, reg, *self._i16(offset))
        return self

    # --- Format E: [opcode][rd:u8][rs1:u8][rs2:u8] (4 bytes) ---

    def iadd(self, rd: int, rs1: int, rs2: int):
        self._emit(self.IADD, rd, rs1, rs2)
        return self

    def isub(self, rd: int, rs1: int, rs2: int):
        self._emit(self.ISUB, rd, rs1, rs2)
        return self

    def imul(self, rd: int, rs1: int, rs2: int):
        self._emit(self.IMUL, rd, rs1, rs2)
        return self

    def idiv(self, rd: int, rs1: int, rs2: int):
        self._emit(self.IDIV, rd, rs1, rs2)
        return self

    def imod(self, rd: int, rs1: int, rs2: int):
        self._emit(self.IMOD, rd, rs1, rs2)
        return self

    def irem(self, rd: int, rs1: int, rs2: int):
        self._emit(self.IREM, rd, rs1, rs2)
        return self

    def iand(self, rd: int, rs1: int, rs2: int):
        self._emit(self.IAND, rd, rs1, rs2)
        return self

    def ior(self, rd: int, rs1: int, rs2: int):
        self._emit(self.IOR, rd, rs1, rs2)
        return self

    def ixor(self, rd: int, rs1: int, rs2: int):
        self._emit(self.IXOR, rd, rs1, rs2)
        return self

    def ishl(self, rd: int, rs1: int, rs2: int):
        self._emit(self.ISHL, rd, rs1, rs2)
        return self

    def ishr(self, rd: int, rs1: int, rs2: int):
        self._emit(self.ISHR, rd, rs1, rs2)
        return self

    def rotl(self, rd: int, rs1: int, rs2: int):
        self._emit(self.ROTL, rd, rs1, rs2)
        return self

    def rotr(self, rd: int, rs1: int, rs2: int):
        self._emit(self.ROTR, rd, rs1, rs2)
        return self

    def vfma(self, rd: int, rs1: int, rs2: int):
        self._emit(self.VFMA, rd, rs1, rs2)
        return self

    # --- Extended Format C (4 bytes) ---

    def icmp(self, cond: int, a_reg: int, b_reg: int):
        """Format C+1: [ICMP][cond:u8][a_reg:u8][b_reg:u8]."""
        self._emit(self.ICMP, cond, a_reg, b_reg)
        return self

    def setcc(self, rd: int, cond: int):
        """Format B+1: [SETCC][rd:u8][cond:u8]."""
        self._emit(self.SETCC, rd, cond)
        return self

    def cast(self, rd: int, rs1: int, type_tag: int):
        """Format C+1: [CAST][rd:u8][rs1:u8][type_tag:u8]."""
        self._emit(self.CAST, rd, rs1, type_tag)
        return self

    def box(self, rd: int, type_tag: int, value: int):
        """Format C+4: [BOX][rd:u8][type_tag:u8][value:i32_LE]."""
        self._emit(self.BOX, rd, type_tag, *struct.pack('<i', value))
        return self

    # --- Format G: variable length ---

    def tell(self, payload: bytes):
        self._emit(self.TELL, *self._var_data(payload))
        return self

    def ask(self, payload: bytes):
        self._emit(self.ASK, *self._var_data(payload))
        return self

    def delegate(self, payload: bytes):
        self._emit(self.DELEGATE, *self._var_data(payload))
        return self

    def broadcast(self, payload: bytes):
        self._emit(self.BROADCAST, *self._var_data(payload))
        return self

    def region_create(self, name: str, size: int, owner: str = "test"):
        """Create a memory region. Format G with structured payload."""
        name_bytes = name.encode()
        owner_bytes = owner.encode()
        payload = (
            bytes([len(name_bytes)]) + name_bytes +
            struct.pack('<I', size) +
            bytes([len(owner_bytes)]) + owner_bytes
        )
        self._emit(self.REGION_CREATE, *self._var_data(payload))
        return self

    def region_destroy(self, name: str):
        name_bytes = name.encode()
        payload = bytes([len(name_bytes)]) + name_bytes
        self._emit(self.REGION_DESTROY, *self._var_data(payload))
        return self

    def memset(self, name: str, offset: int, value: int, size: int):
        name_bytes = name.encode()
        payload = (
            bytes([len(name_bytes)]) + name_bytes +
            struct.pack('<I', offset) +
            bytes([value]) +
            struct.pack('<I', size)
        )
        self._emit(self.MEMSET, *self._var_data(payload))
        return self

    # --- Labels and fixups ---

    def _emit_label_jump(self, opcode: int, reg: int, name: str):
        """Emit a jump instruction with label resolution (forward + backward)."""
        pos = self._pos()
        self._emit(opcode, reg, 0, 0)  # placeholder
        if name in self._labels:
            # Backward reference — resolve immediately
            offset = self._labels[name] - (pos + 4)
            lo = offset & 0xFF
            hi = (offset >> 8) & 0xFF
            self._buf[pos + 2] = lo
            self._buf[pos + 3] = hi
        else:
            # Forward reference — add to fixup list
            self._fixups.append((pos, name))
        return self

    def label(self, name: str):
        """Define a label at the current position."""
        self._labels[name] = self._pos()
        # Fix up any forward references
        new_fixups = []
        for pos, label in self._fixups:
            if label == name:
                offset = self._labels[name] - (pos + 4)
                lo = offset & 0xFF
                hi = (offset >> 8) & 0xFF
                self._buf[pos + 2] = lo
                self._buf[pos + 3] = hi
            else:
                new_fixups.append((pos, label))
        self._fixups = new_fixups
        return self

    def jmp_label(self, name: str, reg: int = 0):
        """Jump to a named label. Supports forward and backward references."""
        return self._emit_label_jump(self.JMP, reg, name)

    def jz_label(self, reg: int, name: str):
        return self._emit_label_jump(self.JZ, reg, name)

    def jnz_label(self, reg: int, name: str):
        return self._emit_label_jump(self.JNZ, reg, name)

    def je_label(self, name: str, reg: int = 0):
        return self._emit_label_jump(self.JE, reg, name)

    def jne_label(self, name: str, reg: int = 0):
        return self._emit_label_jump(self.JNE, reg, name)

    def jl_label(self, name: str, reg: int = 0):
        return self._emit_label_jump(self.JL, reg, name)

    def jge_label(self, name: str, reg: int = 0):
        return self._emit_label_jump(self.JGE, reg, name)

    def jg_label(self, name: str, reg: int = 0):
        return self._emit_label_jump(self.JG, reg, name)

    def jle_label(self, name: str, reg: int = 0):
        return self._emit_label_jump(self.JLE, reg, name)

    def call_label(self, name: str, reg: int = 0):
        return self._emit_label_jump(self.CALL, reg, name)

    # --- Build ---

    def build(self) -> bytes:
        """Build final bytecode. Raises if there are unresolved labels."""
        if self._fixups:
            unresolved = [label for _, label in self._fixups]
            raise ValueError(f"Unresolved labels: {unresolved}")
        return bytes(self._buf)

    def hex(self) -> str:
        """Build and return hex string."""
        return self.build().hex()

    def size(self) -> int:
        """Current size of bytecode in bytes."""
        return self._pos()

    def __len__(self) -> int:
        return self._pos()
