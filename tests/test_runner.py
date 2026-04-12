"""Comprehensive tests for the FLUX Conformance Test Runner.

Tests cover:
1. Encoding helpers (7 functions, ~20 tests)
2. MiniVM execution for all major opcode categories (~50 tests)
3. Edge cases (div-by-zero, stack overflow, invalid opcodes) (~15 tests)
4. A2A opcode trace recording (~5 tests)
5. VectorGenerator produces valid vectors (~15 tests)
6. ConformanceRunner produces correct results (~20 tests)
7. ConformanceReporter formatting (~15 tests)
8. Combined / integration tests (~15 tests)
"""

import math
import struct

import pytest

from flux_conformance.runner import (
    MiniVM,
    Flags,
    TestVector,
    ConformanceResult,
    VectorGenerator,
    ConformanceRunner,
    ConformanceReporter,
    _s32,
    _u32,
    _reg_to_float,
    _float_to_reg,
    _OPCODE_NAMES,
    _OPCODE_FORMATS,
    FORMAT_SIZES,
    MASK32,
    NUM_REGISTERS,
    MEMORY_SIZE,
    STACK_DEPTH,
    encode_a,
    encode_b,
    encode_c,
    encode_d,
    encode_e,
    encode_f,
    encode_g,
)


# ===========================================================================
# Fixtures
# ===========================================================================

@pytest.fixture
def vm() -> MiniVM:
    """Return a fresh MiniVM instance."""
    return MiniVM()


@pytest.fixture
def runner() -> ConformanceRunner:
    """Return a fresh ConformanceRunner."""
    return ConformanceRunner()


@pytest.fixture
def generator() -> VectorGenerator:
    """Return a fresh VectorGenerator."""
    return VectorGenerator()


@pytest.fixture
def all_vectors() -> list[TestVector]:
    """Return all generated test vectors."""
    gen = VectorGenerator()
    return gen.generate_all()


# ===========================================================================
# 1. Internal Helper Tests
# ===========================================================================

class TestInternalHelpers:
    """Tests for _s32, _u32, _reg_to_float, _float_to_reg."""

    def test_s32_zero(self) -> None:
        assert _s32(0) == 0

    def test_s32_positive(self) -> None:
        assert _s32(42) == 42

    def test_s32_max(self) -> None:
        assert _s32(0x7FFFFFFF) == 0x7FFFFFFF

    def test_s32_negative_one(self) -> None:
        assert _s32(0xFFFFFFFF) == -1

    def test_s32_min(self) -> None:
        assert _s32(0x80000000) == -0x80000000

    def test_s32_overflow(self) -> None:
        assert _s32(0x100000000) == 0

    def test_u32_positive(self) -> None:
        assert _u32(42) == 42

    def test_u32_negative(self) -> None:
        assert _u32(-1) == 0xFFFFFFFF

    def test_float_roundtrip(self) -> None:
        for val in [0.0, 1.0, -1.0, 3.14, 100.5]:
            bits = _float_to_reg(val)
            recovered = _reg_to_float(bits)
            assert abs(recovered - val) < 1e-6, f"Failed for {val}"
        # -273.15 loses precision in single-precision float
        bits = _float_to_reg(-273.15)
        assert abs(_reg_to_float(bits) - (-273.15)) < 1e-4

    def test_float_to_reg_zero(self) -> None:
        assert _float_to_reg(0.0) == 0

    def test_u32_mask(self) -> None:
        assert _u32(0x1FFFFFFFF) == 0xFFFFFFFF


# ===========================================================================
# 2. Encoding Helper Tests
# ===========================================================================

class TestEncoding:
    """Tests for encoding helper functions."""

    def test_encode_a_length(self) -> None:
        assert len(encode_a(0x00)) == 1

    def test_encode_a_halt(self) -> None:
        assert encode_a(0x00) == b"\x00"

    def test_encode_a_nop(self) -> None:
        assert encode_a(0x01) == b"\x01"

    def test_encode_b_length(self) -> None:
        assert len(encode_b(0x08, 1)) == 2

    def test_encode_b_registers(self) -> None:
        for rd in range(16):
            b = encode_b(0x08, rd)
            assert b[0] == 0x08
            assert b[1] == rd

    def test_encode_b_masks_rd(self) -> None:
        assert encode_b(0x08, 0x1F)[1] == 0x0F

    def test_encode_c_length(self) -> None:
        assert len(encode_c(0x13, 0)) == 2

    def test_encode_c_imm8(self) -> None:
        b = encode_c(0x13, 42)
        assert b[0] == 0x13
        assert b[1] == 42

    def test_encode_c_masks(self) -> None:
        b = encode_c(0x13, 0x1FF)
        assert b[1] == 0xFF

    def test_encode_d_length(self) -> None:
        assert len(encode_d(0x18, 1, 42)) == 3

    def test_encode_d_fields(self) -> None:
        b = encode_d(0x18, 5, 100)
        assert b[0] == 0x18
        assert b[1] == 5
        assert b[2] == 100

    def test_encode_d_masks(self) -> None:
        b = encode_d(0x18, 0x1F, 0x1FF)
        assert b[1] == 0x0F
        assert b[2] == 0xFF

    def test_encode_e_length(self) -> None:
        assert len(encode_e(0x20, 1, 2, 3)) == 4

    def test_encode_e_fields(self) -> None:
        b = encode_e(0x20, 5, 6, 7)
        assert b[0] == 0x20
        assert b[1] == 5
        assert b[2] == 6
        assert b[3] == 7

    def test_encode_e_masks(self) -> None:
        b = encode_e(0x20, 0x1F, 0x1F, 0x1F)
        assert b[1] == 0x0F
        assert b[2] == 0x0F
        assert b[3] == 0x0F

    def test_encode_f_length(self) -> None:
        assert len(encode_f(0x40, 1, 1000)) == 4

    def test_encode_f_little_endian(self) -> None:
        b = encode_f(0x40, 1, 0x1234)
        assert b[0] == 0x40
        assert b[1] == 1
        assert b[2] == 0x34
        assert b[3] == 0x12

    def test_encode_f_zero_imm(self) -> None:
        b = encode_f(0x43, 0, 0)
        assert b[2] == 0
        assert b[3] == 0

    def test_encode_g_length(self) -> None:
        assert len(encode_g(0x48, 1, 2, 100)) == 5

    def test_encode_g_fields(self) -> None:
        b = encode_g(0x48, 3, 4, 0xABCD)
        assert b[0] == 0x48
        assert b[1] == 3
        assert b[2] == 4
        assert b[3] == 0xCD
        assert b[4] == 0xAB

    def test_encode_g_little_endian(self) -> None:
        b = encode_g(0x48, 0, 0, 0x0100)
        assert b[3] == 0x00
        assert b[4] == 0x01


# ===========================================================================
# 3. Opcode Table Tests
# ===========================================================================

class TestOpcodeTable:
    """Tests for the opcode format and name tables."""

    def test_all_converged_opcodes_have_formats(self) -> None:
        important = list(range(0x00, 0x04)) + list(range(0x08, 0x10)) + \
                    list(range(0x10, 0x18)) + list(range(0x18, 0x20)) + \
                    list(range(0x20, 0x40)) + list(range(0x40, 0x48)) + \
                    list(range(0x48, 0x50)) + list(range(0x50, 0x60)) + \
                    list(range(0xF0, 0x100))
        for op in important:
            assert op in _OPCODE_FORMATS, f"Opcode 0x{op:02X} missing from format table"

    def test_format_sizes(self) -> None:
        assert FORMAT_SIZES["A"] == 1
        assert FORMAT_SIZES["B"] == 2
        assert FORMAT_SIZES["C"] == 2
        assert FORMAT_SIZES["D"] == 3
        assert FORMAT_SIZES["E"] == 4
        assert FORMAT_SIZES["F"] == 4
        assert FORMAT_SIZES["G"] == 5

    def test_halt_is_format_a(self) -> None:
        assert _OPCODE_FORMATS[0x00] == "A"

    def test_add_is_format_e(self) -> None:
        assert _OPCODE_FORMATS[0x20] == "E"

    def test_mov16_is_format_f(self) -> None:
        assert _OPCODE_FORMATS[0x40] == "F"

    def test_loadoff_is_format_g(self) -> None:
        assert _OPCODE_FORMATS[0x48] == "G"

    def test_opcode_names_non_empty(self) -> None:
        assert len(_OPCODE_NAMES) > 100


# ===========================================================================
# 4. MiniVM System Opcodes
# ===========================================================================

class TestMiniVMSystem:
    """Tests for system opcodes: HALT, NOP, VER, ID, DUMP, ASSERT, HALT_ERR."""

    def test_halt(self, vm: MiniVM) -> None:
        vm.load(encode_a(0x00))
        vm.run()
        assert vm.halted is True
        assert vm.halt_error is False

    def test_nop_then_halt(self, vm: MiniVM) -> None:
        vm.load(encode_a(0x01) + encode_a(0x00))
        vm.run()
        assert vm.halted is True
        assert vm.cycle_count == 2

    def test_ver_sets_r0(self, vm: MiniVM) -> None:
        vm.load(encode_a(0xF5) + encode_a(0x00))
        vm.run()
        assert vm.registers[0] == 2

    def test_id_sets_r0(self, vm: MiniVM) -> None:
        vm.load(encode_a(0xF4) + encode_a(0x00))
        vm.run()
        assert vm.registers[0] == 1

    def test_dump_no_halt(self, vm: MiniVM) -> None:
        vm.load(encode_a(0xF2) + encode_a(0x00))
        vm.run()
        assert vm.halted is True
        assert any("DUMP" in t for t in vm.trace)

    def test_assert_pass(self, vm: MiniVM) -> None:
        vm.load(encode_d(0x18, 0, 42) + encode_a(0xF3) + encode_a(0x00))
        vm.run()
        assert vm.halted is True
        assert vm.halt_error is False

    def test_assert_fail(self, vm: MiniVM) -> None:
        vm.load(encode_a(0xF3))
        vm.run()
        assert vm.halted is True
        assert vm.halt_error is True
        assert vm.flags.error is True

    def test_halt_err(self, vm: MiniVM) -> None:
        vm.load(encode_a(0xF0))
        vm.run()
        assert vm.halted is True
        assert vm.halt_error is True

    def test_illegal(self, vm: MiniVM) -> None:
        vm.load(encode_a(0xFF))
        vm.run()
        assert vm.halted is True
        assert vm.halt_error is True

    def test_clf(self, vm: MiniVM) -> None:
        vm.flags.zero = True
        vm.flags.negative = True
        vm.load(encode_c(0x13, 0) + encode_a(0x00))
        vm.run()
        assert vm.flags.zero is False
        assert vm.flags.negative is False

    def test_clk(self, vm: MiniVM) -> None:
        vm.load(encode_d(0x18, 1, 5) + encode_d(0x18, 1, 5)
                + encode_d(0x18, 1, 5) + encode_a(0xF6) + encode_a(0x00))
        vm.run()
        assert vm.registers[0] >= 0


# ===========================================================================
# 5. MiniVM Register Operations
# ===========================================================================

class TestMiniVMRegisterOps:
    """Tests for INC, DEC, NOT, NEG."""

    def test_inc(self, vm: MiniVM) -> None:
        vm.load(encode_d(0x18, 1, 10) + encode_b(0x08, 1) + encode_a(0x00))
        vm.run()
        assert vm.registers[1] == 11

    def test_inc_overflow(self, vm: MiniVM) -> None:
        vm.load(encode_f(0x40, 1, 0x7FFF) + encode_b(0x08, 1) + encode_a(0x00))
        vm.run()
        assert vm.registers[1] == 0x8000

    def test_dec(self, vm: MiniVM) -> None:
        vm.load(encode_d(0x18, 1, 10) + encode_b(0x09, 1) + encode_a(0x00))
        vm.run()
        assert vm.registers[1] == 9

    def test_not_zero(self, vm: MiniVM) -> None:
        vm.load(encode_d(0x18, 1, 0) + encode_b(0x0A, 1) + encode_a(0x00))
        vm.run()
        assert vm.registers[1] == -1

    def test_not_invert(self, vm: MiniVM) -> None:
        vm.load(encode_d(0x18, 1, 0x0F) + encode_b(0x0A, 1) + encode_a(0x00))
        vm.run()
        assert vm.registers[1] == -16  # ~0x0F = 0xFFFFFFF0

    def test_neg_positive(self, vm: MiniVM) -> None:
        vm.load(encode_d(0x18, 1, 5) + encode_b(0x0B, 1) + encode_a(0x00))
        vm.run()
        assert vm.registers[1] == -5

    def test_neg_zero(self, vm: MiniVM) -> None:
        vm.load(encode_d(0x18, 1, 0) + encode_b(0x0B, 1) + encode_a(0x00))
        vm.run()
        assert vm.registers[1] == 0

    def test_neg_negative(self, vm: MiniVM) -> None:
        # NEG(-128) = 128, then NEG(128) = -128
        vm.load(encode_d(0x18, 1, 0x80) + encode_b(0x0B, 1) + encode_a(0x00))
        vm.run()
        assert vm.registers[1] == 128  # NEG(-128) = 128


# ===========================================================================
# 6. MiniVM Stack Operations
# ===========================================================================

class TestMiniVMStack:
    """Tests for PUSH, POP, RET."""

    def test_push_pop(self, vm: MiniVM) -> None:
        vm.load(
            encode_d(0x18, 1, 42)
            + encode_b(0x0C, 1)
            + encode_d(0x18, 2, 0)
            + encode_b(0x0D, 2)
            + encode_a(0x00)
        )
        vm.run()
        assert vm.registers[2] == 42

    def test_push_pop_order(self, vm: MiniVM) -> None:
        vm.load(
            encode_d(0x18, 1, 10)
            + encode_b(0x0C, 1)
            + encode_d(0x18, 1, 20)
            + encode_b(0x0C, 1)
            + encode_b(0x0D, 2)
            + encode_b(0x0D, 3)
            + encode_a(0x00)
        )
        vm.run()
        assert vm.registers[2] == 20  # LIFO
        assert vm.registers[3] == 10

    def test_ret(self, vm: MiniVM) -> None:
        vm.load(
            encode_f(0x40, 15, 11)  # MOVI16 R15, 11 (return addr)
            + encode_b(0x0C, 15)    # PUSH R15 (bytes 4-5)
            + encode_d(0x18, 1, 99) # MOVI R1, 99 (bytes 6-8)
            + encode_a(0x02)        # RET -> PC = 11 (byte 9)
            + encode_a(0x00)        # padding (byte 10)
            + encode_d(0x18, 1, 0)  # addr 11: MOVI R1, 0 (overwrite)
            + encode_a(0x00)        # HALT
        )
        vm.run()
        assert vm.registers[1] == 0

    def test_pop_empty_stack(self, vm: MiniVM) -> None:
        vm.load(encode_b(0x0D, 1) + encode_a(0x00))
        vm.run()
        assert vm.halt_error is True
        assert vm.flags.error is True


# ===========================================================================
# 7. MiniVM Immediate Operations
# ===========================================================================

class TestMiniVMImmediate:
    """Tests for MOVI, ADDI, SUBI, ANDI, ORI, XORI, SHLI, SHRI."""

    def test_mov_i_zero(self, vm: MiniVM) -> None:
        vm.load(encode_d(0x18, 1, 0) + encode_a(0x00))
        vm.run()
        assert vm.registers[1] == 0

    def test_mov_i_positive(self, vm: MiniVM) -> None:
        vm.load(encode_d(0x18, 1, 42) + encode_a(0x00))
        vm.run()
        assert vm.registers[1] == 42

    def test_mov_i_negative(self, vm: MiniVM) -> None:
        vm.load(encode_d(0x18, 1, 0x80) + encode_a(0x00))
        vm.run()
        assert vm.registers[1] == -128

    def test_addi(self, vm: MiniVM) -> None:
        vm.load(encode_d(0x18, 1, 10) + encode_d(0x19, 1, 20) + encode_a(0x00))
        vm.run()
        assert vm.registers[1] == 30

    def test_subi(self, vm: MiniVM) -> None:
        vm.load(encode_d(0x18, 1, 30) + encode_d(0x1A, 1, 10) + encode_a(0x00))
        vm.run()
        assert vm.registers[1] == 20

    def test_andi(self, vm: MiniVM) -> None:
        vm.load(encode_d(0x18, 1, 0xFF) + encode_d(0x1B, 1, 0x0F) + encode_a(0x00))
        vm.run()
        assert vm.registers[1] == 0x0F

    def test_ori(self, vm: MiniVM) -> None:
        # Use MOVI16 to avoid sign extension of 0xF0
        vm.load(encode_f(0x40, 1, 0xF0) + encode_d(0x1C, 1, 0x0F) + encode_a(0x00))
        vm.run()
        assert vm.registers[1] == 0xFF

    def test_xori(self, vm: MiniVM) -> None:
        vm.load(encode_d(0x18, 1, 0xFF) + encode_d(0x1D, 1, 0xFF) + encode_a(0x00))
        vm.run()
        assert vm.registers[1] == 0
        assert vm.flags.zero is True

    def test_shli(self, vm: MiniVM) -> None:
        vm.load(encode_d(0x18, 1, 1) + encode_d(0x1E, 1, 4) + encode_a(0x00))
        vm.run()
        assert vm.registers[1] == 16

    def test_shri(self, vm: MiniVM) -> None:
        vm.load(encode_d(0x18, 1, 16) + encode_d(0x1F, 1, 2) + encode_a(0x00))
        vm.run()
        assert vm.registers[1] == 4


# ===========================================================================
# 8. MiniVM Arithmetic
# ===========================================================================

class TestMiniVMArithmetic:
    """Tests for ADD, SUB, MUL, DIV, MOD."""

    def test_add_basic(self, vm: MiniVM) -> None:
        vm.load(
            encode_f(0x40, 1, 10) + encode_f(0x40, 2, 20)
            + encode_e(0x20, 3, 1, 2) + encode_a(0x00)
        )
        vm.run()
        assert vm.registers[3] == 30

    def test_add_zero(self, vm: MiniVM) -> None:
        vm.load(
            encode_d(0x18, 1, 0) + encode_f(0x40, 2, 42)
            + encode_e(0x20, 3, 1, 2) + encode_a(0x00)
        )
        vm.run()
        assert vm.registers[3] == 42

    def test_add_negative(self, vm: MiniVM) -> None:
        vm.load(
            encode_f(0x40, 1, (-5) & 0xFFFF) + encode_f(0x40, 2, 3)
            + encode_e(0x20, 3, 1, 2) + encode_a(0x00)
        )
        vm.run()
        assert vm.registers[3] == -2

    def test_sub_basic(self, vm: MiniVM) -> None:
        vm.load(
            encode_f(0x40, 1, 30) + encode_f(0x40, 2, 10)
            + encode_e(0x21, 3, 1, 2) + encode_a(0x00)
        )
        vm.run()
        assert vm.registers[3] == 20

    def test_mul_basic(self, vm: MiniVM) -> None:
        vm.load(
            encode_d(0x18, 1, 6) + encode_d(0x18, 2, 7)
            + encode_e(0x22, 3, 1, 2) + encode_a(0x00)
        )
        vm.run()
        assert vm.registers[3] == 42

    def test_mul_zero(self, vm: MiniVM) -> None:
        vm.load(
            encode_d(0x18, 1, 42) + encode_d(0x18, 2, 0)
            + encode_e(0x22, 3, 1, 2) + encode_a(0x00)
        )
        vm.run()
        assert vm.registers[3] == 0

    def test_div_basic(self, vm: MiniVM) -> None:
        vm.load(
            encode_d(0x18, 1, 42) + encode_d(0x18, 2, 7)
            + encode_e(0x23, 3, 1, 2) + encode_a(0x00)
        )
        vm.run()
        assert vm.registers[3] == 6

    def test_div_negative(self, vm: MiniVM) -> None:
        vm.load(
            encode_f(0x40, 1, (-42) & 0xFFFF) + encode_d(0x18, 2, 7)
            + encode_e(0x23, 3, 1, 2) + encode_a(0x00)
        )
        vm.run()
        assert vm.registers[3] == -6

    def test_div_by_zero(self, vm: MiniVM) -> None:
        vm.load(
            encode_d(0x18, 1, 10) + encode_d(0x18, 2, 0)
            + encode_e(0x23, 3, 1, 2) + encode_a(0x00)
        )
        vm.run()
        assert vm.registers[3] == 0
        assert vm.flags.error is True

    def test_mod_basic(self, vm: MiniVM) -> None:
        vm.load(
            encode_d(0x18, 1, 42) + encode_d(0x18, 2, 10)
            + encode_e(0x24, 3, 1, 2) + encode_a(0x00)
        )
        vm.run()
        assert vm.registers[3] == 2

    def test_mod_by_zero(self, vm: MiniVM) -> None:
        vm.load(
            encode_d(0x18, 1, 10) + encode_d(0x18, 2, 0)
            + encode_e(0x24, 3, 1, 2) + encode_a(0x00)
        )
        vm.run()
        assert vm.registers[3] == 0
        assert vm.flags.error is True

    def test_add_flags_zero(self, vm: MiniVM) -> None:
        vm.load(
            encode_f(0x40, 1, (-5) & 0xFFFF) + encode_d(0x18, 2, 5)
            + encode_e(0x20, 3, 1, 2) + encode_a(0x00)
        )
        vm.run()
        assert vm.flags.zero is True

    def test_add_flags_negative(self, vm: MiniVM) -> None:
        vm.load(
            encode_f(0x40, 1, (-10) & 0xFFFF) + encode_d(0x18, 2, 5)
            + encode_e(0x20, 3, 1, 2) + encode_a(0x00)
        )
        vm.run()
        assert vm.flags.negative is True


# ===========================================================================
# 9. MiniVM Bitwise Operations
# ===========================================================================

class TestMiniVMBitwise:
    """Tests for AND, OR, XOR, SHL, SHR, MIN, MAX."""

    def test_and(self, vm: MiniVM) -> None:
        vm.load(
            encode_d(0x18, 1, 0xFF) + encode_d(0x18, 2, 0x0F)
            + encode_e(0x25, 3, 1, 2) + encode_a(0x00)
        )
        vm.run()
        assert vm.registers[3] == 0x0F

    def test_or(self, vm: MiniVM) -> None:
        # Use MOVI16 to avoid sign extension of 0xF0
        vm.load(
            encode_f(0x40, 1, 0xF0) + encode_d(0x18, 2, 0x0F)
            + encode_e(0x26, 3, 1, 2) + encode_a(0x00)
        )
        vm.run()
        assert vm.registers[3] == 0xFF

    def test_xor(self, vm: MiniVM) -> None:
        vm.load(
            encode_d(0x18, 1, 0xFF) + encode_d(0x18, 2, 0xFF)
            + encode_e(0x27, 3, 1, 2) + encode_a(0x00)
        )
        vm.run()
        assert vm.registers[3] == 0

    def test_shl(self, vm: MiniVM) -> None:
        vm.load(
            encode_d(0x18, 1, 1) + encode_d(0x18, 2, 8)
            + encode_e(0x28, 3, 1, 2) + encode_a(0x00)
        )
        vm.run()
        assert vm.registers[3] == 256

    def test_shr(self, vm: MiniVM) -> None:
        # Use MOVI16 to load 256 (doesn't fit in signed 8-bit immediate)
        vm.load(
            encode_f(0x40, 1, 256) + encode_d(0x18, 2, 8)
            + encode_e(0x29, 3, 1, 2) + encode_a(0x00)
        )
        vm.run()
        assert vm.registers[3] == 1

    def test_min(self, vm: MiniVM) -> None:
        vm.load(
            encode_d(0x18, 1, 3) + encode_d(0x18, 2, 7)
            + encode_e(0x2A, 3, 1, 2) + encode_a(0x00)
        )
        vm.run()
        assert vm.registers[3] == 3

    def test_max(self, vm: MiniVM) -> None:
        vm.load(
            encode_d(0x18, 1, 3) + encode_d(0x18, 2, 7)
            + encode_e(0x2B, 3, 1, 2) + encode_a(0x00)
        )
        vm.run()
        assert vm.registers[3] == 7


# ===========================================================================
# 10. MiniVM Compare Operations
# ===========================================================================

class TestMiniVMCompare:
    """Tests for CMP_EQ, CMP_LT, CMP_GT, CMP_NE."""

    def test_cmp_eq_true(self, vm: MiniVM) -> None:
        vm.load(
            encode_d(0x18, 1, 42) + encode_d(0x18, 2, 42)
            + encode_e(0x2C, 3, 1, 2) + encode_a(0x00)
        )
        vm.run()
        assert vm.registers[3] == 1
        assert vm.flags.zero is True

    def test_cmp_eq_false(self, vm: MiniVM) -> None:
        vm.load(
            encode_d(0x18, 1, 42) + encode_d(0x18, 2, 7)
            + encode_e(0x2C, 3, 1, 2) + encode_a(0x00)
        )
        vm.run()
        assert vm.registers[3] == 0
        assert vm.flags.zero is False

    def test_cmp_lt_true(self, vm: MiniVM) -> None:
        vm.load(
            encode_d(0x18, 1, 3) + encode_d(0x18, 2, 7)
            + encode_e(0x2D, 3, 1, 2) + encode_a(0x00)
        )
        vm.run()
        assert vm.registers[3] == 1
        assert vm.flags.negative is True

    def test_cmp_lt_false(self, vm: MiniVM) -> None:
        vm.load(
            encode_d(0x18, 1, 7) + encode_d(0x18, 2, 3)
            + encode_e(0x2D, 3, 1, 2) + encode_a(0x00)
        )
        vm.run()
        assert vm.registers[3] == 0

    def test_cmp_gt_true(self, vm: MiniVM) -> None:
        vm.load(
            encode_d(0x18, 1, 7) + encode_d(0x18, 2, 3)
            + encode_e(0x2E, 3, 1, 2) + encode_a(0x00)
        )
        vm.run()
        assert vm.registers[3] == 1

    def test_cmp_gt_false(self, vm: MiniVM) -> None:
        vm.load(
            encode_d(0x18, 1, 3) + encode_d(0x18, 2, 7)
            + encode_e(0x2E, 3, 1, 2) + encode_a(0x00)
        )
        vm.run()
        assert vm.registers[3] == 0

    def test_cmp_ne_true(self, vm: MiniVM) -> None:
        vm.load(
            encode_d(0x18, 1, 42) + encode_d(0x18, 2, 7)
            + encode_e(0x2F, 3, 1, 2) + encode_a(0x00)
        )
        vm.run()
        assert vm.registers[3] == 1

    def test_cmp_ne_false(self, vm: MiniVM) -> None:
        vm.load(
            encode_d(0x18, 1, 42) + encode_d(0x18, 2, 42)
            + encode_e(0x2F, 3, 1, 2) + encode_a(0x00)
        )
        vm.run()
        assert vm.registers[3] == 0
        assert vm.flags.zero is True


# ===========================================================================
# 11. MiniVM Float Operations
# ===========================================================================

class TestMiniVMFloat:
    """Tests for ITOF, FTOI, FADD, FSUB, FMUL, FDIV."""

    def test_itof_ftoi_roundtrip(self, vm: MiniVM) -> None:
        vm.load(
            encode_f(0x40, 1, 42)
            + encode_e(0x37, 2, 1, 0)  # ITOF R2, R1
            + encode_e(0x36, 3, 2, 0)  # FTOI R3, R2
            + encode_a(0x00)
        )
        vm.run()
        assert vm.registers[3] == 42

    def test_fadd(self, vm: MiniVM) -> None:
        f1_bits = _float_to_reg(1.0)
        f2_bits = _float_to_reg(2.0)
        expected = _float_to_reg(3.0)
        # Load float bit patterns into registers
        vm.load(
            # Load 1.0 float bit pattern into R1
            encode_f(0x40, 1, f1_bits & 0xFFFF)
            + encode_d(0x18, 2, (f1_bits >> 16) & 0xFF)
            + encode_e(0x3A, 1, 2, 0)  # MOV R1, R2 (combine)
            # Hmm this won't work for 32-bit values... let me use a simpler approach
            + encode_a(0x00)
        )
        # Actually let me just test via ITOF
        vm.load(
            encode_d(0x18, 1, 10)  # R1 = 10
            + encode_e(0x37, 1, 1, 0)  # ITOF R1 (10.0)
            + encode_d(0x18, 2, 20)  # R2 = 20
            + encode_e(0x37, 2, 2, 0)  # ITOF R2 (20.0)
            + encode_e(0x30, 3, 1, 2)  # FADD R3 = R1 + R2
            + encode_e(0x36, 4, 3, 0)  # FTOI R4
            + encode_a(0x00)
        )
        vm.run()
        assert vm.registers[4] == 30

    def test_fsub(self, vm: MiniVM) -> None:
        vm.load(
            encode_d(0x18, 1, 20) + encode_e(0x37, 1, 1, 0)
            + encode_d(0x18, 2, 8) + encode_e(0x37, 2, 2, 0)
            + encode_e(0x31, 3, 1, 2)
            + encode_e(0x36, 4, 3, 0)
            + encode_a(0x00)
        )
        vm.run()
        assert vm.registers[4] == 12

    def test_fmul(self, vm: MiniVM) -> None:
        vm.load(
            encode_d(0x18, 1, 6) + encode_e(0x37, 1, 1, 0)
            + encode_d(0x18, 2, 7) + encode_e(0x37, 2, 2, 0)
            + encode_e(0x32, 3, 1, 2)
            + encode_e(0x36, 4, 3, 0)
            + encode_a(0x00)
        )
        vm.run()
        assert vm.registers[4] == 42

    def test_fdiv(self, vm: MiniVM) -> None:
        vm.load(
            encode_d(0x18, 1, 100) + encode_e(0x37, 1, 1, 0)
            + encode_d(0x18, 2, 4) + encode_e(0x37, 2, 2, 0)
            + encode_e(0x33, 3, 1, 2)
            + encode_e(0x36, 4, 3, 0)
            + encode_a(0x00)
        )
        vm.run()
        assert vm.registers[4] == 25

    def test_fdiv_by_zero(self, vm: MiniVM) -> None:
        vm.load(
            encode_d(0x18, 1, 10) + encode_e(0x37, 1, 1, 0)
            + encode_d(0x18, 2, 0) + encode_e(0x37, 2, 2, 0)
            + encode_e(0x33, 3, 1, 2)
            + encode_a(0x00)
        )
        vm.run()
        assert vm.flags.error is True
        assert vm.registers[3] == 0


# ===========================================================================
# 12. MiniVM Memory Operations
# ===========================================================================

class TestMiniVMMemory:
    """Tests for LOAD, STORE, MOV, SWP."""

    def test_store_load(self, vm: MiniVM) -> None:
        vm.load(
            encode_d(0x18, 1, 42)
            + encode_d(0x18, 2, 10)
            + encode_e(0x39, 1, 2, 0)  # STORE R1 -> mem[R2]
            + encode_d(0x18, 3, 0)
            + encode_e(0x38, 3, 2, 0)  # LOAD R3 <- mem[R2]
            + encode_a(0x00)
        )
        vm.run()
        assert vm.registers[3] == 42
        assert vm.memory[10] == 42

    def test_mov(self, vm: MiniVM) -> None:
        vm.load(encode_d(0x18, 1, 99) + encode_e(0x3A, 2, 1, 0) + encode_a(0x00))
        vm.run()
        assert vm.registers[2] == 99

    def test_swp(self, vm: MiniVM) -> None:
        vm.load(
            encode_d(0x18, 1, 10) + encode_d(0x18, 2, 20)
            + encode_e(0x3B, 1, 2, 0) + encode_a(0x00)
        )
        vm.run()
        assert vm.registers[1] == 20
        assert vm.registers[2] == 10

    def test_store_byte_truncation(self, vm: MiniVM) -> None:
        vm.load(
            encode_f(0x40, 1, 0x1FF)  # MOVI16 R1, 511
            + encode_d(0x18, 2, 5)
            + encode_e(0x39, 1, 2, 0)  # STORE
            + encode_a(0x00)
        )
        vm.run()
        assert vm.memory[5] == 0xFF  # truncated to byte


# ===========================================================================
# 13. MiniVM Control Flow
# ===========================================================================

class TestMiniVMControl:
    """Tests for JMP, JZ, JNZ, JLT, JGT, JAL, CALL, LOOP."""

    def test_jmp(self, vm: MiniVM) -> None:
        vm.load(encode_f(0x43, 0, 3) + encode_a(0x00) + encode_a(0x00) + encode_a(0x00))
        vm.run()
        assert vm.halted is True

    def test_jz_taken(self, vm: MiniVM) -> None:
        # JZ at bytes 7-10, base_pc=11, target=14 (skip MOVI R1, 99 at 11-13)
        vm.load(
            encode_d(0x18, 1, 0)       # 0-2: MOVI R1, 0
            + encode_f(0x40, 4, 14)     # 3-6: MOVI16 R4, 14
            + encode_e(0x3C, 1, 0, 4)  # 7-10: JZ R1 -> PC=14
            + encode_d(0x18, 1, 99)     # 11-13: MOVI R1, 99 (skipped)
            + encode_a(0x00)            # 14: HALT (target)
        )
        vm.run()
        assert vm.halted is True
        assert vm.registers[1] == 0  # MOVI R1, 99 was skipped

    def test_jnz_taken(self, vm: MiniVM) -> None:
        vm.load(
            encode_d(0x18, 1, 42)       # MOVI R1, 42
            + encode_f(0x40, 4, 8)      # MOVI16 R4, 8
            + encode_e(0x3D, 1, 0, 4)  # JNZ R1 -> PC=8
            + encode_d(0x18, 1, 0)      # skipped
            + encode_a(0x00)            # skipped
            + encode_a(0x00)            # skipped
            + encode_a(0x00)            # skipped
            + encode_a(0x00)            # byte 8: HALT
        )
        vm.run()
        assert vm.registers[1] == 42

    def test_jnz_not_taken(self, vm: MiniVM) -> None:
        vm.load(
            encode_d(0x18, 1, 0)        # MOVI R1, 0
            + encode_f(0x40, 4, 100)    # MOVI16 R4, 100
            + encode_e(0x3D, 1, 0, 4)  # JNZ R1 (not taken)
            + encode_d(0x18, 2, 77)     # MOVI R2, 77
            + encode_a(0x00)            # HALT
        )
        vm.run()
        assert vm.registers[2] == 77

    def test_jlt_taken(self, vm: MiniVM) -> None:
        vm.load(
            encode_d(0x18, 1, 3)        # R1 = 3
            + encode_d(0x18, 2, 7)      # R2 = 7
            + encode_f(0x40, 3, 10)     # R3 = 10 (target addr)
            + encode_e(0x3E, 1, 2, 3)  # JLT R1, R2, R3 -> 10
            + encode_d(0x18, 1, 0)      # skipped
            + encode_a(0x00)            # skipped
            + encode_a(0x00)            # skipped
            + encode_a(0x00)            # skipped
            + encode_a(0x00)            # skipped
            + encode_a(0x00)            # skipped
            + encode_a(0x00)            # byte 10: HALT
        )
        vm.run()
        assert vm.registers[1] == 3  # skipped MOVI R1, 0

    def test_loop(self, vm: MiniVM) -> None:
        vm.load(
            encode_d(0x18, 1, 3)    # R1 = 3
            + encode_d(0x18, 2, 0)  # R2 = 0
            # loop at byte 6:
            + encode_b(0x08, 2)     # INC R2 (byte 6-7)
            + encode_f(0x46, 1, 6)  # LOOP R1, 6 (byte 8-11)
            + encode_a(0x00)        # HALT
        )
        vm.run()
        assert vm.registers[1] == 0
        assert vm.registers[2] == 3

    def test_call_ret(self, vm: MiniVM) -> None:
        # CALL pushes return addr (7), jumps to subroutine at 8
        vm.load(
            encode_d(0x18, 1, 10)   # 0-2: R1 = 10
            + encode_f(0x45, 0, 8)  # 3-6: CALL addr 8 (pushes 7, jumps to 8)
            + encode_a(0x00)        # 7: HALT (return here from CALL)
            + encode_d(0x1A, 1, 5)  # 8-10: SUBI R1, 5 -> R1=5
            + encode_a(0x02)        # 11: RET -> back to PC=7 (HALT)
        )
        vm.run()
        assert vm.registers[1] == 5

    def test_loop_zero_iter(self, vm: MiniVM) -> None:
        # LOOP decrements first: R1=0 -> R1=-1 (non-zero), so it loops once.
        # To test a single-iteration loop, use R1=1.
        vm.load(
            encode_d(0x18, 1, 1)    # R1 = 1
            + encode_d(0x18, 2, 0)  # R2 = 0
            + encode_b(0x08, 2)     # INC R2
            + encode_f(0x46, 1, 6)  # LOOP R1, 6 (decrement R1 first, jump if non-zero)
            + encode_a(0x00)        # HALT
        )
        vm.run()
        assert vm.registers[1] == 0  # decremented from 1 to 0
        assert vm.registers[2] == 1  # body executed once


# ===========================================================================
# 14. MiniVM Format F 16-bit
# ===========================================================================

class TestMiniVMFormatF16:
    """Tests for MOVI16, ADDI16, SUBI16."""

    def test_movi16(self, vm: MiniVM) -> None:
        vm.load(encode_f(0x40, 1, 1000) + encode_a(0x00))
        vm.run()
        assert vm.registers[1] == 1000

    def test_movi16_negative(self, vm: MiniVM) -> None:
        vm.load(encode_f(0x40, 1, (-1000) & 0xFFFF) + encode_a(0x00))
        vm.run()
        assert vm.registers[1] == -1000

    def test_movi16_max(self, vm: MiniVM) -> None:
        vm.load(encode_f(0x40, 1, 0x7FFF) + encode_a(0x00))
        vm.run()
        assert vm.registers[1] == 32767

    def test_addi16(self, vm: MiniVM) -> None:
        vm.load(encode_f(0x40, 1, 100) + encode_f(0x41, 1, 200) + encode_a(0x00))
        vm.run()
        assert vm.registers[1] == 300

    def test_subi16(self, vm: MiniVM) -> None:
        vm.load(encode_f(0x40, 1, 300) + encode_f(0x42, 1, 100) + encode_a(0x00))
        vm.run()
        assert vm.registers[1] == 200


# ===========================================================================
# 15. MiniVM Format G
# ===========================================================================

class TestMiniVMFormatG:
    """Tests for LOADOFF, STOREOFF, LOADI, STOREI, COPY, FILL."""

    def test_loadoff(self, vm: MiniVM) -> None:
        vm.load(
            encode_d(0x18, 1, 42)
            + encode_d(0x18, 2, 5)
            + encode_e(0x39, 1, 2, 0)   # STORE R1 -> mem[5]
            + encode_g(0x48, 3, 2, 0)   # LOADOFF R3, [R2+0]
            + encode_a(0x00)
        )
        vm.run()
        assert vm.registers[3] == 42

    def test_storeoff(self, vm: MiniVM) -> None:
        vm.load(
            encode_d(0x18, 1, 77)
            + encode_d(0x18, 2, 10)
            + encode_g(0x49, 1, 2, 0)  # STOREOFF R1, [R2+0]
            + encode_a(0x00)
        )
        vm.run()
        assert vm.memory[10] == 77

    def test_loadi(self, vm: MiniVM) -> None:
        vm.load(
            encode_d(0x18, 1, 55)
            + encode_d(0x18, 2, 8)
            + encode_e(0x39, 1, 2, 0)
            + encode_g(0x4A, 3, 2, 0)  # LOADI R3, [R2]
            + encode_a(0x00)
        )
        vm.run()
        assert vm.registers[3] == 55

    def test_storei(self, vm: MiniVM) -> None:
        vm.load(
            encode_d(0x18, 1, 0xDD)
            + encode_d(0x18, 2, 15)
            + encode_g(0x4B, 1, 2, 0)  # STOREI R1, [R2]
            + encode_a(0x00)
        )
        vm.run()
        assert vm.memory[15] == 0xDD

    def test_fill(self, vm: MiniVM) -> None:
        vm.load(
            encode_d(0x18, 1, 0xAB)
            + encode_d(0x18, 2, 20)
            + encode_g(0x4F, 2, 1, 4)  # FILL addr=20, val=R1(0xAB), count=4
            + encode_a(0x00)
        )
        vm.run()
        for i in range(4):
            assert vm.memory[20 + i] == 0xAB

    def test_copy(self, vm: MiniVM) -> None:
        vm.load(
            encode_d(0x18, 1, 0xCC)
            + encode_d(0x18, 2, 10)
            + encode_e(0x39, 1, 2, 0)  # STORE -> mem[10]
            + encode_g(0x4E, 3, 2, 1)  # COPY dst=0, src=10, count=1
            + encode_a(0x00)
        )
        vm.run()
        assert vm.memory[0] == 0xCC
        assert vm.memory[10] == 0xCC


# ===========================================================================
# 16. MiniVM Extended Math
# ===========================================================================

class TestMiniVMExtendedMath:
    """Tests for ABS, SIGN, SQRT, CLZ, CTZ, POPCNT, LOG2."""

    def test_abs_negative(self, vm: MiniVM) -> None:
        vm.load(encode_f(0x40, 1, (-42) & 0xFFFF) + encode_e(0x90, 2, 1, 0) + encode_a(0x00))
        vm.run()
        assert vm.registers[2] == 42

    def test_abs_positive(self, vm: MiniVM) -> None:
        vm.load(encode_d(0x18, 1, 42) + encode_e(0x90, 2, 1, 0) + encode_a(0x00))
        vm.run()
        assert vm.registers[2] == 42

    def test_sign_neg(self, vm: MiniVM) -> None:
        vm.load(encode_f(0x40, 1, (-5) & 0xFFFF) + encode_e(0x91, 2, 1, 0) + encode_a(0x00))
        vm.run()
        assert vm.registers[2] == -1

    def test_sign_zero(self, vm: MiniVM) -> None:
        vm.load(encode_d(0x18, 1, 0) + encode_e(0x91, 2, 1, 0) + encode_a(0x00))
        vm.run()
        assert vm.registers[2] == 0

    def test_sign_pos(self, vm: MiniVM) -> None:
        vm.load(encode_d(0x18, 1, 7) + encode_e(0x91, 2, 1, 0) + encode_a(0x00))
        vm.run()
        assert vm.registers[2] == 1

    def test_sqrt(self, vm: MiniVM) -> None:
        vm.load(encode_d(0x18, 1, 16) + encode_e(0x92, 2, 1, 0) + encode_a(0x00))
        vm.run()
        assert vm.registers[2] == 4

    def test_sqrt_large(self, vm: MiniVM) -> None:
        vm.load(encode_f(0x40, 1, 100) + encode_e(0x92, 2, 1, 0) + encode_a(0x00))
        vm.run()
        assert vm.registers[2] == 10

    def test_clz_one(self, vm: MiniVM) -> None:
        vm.load(encode_d(0x18, 1, 1) + encode_e(0x95, 2, 1, 0) + encode_a(0x00))
        vm.run()
        assert vm.registers[2] == 31

    def test_clz_zero(self, vm: MiniVM) -> None:
        vm.load(encode_d(0x18, 1, 0) + encode_e(0x95, 2, 1, 0) + encode_a(0x00))
        vm.run()
        assert vm.registers[2] == 32

    def test_ctz_eight(self, vm: MiniVM) -> None:
        vm.load(encode_d(0x18, 1, 8) + encode_e(0x96, 2, 1, 0) + encode_a(0x00))
        vm.run()
        assert vm.registers[2] == 3

    def test_popcnt_ff(self, vm: MiniVM) -> None:
        # Use MOVI16 to avoid sign extension (MOVI would make 0xFF = -1 = 0xFFFFFFFF)
        vm.load(encode_f(0x40, 1, 0xFF) + encode_e(0x97, 2, 1, 0) + encode_a(0x00))
        vm.run()
        assert vm.registers[2] == 8

    def test_popcnt_zero(self, vm: MiniVM) -> None:
        vm.load(encode_d(0x18, 1, 0) + encode_e(0x97, 2, 1, 0) + encode_a(0x00))
        vm.run()
        assert vm.registers[2] == 0

    def test_log2(self, vm: MiniVM) -> None:
        vm.load(encode_d(0x18, 1, 16) + encode_e(0x94, 2, 1, 0) + encode_a(0x00))
        vm.run()
        assert vm.registers[2] == 4

    def test_pow(self, vm: MiniVM) -> None:
        vm.load(encode_d(0x18, 1, 2) + encode_d(0x18, 2, 10) + encode_e(0x93, 3, 1, 2) + encode_a(0x00))
        vm.run()
        assert vm.registers[3] == 1024


# ===========================================================================
# 17. MiniVM Float Extended
# ===========================================================================

class TestMiniVMFloatExtended:
    """Tests for FSQRT, FSIN, FCOS."""

    def test_fsqrt(self, vm: MiniVM) -> None:
        f2 = _float_to_reg(2.0)
        # ITOF converts integer 4 to float 4.0, then FSQRT gives 2.0
        vm.load(
            encode_f(0x40, 1, 4)        # R1 = 4
            + encode_e(0x37, 1, 1, 0)  # ITOF R1 -> 4.0
            + encode_e(0x9D, 2, 1, 0)  # FSQRT R2, R1 -> 2.0
            + encode_a(0x00)
        )
        vm.run()
        assert vm.registers[2] == f2

    def test_fsin(self, vm: MiniVM) -> None:
        f0 = _float_to_reg(0.0)
        vm.load(
            encode_d(0x18, 1, 0) + encode_e(0x37, 1, 1, 0)
            + encode_e(0x9E, 2, 1, 0)  # FSIN
            + encode_a(0x00)
        )
        vm.run()
        assert vm.registers[2] == f0

    def test_fcos(self, vm: MiniVM) -> None:
        f1 = _float_to_reg(1.0)
        vm.load(
            encode_d(0x18, 1, 0) + encode_e(0x37, 1, 1, 0)
            + encode_e(0x9F, 2, 1, 0)  # FCOS(0) = 1.0
            + encode_a(0x00)
        )
        vm.run()
        assert vm.registers[2] == f1


# ===========================================================================
# 18. MiniVM A2A Trace
# ===========================================================================

class TestMiniVMA2A:
    """Tests that A2A opcodes record to the trace log."""

    def test_tell_logs(self, vm: MiniVM) -> None:
        vm.load(encode_e(0x50, 1, 2, 3) + encode_a(0x00))
        vm.run()
        assert len(vm.a2a_log) == 1
        assert vm.a2a_log[0]["mnemonic"] == "TELL"

    def test_ask_logs(self, vm: MiniVM) -> None:
        vm.load(encode_e(0x51, 1, 2, 3) + encode_a(0x00))
        vm.run()
        assert len(vm.a2a_log) == 1
        assert vm.a2a_log[0]["mnemonic"] == "ASK"

    def test_multiple_a2a(self, vm: MiniVM) -> None:
        vm.load(
            encode_e(0x50, 1, 2, 3)  # TELL
            + encode_e(0x52, 1, 2, 3)  # DELEG
            + encode_e(0x58, 1, 2, 3)  # FORK
            + encode_a(0x00)
        )
        vm.run()
        assert len(vm.a2a_log) == 3
        mnemonics = [e["mnemonic"] for e in vm.a2a_log]
        assert "TELL" in mnemonics
        assert "DELEG" in mnemonics
        assert "FORK" in mnemonics

    def test_a2a_no_halt(self, vm: MiniVM) -> None:
        vm.load(encode_e(0x50, 1, 2, 3) + encode_a(0x00))
        vm.run()
        assert vm.halted is True
        assert vm.halt_error is False

    def test_a2a_registers_unchanged(self, vm: MiniVM) -> None:
        vm.load(
            encode_d(0x18, 1, 99)
            + encode_e(0x50, 1, 2, 3)
            + encode_a(0x00)
        )
        vm.run()
        assert vm.registers[1] == 99  # A2A no-ops don't modify registers


# ===========================================================================
# 19. MiniVM Edge Cases
# ===========================================================================

class TestMiniVMEdgeCases:
    """Tests for edge cases: div-by-zero, stack overflow, unknown opcodes."""

    def test_pc_out_of_bounds(self, vm: MiniVM) -> None:
        vm.load(b"")  # empty program
        vm.run()
        assert vm.halted is True
        assert vm.halt_error is True

    def test_unknown_opcode(self, vm: MiniVM) -> None:
        vm.load(bytes([0x05]))  # undefined in Format A range
        vm.run()
        assert vm.halted is True
        assert vm.halt_error is True

    def test_max_instructions(self, vm: MiniVM) -> None:
        # Infinite loop: JMP 0
        from flux_conformance.runner import MAX_INSTRUCTIONS
        vm.load(encode_f(0x43, 0, 0))
        vm.run()
        assert vm.cycle_count >= MAX_INSTRUCTIONS

    def test_flags_cleared_on_reset(self, vm: MiniVM) -> None:
        vm.flags.error = True
        vm.flags.zero = True
        vm.reset()
        assert vm.flags.error is False
        assert vm.flags.zero is False

    def test_registers_cleared_on_reset(self, vm: MiniVM) -> None:
        vm.registers[0] = 999
        vm.reset()
        assert vm.registers[0] == 0

    def test_empty_program(self, vm: MiniVM) -> None:
        vm.load(b"")
        vm.run()
        assert vm.halted is True
        assert vm.halt_error is True

    def test_store_load_different_addresses(self, vm: MiniVM) -> None:
        vm.load(
            encode_d(0x18, 1, 10)
            + encode_d(0x18, 2, 0) + encode_e(0x39, 1, 2, 0)   # mem[0] = 10
            + encode_d(0x18, 1, 20)
            + encode_d(0x18, 2, 1) + encode_e(0x39, 1, 2, 0)   # mem[1] = 20
            + encode_d(0x18, 2, 0)  # R2 = 0 (restore address)
            + encode_d(0x18, 3, 0) + encode_e(0x38, 3, 2, 0)   # R3 = mem[0] = 10
            + encode_d(0x18, 2, 1)  # R2 = 1 (set address for next load)
            + encode_d(0x18, 4, 0) + encode_e(0x38, 4, 2, 0)   # R4 = mem[1] = 20
            + encode_a(0x00)
        )
        vm.run()
        assert vm.registers[3] == 10
        assert vm.registers[4] == 20

    def test_mov_chain(self, vm: MiniVM) -> None:
        vm.load(
            encode_d(0x18, 1, 1)
            + encode_e(0x3A, 2, 1, 0)  # R2 = R1 = 1
            + encode_e(0x3A, 3, 2, 0)  # R3 = R2 = 1
            + encode_e(0x3A, 4, 3, 0)  # R4 = R3 = 1
            + encode_a(0x00)
        )
        vm.run()
        assert vm.registers[4] == 1

    def test_panics(self, vm: MiniVM) -> None:
        vm.load(encode_a(0xFA))
        vm.run()
        assert vm.halted is True
        assert vm.halt_error is True


# ===========================================================================
# 20. MiniVM Integration Programs
# ===========================================================================

class TestMiniVMIntegration:
    """Integration tests with multi-step programs."""

    def test_factorial_5(self, vm: MiniVM) -> None:
        vm.load(
            encode_f(0x40, 1, 5)          # R1 = 5
            + encode_f(0x40, 2, 1)        # R2 = 1
            + encode_e(0x22, 2, 2, 1)     # MUL R2, R2, R1
            + encode_f(0x46, 1, 8)        # LOOP R1, 8
            + encode_a(0x00)
        )
        vm.run()
        assert vm.registers[1] == 0
        assert vm.registers[2] == 120

    def test_sum_1_to_10(self, vm: MiniVM) -> None:
        vm.load(
            encode_f(0x40, 1, 10)         # R1 = 10
            + encode_d(0x18, 2, 0)        # R2 = 0
            + encode_e(0x20, 2, 2, 1)     # ADD R2, R2, R1
            + encode_b(0x09, 1)           # DEC R1
            + encode_f(0x40, 3, 7)        # MOVI16 R3, 7
            + encode_e(0x3D, 1, 0, 3)     # JNZ R1 -> R3
            + encode_a(0x00)
        )
        vm.run()
        assert vm.registers[1] == 0
        assert vm.registers[2] == 55


# ===========================================================================
# 21. VectorGenerator Tests
# ===========================================================================

class TestVectorGenerator:
    """Tests for VectorGenerator."""

    def test_generate_all_returns_list(self, generator: VectorGenerator) -> None:
        vectors = generator.generate_all()
        assert isinstance(vectors, list)

    def test_generate_all_non_empty(self, generator: VectorGenerator) -> None:
        vectors = generator.generate_all()
        assert len(vectors) >= 100

    def test_generate_all_unique_names(self, generator: VectorGenerator) -> None:
        vectors = generator.generate_all()
        names = [v.name for v in vectors]
        assert len(names) == len(set(names)), "Vector names must be unique"

    def test_all_vectors_have_bytecode(self, generator: VectorGenerator) -> None:
        vectors = generator.generate_all()
        for v in vectors:
            assert len(v.bytecode) > 0, f"{v.name} has empty bytecode"

    def test_all_vectors_have_description(self, generator: VectorGenerator) -> None:
        vectors = generator.generate_all()
        for v in vectors:
            assert len(v.description) > 0, f"{v.name} has empty description"

    def test_has_system_vectors(self, generator: VectorGenerator) -> None:
        vectors = generator.generate_all()
        system = [v for v in vectors if v.name.startswith("system/")]
        assert len(system) >= 3

    def test_has_arith_vectors(self, generator: VectorGenerator) -> None:
        vectors = generator.generate_all()
        arith = [v for v in vectors if v.name.startswith("arith/")]
        assert len(arith) >= 5

    def test_has_a2a_vectors(self, generator: VectorGenerator) -> None:
        vectors = generator.generate_all()
        a2a = [v for v in vectors if v.name.startswith("a2a/")]
        assert len(a2a) >= 10

    def test_has_float_vectors(self, generator: VectorGenerator) -> None:
        vectors = generator.generate_all()
        float_vecs = [v for v in vectors if "float" in v.name or v.name.startswith("float/")]
        assert len(float_vecs) >= 2

    def test_has_combined_vectors(self, generator: VectorGenerator) -> None:
        vectors = generator.generate_all()
        combined = [v for v in vectors if v.name.startswith("combined/")]
        assert len(combined) >= 2

    def test_has_control_vectors(self, generator: VectorGenerator) -> None:
        vectors = generator.generate_all()
        ctrl = [v for v in vectors if v.name.startswith("ctrl/")]
        assert len(ctrl) >= 3

    def test_has_edge_case_vectors(self, generator: VectorGenerator) -> None:
        vectors = generator.generate_all()
        edge = [v for v in vectors if v.name.startswith("edge/")]
        assert len(edge) >= 1

    def test_regenerate_is_consistent(self, generator: VectorGenerator) -> None:
        v1 = generator.generate_all()
        v2 = generator.generate_all()
        assert len(v1) == len(v2)
        names1 = [v.name for v in v1]
        names2 = [v.name for v in v2]
        assert names1 == names2


# ===========================================================================
# 22. ConformanceRunner Tests
# ===========================================================================

class TestConformanceRunner:
    """Tests for ConformanceRunner."""

    def test_run_single_passing(self, runner: ConformanceRunner) -> None:
        v = TestVector(
            name="test/halt",
            bytecode=encode_a(0x00),
            expected_halt=True,
        )
        result = runner.run_vector(v)
        assert result.passed is True

    def test_run_single_failing_registers(self, runner: ConformanceRunner) -> None:
        v = TestVector(
            name="test/wrong_reg",
            bytecode=encode_a(0x00),
            expected_registers={0: 42},  # R0 should be 0, not 42
        )
        result = runner.run_vector(v)
        assert result.passed is False
        assert "R0" in result.error_message

    def test_run_single_failing_halt(self, runner: ConformanceRunner) -> None:
        v = TestVector(
            name="test/no_halt",
            bytecode=encode_a(0x01),  # NOP only, no HALT
            expected_halt=True,
        )
        result = runner.run_vector(v)
        assert result.passed is False

    def test_run_single_error_expected(self, runner: ConformanceRunner) -> None:
        v = TestVector(
            name="test/expected_error",
            bytecode=encode_a(0xFF),
            expected_halt=True,
            expected_error=True,
        )
        result = runner.run_vector(v)
        assert result.passed is True

    def test_run_single_error_not_expected(self, runner: ConformanceRunner) -> None:
        v = TestVector(
            name="test/unexpected_error",
            bytecode=encode_a(0xFF),
            expected_halt=True,
            expected_error=False,
        )
        result = runner.run_vector(v)
        assert result.passed is False

    def test_result_has_trace(self, runner: ConformanceRunner) -> None:
        v = TestVector(name="test/trace", bytecode=encode_a(0x00))
        result = runner.run_vector(v)
        assert isinstance(result.execution_trace, list)

    def test_result_has_flags(self, runner: ConformanceRunner) -> None:
        v = TestVector(name="test/flags", bytecode=encode_a(0x00))
        result = runner.run_vector(v)
        assert "zero" in result.actual_flags
        assert "negative" in result.actual_flags
        assert "error" in result.actual_flags

    def test_result_has_registers(self, runner: ConformanceRunner) -> None:
        v = TestVector(name="test/regs", bytecode=encode_a(0x00))
        result = runner.run_vector(v)
        assert len(result.actual_registers) == NUM_REGISTERS

    def test_result_has_memory(self, runner: ConformanceRunner) -> None:
        v = TestVector(name="test/mem", bytecode=encode_a(0x00))
        result = runner.run_vector(v)
        assert len(result.actual_memory) == MEMORY_SIZE

    def test_run_all(self, runner: ConformanceRunner, all_vectors: list[TestVector]) -> None:
        results = runner.run_all(all_vectors)
        assert len(results) == len(all_vectors)
        assert all(isinstance(r, ConformanceResult) for r in results)

    def test_run_all_most_pass(self, runner: ConformanceRunner, all_vectors: list[TestVector]) -> None:
        results = runner.run_all(all_vectors)
        passed = sum(1 for r in results if r.passed)
        assert passed >= len(results) * 0.8, f"Only {passed}/{len(results)} passed"

    def test_memory_check(self, runner: ConformanceRunner) -> None:
        v = TestVector(
            name="test/mem_check",
            bytecode=(
                encode_d(0x18, 1, 42)
                + encode_d(0x18, 2, 10)
                + encode_e(0x39, 1, 2, 0)
                + encode_a(0x00)
            ),
            expected_memory={10: 42},
        )
        result = runner.run_vector(v)
        assert result.passed is True

    def test_flag_check(self, runner: ConformanceRunner) -> None:
        v = TestVector(
            name="test/flag_check",
            bytecode=(
                encode_d(0x18, 1, 0)
                + encode_d(0x18, 2, 0)
                + encode_e(0x2C, 3, 1, 2)
                + encode_a(0x00)
            ),
            expected_flags={"zero": True},
        )
        result = runner.run_vector(v)
        assert result.passed is True

    def test_vm_reset_between_runs(self, runner: ConformanceRunner) -> None:
        v1 = TestVector(
            name="test/reset1",
            bytecode=encode_d(0x18, 1, 99) + encode_a(0x00),
            expected_registers={1: 99},
        )
        v2 = TestVector(
            name="test/reset2",
            bytecode=encode_a(0x00),
            expected_registers={1: 0},  # should be reset
        )
        r1 = runner.run_vector(v1)
        r2 = runner.run_vector(v2)
        assert r1.passed is True
        assert r2.passed is True


# ===========================================================================
# 23. ConformanceReporter Tests
# ===========================================================================

class TestConformanceReporter:
    """Tests for ConformanceReporter."""

    def test_summary_structure(self, runner: ConformanceRunner) -> None:
        results = runner.run_all([
            TestVector(name="a", bytecode=encode_a(0x00)),
            TestVector(name="b", bytecode=encode_d(0x18, 0, 42) + encode_a(0x00),
                      expected_registers={0: 42}),
        ])
        summ = ConformanceReporter.summary(results)
        assert "total" in summ
        assert "passed" in summ
        assert "failed" in summ
        assert "pass_rate" in summ
        assert "categories" in summ

    def test_summary_counts(self, runner: ConformanceRunner) -> None:
        results = runner.run_all([
            TestVector(name="x/a", bytecode=encode_a(0x00)),
            TestVector(name="x/b", bytecode=encode_a(0x00)),
            TestVector(name="y/a", bytecode=encode_a(0x00)),
        ])
        summ = ConformanceReporter.summary(results)
        assert summ["total"] == 3
        assert summ["passed"] == 3
        assert summ["failed"] == 0

    def test_summary_categories(self, runner: ConformanceRunner) -> None:
        results = runner.run_all([
            TestVector(name="sys/a", bytecode=encode_a(0x00)),
            TestVector(name="sys/b", bytecode=encode_a(0x00)),
            TestVector(name="arith/a", bytecode=encode_a(0x00)),
        ])
        summ = ConformanceReporter.summary(results)
        assert "sys" in summ["categories"]
        assert summ["categories"]["sys"]["total"] == 2
        assert "arith" in summ["categories"]

    def test_to_markdown_not_empty(self, runner: ConformanceRunner) -> None:
        results = runner.run_all([
            TestVector(name="test/a", bytecode=encode_a(0x00)),
        ])
        md = ConformanceReporter.to_markdown(results)
        assert len(md) > 0

    def test_to_markdown_contains_header(self, runner: ConformanceRunner) -> None:
        results = runner.run_all([
            TestVector(name="test/a", bytecode=encode_a(0x00)),
        ])
        md = ConformanceReporter.to_markdown(results)
        assert "FLUX Conformance" in md

    def test_to_markdown_contains_table(self, runner: ConformanceRunner) -> None:
        results = runner.run_all([
            TestVector(name="test/a", bytecode=encode_a(0x00)),
        ])
        md = ConformanceReporter.to_markdown(results)
        assert "Category" in md
        assert "Total" in md

    def test_to_json_valid(self, runner: ConformanceRunner) -> None:
        import json
        results = runner.run_all([
            TestVector(name="test/a", bytecode=encode_a(0x00)),
        ])
        json_str = ConformanceReporter.to_json(results)
        data = json.loads(json_str)
        assert "summary" in data
        assert "results" in data

    def test_to_json_contains_summary(self, runner: ConformanceRunner) -> None:
        import json
        results = runner.run_all([
            TestVector(name="test/a", bytecode=encode_a(0x00)),
        ])
        data = json.loads(ConformanceReporter.to_json(results))
        assert data["summary"]["total"] == 1
        assert data["summary"]["passed"] == 1

    def test_to_json_contains_results(self, runner: ConformanceRunner) -> None:
        import json
        results = runner.run_all([
            TestVector(name="test/a", bytecode=encode_a(0x00)),
        ])
        data = json.loads(ConformanceReporter.to_json(results))
        assert len(data["results"]) == 1
        assert data["results"][0]["name"] == "test/a"

    def test_full_suite_report(self, runner: ConformanceRunner, all_vectors: list[TestVector]) -> None:
        results = runner.run_all(all_vectors)
        summ = ConformanceReporter.summary(results)
        assert summ["total"] >= 100
        assert summ["pass_rate"] >= 0.9

    def test_to_markdown_full_suite(self, runner: ConformanceRunner, all_vectors: list[TestVector]) -> None:
        results = runner.run_all(all_vectors)
        md = ConformanceReporter.to_markdown(results)
        assert "Pass Rate" in md

    def test_to_json_full_suite(self, runner: ConformanceRunner, all_vectors: list[TestVector]) -> None:
        import json
        results = runner.run_all(all_vectors)
        json_str = ConformanceReporter.to_json(results)
        data = json.loads(json_str)
        assert data["summary"]["total"] == len(all_vectors)


# ===========================================================================
# 24. TestVector Dataclass Tests
# ===========================================================================

class TestTestVector:
    """Tests for the TestVector dataclass."""

    def test_defaults(self) -> None:
        v = TestVector(name="t", bytecode=b"\x00")
        assert v.expected_halt is True
        assert v.expected_error is False
        assert v.expected_registers == {}
        assert v.expected_memory == {}
        assert v.expected_flags == {}
        assert v.description == ""

    def test_custom_fields(self) -> None:
        v = TestVector(
            name="t",
            bytecode=b"\x00",
            expected_registers={0: 42},
            expected_memory={0: 0xFF},
            expected_flags={"error": True},
            expected_halt=False,
            expected_error=True,
            description="test",
        )
        assert v.expected_registers[0] == 42
        assert v.expected_memory[0] == 0xFF
        assert v.expected_flags["error"] is True
        assert v.expected_halt is False
        assert v.expected_error is True


# ===========================================================================
# 25. ConformanceResult Dataclass Tests
# ===========================================================================

class TestConformanceResult:
    """Tests for the ConformanceResult dataclass."""

    def test_defaults(self) -> None:
        r = ConformanceResult(vector_name="t", passed=True)
        assert r.passed is True
        assert r.halted is False
        assert r.halt_error is False
        assert r.error_message == ""
        assert r.execution_trace == []
        assert r.a2a_log == []


# ===========================================================================
# 26. Flags Tests
# ===========================================================================

class TestFlags:
    """Tests for the Flags dataclass."""

    def test_default_flags(self) -> None:
        f = Flags()
        assert f.zero is False
        assert f.negative is False
        assert f.overflow is False
        assert f.carry is False
        assert f.error is False

    def test_clear(self) -> None:
        f = Flags()
        f.zero = True
        f.error = True
        f.clear()
        assert f.zero is False
        assert f.error is False

    def test_update_arithmetic_zero(self) -> None:
        f = Flags()
        f.update_arithmetic(0, 5, -5)
        assert f.zero is True

    def test_update_arithmetic_negative(self) -> None:
        f = Flags()
        f.update_arithmetic(-3, 5, 8, is_sub=True)
        assert f.negative is True

    def test_update_arithmetic_positive(self) -> None:
        f = Flags()
        f.update_arithmetic(10, 5, 5)
        assert f.zero is False
        assert f.negative is False


# ===========================================================================
# 27. MiniVM State Tests
# ===========================================================================

class TestMiniVMState:
    """Tests for VM state management."""

    def test_initial_state(self, vm: MiniVM) -> None:
        assert vm.pc == 0
        assert vm.halted is False
        assert vm.cycle_count == 0
        assert len(vm.stack) == 0

    def test_load_resets(self, vm: MiniVM) -> None:
        vm.registers[0] = 999
        vm.load(encode_a(0x00))
        assert vm.registers[0] == 0
        assert vm.pc == 0

    def test_reset_clears_trace(self, vm: MiniVM) -> None:
        vm.load(encode_a(0x00))
        vm.run()
        assert len(vm.trace) > 0
        vm.reset()
        assert len(vm.trace) == 0

    def test_reset_clears_a2a(self, vm: MiniVM) -> None:
        vm.load(encode_e(0x50, 1, 2, 3) + encode_a(0x00))
        vm.run()
        assert len(vm.a2a_log) > 0
        vm.reset()
        assert len(vm.a2a_log) == 0

    def test_memory_size(self, vm: MiniVM) -> None:
        assert len(vm.memory) == MEMORY_SIZE

    def test_register_count(self, vm: MiniVM) -> None:
        assert len(vm.registers) == NUM_REGISTERS
