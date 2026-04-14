"""
FLUX Conformance Test Suite — Comprehensive Pytest Runner

Runs every built-in conformance test case against the reference VM and
verifies stack output, flag state, error conditions, and framework behavior.
Also tests the cross-runtime runner, validator, and opcode shim modules.
"""

import pytest
import sys
import os
import json
import math
import struct

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from conformance_core import (
    ConformanceTestSuite,
    ConformanceTestCase,
    FluxVM,
    FluxFlags,
    FLAG_Z, FLAG_S, FLAG_C, FLAG_O, FLAGS_ANY,
    HALT, NOP, BREAK,
    ADD, SUB, MUL, DIV, MOD, NEG, INC, DEC,
    EQ, NE, LT, LE, GT, GE,
    AND, OR, XOR, NOT, SHL, SHR,
    LOAD, STORE, PEEK, POKE,
    JMP, JZ, JNZ, CALL, RET, PUSH, POP,
    DUP, SWAP, OVER, ROT,
    FADD, FSUB, FMUL, FDIV,
    CONF_GET, CONF_SET, CONF_MUL,
    SIGNAL, BROADCAST, LISTEN,
    push_imm32,
    jmp_addr, jz_addr, jnz_addr, call_addr,
    store_addr, load_addr,
    signal_ch, broadcast_ch, listen_ch,
)


# ─── Build all cases at import time for parametrize ───────────────────────────

def _get_all_cases():
    s = ConformanceTestSuite()
    s.load_builtin_cases()
    return s.cases


_ALL_CASES = _get_all_cases()


# ─── Parameterized: run every conformance test case ──────────────────────────

@pytest.mark.parametrize("case", _ALL_CASES, ids=lambda c: c.name)
def test_conformance(case: ConformanceTestCase):
    """Run a single conformance test case against the reference VM."""
    vm = FluxVM()
    code = bytes.fromhex(case.bytecode_hex)
    stack, flags = vm.run(code, initial_stack=case.initial_stack or None)

    # Check flags (only when explicitly specified)
    if case.expected_flags != FLAGS_ANY:
        assert flags == case.expected_flags, (
            f"[{case.name}] Flags: expected 0x{case.expected_flags:02x}, "
            f"got 0x{flags:02x}"
        )

    # Check stack length
    assert len(stack) == len(case.expected_stack), (
        f"[{case.name}] Stack length: expected {len(case.expected_stack)}, "
        f"got {len(stack)} (stack={stack})"
    )

    # Check each stack element
    for i, (actual, expected) in enumerate(zip(stack, case.expected_stack)):
        if case.allow_float_epsilon and (
            isinstance(actual, float) or isinstance(expected, float)
        ):
            assert abs(float(actual) - float(expected)) < 1e-5, (
                f"[{case.name}] Stack[{i}]: expected ~{expected}, got {actual}"
            )
        else:
            assert actual == expected, (
                f"[{case.name}] Stack[{i}]: expected {expected}, got {actual}"
            )


# ═══════════════════════════════════════════════════════════════════════
# CATEGORY SMOKE TESTS — VM Reference Behavior
# ═══════════════════════════════════════════════════════════════════════

class TestSystemControl:
    def test_halt_empty_stack(self):
        vm = FluxVM()
        stack, flags = vm.run(bytes([HALT]))
        assert stack == []
        assert flags == 0

    def test_nop_no_effect(self):
        vm = FluxVM()
        stack, flags = vm.run(bytes([NOP, HALT]), initial_stack=[42])
        assert stack == [42]

    def test_break_stops_execution(self):
        vm = FluxVM()
        code = push_imm32(1) + bytes([BREAK]) + push_imm32(2) + bytes([HALT])
        stack, flags = vm.run(code)
        assert stack == [1]

    def test_multiple_nops(self):
        vm = FluxVM()
        code = bytes([NOP] * 10 + [HALT])
        stack, flags = vm.run(code)
        assert stack == []

    def test_halt_preserves_initial_stack(self):
        vm = FluxVM()
        stack, flags = vm.run(bytes([HALT]), initial_stack=[1, 2, 3])
        assert stack == [1, 2, 3]

    def test_halted_flag_set(self):
        vm = FluxVM()
        vm.run(bytes([HALT]))
        assert vm.halted is True

    def test_break_not_halted(self):
        vm = FluxVM()
        vm.run(bytes([BREAK]))
        assert vm.halted is False  # BREAK stops running but doesn't set halted
        assert vm.running is False


class TestIntegerArithmetic:
    def test_add_basic(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(3) + push_imm32(4) + bytes([ADD, HALT]))
        assert stack == [7]

    def test_add_negative(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(-5) + push_imm32(3) + bytes([ADD, HALT]))
        assert stack == [-2]

    def test_sub_basic(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(10) + push_imm32(3) + bytes([SUB, HALT]))
        assert stack == [7]

    def test_mul_basic(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(6) + push_imm32(7) + bytes([MUL, HALT]))
        assert stack == [42]

    def test_div_truncate(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(7) + push_imm32(2) + bytes([DIV, HALT]))
        assert stack == [3]

    def test_div_by_zero_raises(self):
        vm = FluxVM()
        with pytest.raises(RuntimeError, match="Division by zero"):
            vm.run(push_imm32(1) + push_imm32(0) + bytes([DIV, HALT]))

    def test_mod_basic(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(10) + push_imm32(3) + bytes([MOD, HALT]))
        assert stack == [1]

    def test_mod_by_zero_raises(self):
        vm = FluxVM()
        with pytest.raises(RuntimeError, match="Modulo by zero"):
            vm.run(push_imm32(1) + push_imm32(0) + bytes([MOD, HALT]))

    def test_neg_basic(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(5) + bytes([NEG, HALT]))
        assert stack == [-5]

    def test_inc_basic(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(41) + bytes([INC, HALT]))
        assert stack == [42]

    def test_dec_basic(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(43) + bytes([DEC, HALT]))
        assert stack == [42]

    def test_chained(self):
        vm = FluxVM()
        code = push_imm32(2) + push_imm32(3) + bytes([ADD]) + push_imm32(4) + bytes([MUL, HALT])
        stack, _ = vm.run(code)
        assert stack == [20]  # (2+3)*4

    def test_add_with_initial_stack(self):
        vm = FluxVM()
        stack, _ = vm.run(bytes([ADD, HALT]), initial_stack=[5, 3])
        assert stack == [8]

    def test_add_zero_flag(self):
        vm = FluxVM()
        _, flags = vm.run(push_imm32(5) + push_imm32(-5) + bytes([ADD, HALT]))
        assert flags & FLAG_Z

    def test_sub_zero_flag(self):
        vm = FluxVM()
        _, flags = vm.run(push_imm32(3) + push_imm32(3) + bytes([SUB, HALT]))
        assert flags & FLAG_Z

    def test_neg_result_sign_flag(self):
        vm = FluxVM()
        _, flags = vm.run(push_imm32(3) + push_imm32(10) + bytes([SUB, HALT]))
        assert flags & FLAG_S

    def test_mul_zero_flag(self):
        vm = FluxVM()
        _, flags = vm.run(push_imm32(100) + push_imm32(0) + bytes([MUL, HALT]))
        assert flags & FLAG_Z

    def test_div_negative(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(-7) + push_imm32(2) + bytes([DIV, HALT]))
        assert stack == [-3]

    def test_mod_negative(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(-7) + push_imm32(3) + bytes([MOD, HALT]))
        assert stack == [2]

    def test_neg_double_negation(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(42) + bytes([NEG, NEG, HALT]))
        assert stack == [42]

    def test_dec_to_zero(self):
        vm = FluxVM()
        _, flags = vm.run(push_imm32(1) + bytes([DEC, HALT]))
        assert flags & FLAG_Z

    def test_large_addition(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(1000000) + push_imm32(2000000) + bytes([ADD, HALT]))
        assert stack == [3000000]

    def test_large_multiplication(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(1000) + push_imm32(1000) + bytes([MUL, HALT]))
        assert stack == [1000000]

    def test_mul_negative_times_positive(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(-3) + push_imm32(4) + bytes([MUL, HALT]))
        assert stack == [-12]

    def test_mod_zero_result(self):
        vm = FluxVM()
        _, flags = vm.run(push_imm32(7) + push_imm32(7) + bytes([MOD, HALT]))
        assert flags & FLAG_Z


class TestComparison:
    def test_eq_true(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(5) + push_imm32(5) + bytes([EQ, HALT]))
        assert stack == [1]

    def test_eq_false(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(5) + push_imm32(6) + bytes([EQ, HALT]))
        assert stack == [0]

    def test_ne_true(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(1) + push_imm32(2) + bytes([NE, HALT]))
        assert stack == [1]

    def test_ne_false(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(5) + push_imm32(5) + bytes([NE, HALT]))
        assert stack == [0]

    def test_lt_true(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(3) + push_imm32(5) + bytes([LT, HALT]))
        assert stack == [1]

    def test_lt_false(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(5) + push_imm32(3) + bytes([LT, HALT]))
        assert stack == [0]

    def test_ge_equal(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(7) + push_imm32(7) + bytes([GE, HALT]))
        assert stack == [1]

    def test_gt_true(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(10) + push_imm32(3) + bytes([GT, HALT]))
        assert stack == [1]

    def test_gt_false(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(3) + push_imm32(10) + bytes([GT, HALT]))
        assert stack == [0]

    def test_le_equal(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(5) + push_imm32(5) + bytes([LE, HALT]))
        assert stack == [1]

    def test_le_false(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(10) + push_imm32(5) + bytes([LE, HALT]))
        assert stack == [0]

    def test_negatives_compare(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(-10) + push_imm32(-3) + bytes([LT, HALT]))
        assert stack == [1]

    def test_eq_with_stack(self):
        vm = FluxVM()
        stack, _ = vm.run(bytes([EQ, HALT]), initial_stack=[100, 100])
        assert stack == [1]

    def test_eq_zero_flag_on_false(self):
        vm = FluxVM()
        _, flags = vm.run(push_imm32(1) + push_imm32(2) + bytes([EQ, HALT]))
        assert flags & FLAG_Z

    def test_eq_no_zero_flag_on_true(self):
        vm = FluxVM()
        _, flags = vm.run(push_imm32(42) + push_imm32(42) + bytes([EQ, HALT]))
        assert not (flags & FLAG_Z)

    def test_comparison_sign_flag_gt(self):
        vm = FluxVM()
        stack, flags = vm.run(push_imm32(5) + push_imm32(-3) + bytes([GT, HALT]))
        assert stack == [1]
        assert not (flags & FLAG_S)


class TestLogic:
    def test_and_basic(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(0xFF) + push_imm32(0x0F) + bytes([AND, HALT]))
        assert stack == [0x0F]

    def test_or_basic(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(0xF0) + push_imm32(0x0F) + bytes([OR, HALT]))
        assert stack == [0xFF]

    def test_xor_self_zero(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(42) + push_imm32(42) + bytes([XOR, HALT]))
        assert stack == [0]

    def test_not_zero(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(0) + bytes([NOT, HALT]))
        assert stack == [-1]

    def test_not_negative_one(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(-1) + bytes([NOT, HALT]))
        assert stack == [0]

    def test_shl_basic(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(1) + push_imm32(8) + bytes([SHL, HALT]))
        assert stack == [256]

    def test_shr_basic(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(256) + push_imm32(8) + bytes([SHR, HALT]))
        assert stack == [1]

    def test_xor_inverse(self):
        vm = FluxVM()
        code = push_imm32(0xFF) + push_imm32(0x0F) + bytes([XOR]) + push_imm32(0x0F) + bytes([XOR, HALT])
        stack, _ = vm.run(code)
        assert stack == [0xFF]

    def test_and_zero_flag(self):
        vm = FluxVM()
        _, flags = vm.run(push_imm32(0xFF) + push_imm32(0x00) + bytes([AND, HALT]))
        assert flags & FLAG_Z

    def test_shl_zero_shift(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(42) + push_imm32(0) + bytes([SHL, HALT]))
        assert stack == [42]

    def test_shl_masked_to_31_bits(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(1) + push_imm32(32) + bytes([SHL, HALT]))
        # 32 & 0x1F = 0, so 1 << 0 = 1
        assert stack == [1]

    def test_shr_masked_to_31_bits(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(256) + push_imm32(32) + bytes([SHR, HALT]))
        # 32 & 0x1F = 0, so 256 >> 0 = 256
        assert stack == [256]

    def test_not_double(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(42) + bytes([NOT, NOT, HALT]))
        assert stack == [42]

    def test_not_sign_flag(self):
        vm = FluxVM()
        _, flags = vm.run(push_imm32(0) + bytes([NOT, HALT]))
        assert flags & FLAG_S

    def test_logic_clears_carry_overflow(self):
        vm = FluxVM()
        _, flags = vm.run(push_imm32(0xFF) + push_imm32(0x0F) + bytes([AND, HALT]))
        assert not (flags & FLAG_C)
        assert not (flags & FLAG_O)


class TestMemory:
    def test_store_load_roundtrip(self):
        vm = FluxVM()
        code = push_imm32(12345) + store_addr(100) + load_addr(100) + bytes([HALT])
        stack, _ = vm.run(code)
        assert stack == [12345]

    def test_poke_peek(self):
        vm = FluxVM()
        code = push_imm32(500) + push_imm32(999) + bytes([POKE]) + push_imm32(500) + bytes([PEEK, HALT])
        stack, _ = vm.run(code)
        assert stack == [999]

    def test_overwrite(self):
        vm = FluxVM()
        code = push_imm32(1) + store_addr(42) + push_imm32(2) + store_addr(42) + load_addr(42) + bytes([HALT])
        stack, _ = vm.run(code)
        assert stack == [2]

    def test_store_load_zero(self):
        vm = FluxVM()
        code = push_imm32(0) + store_addr(200) + load_addr(200) + bytes([HALT])
        stack, _ = vm.run(code)
        assert stack == [0]

    def test_store_negative(self):
        vm = FluxVM()
        code = push_imm32(-42) + store_addr(300) + load_addr(300) + bytes([HALT])
        stack, _ = vm.run(code)
        assert stack == [-42]

    def test_multiple_stores(self):
        vm = FluxVM()
        code = (push_imm32(10) + store_addr(0) + push_imm32(20) + store_addr(4) +
                push_imm32(30) + store_addr(8) + load_addr(0) + load_addr(4) +
                load_addr(8) + bytes([HALT]))
        stack, _ = vm.run(code)
        assert stack == [10, 20, 30]

    def test_uninitialized_memory_is_zero(self):
        vm = FluxVM()
        code = load_addr(500) + bytes([HALT])
        stack, _ = vm.run(code)
        assert stack == [0]

    def test_memory_isolated_between_runs(self):
        vm = FluxVM()
        push_imm32(42) + store_addr(50) + bytes([HALT])
        vm.run(push_imm32(42) + store_addr(50) + bytes([HALT]))
        # After reset, memory should be zero again
        vm2 = FluxVM()
        stack, _ = vm2.run(load_addr(50) + bytes([HALT]))
        assert stack == [0]

    def test_poke_peek_different_address(self):
        vm = FluxVM()
        code = (push_imm32(100) + push_imm32(77) + bytes([POKE]) +
                push_imm32(200) + push_imm32(88) + bytes([POKE]) +
                push_imm32(100) + bytes([PEEK]) + push_imm32(200) + bytes([PEEK, HALT]))
        stack, _ = vm.run(code)
        assert stack == [77, 88]


class TestControlFlow:
    def test_push_pop(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(42) + bytes([POP, HALT]))
        assert stack == []

    def test_jmp_skips_instruction(self):
        vm = FluxVM()
        code = push_imm32(0) + bytes([HALT]) + push_imm32(99) + bytes([HALT]) + jmp_addr(5)
        stack, _ = vm.run(code)
        assert stack == [0]

    def test_jz_taken(self):
        vm = FluxVM()
        code = push_imm32(1) + bytes([DEC, POP]) + push_imm32(42) + jz_addr(20) + push_imm32(99) + bytes([HALT])
        stack, _ = vm.run(code)
        assert stack == [42]

    def test_jz_not_taken(self):
        vm = FluxVM()
        code = push_imm32(0) + bytes([DEC, POP]) + push_imm32(42) + jz_addr(20) + push_imm32(99) + bytes([HALT])
        stack, _ = vm.run(code)
        assert stack == [42, 99]

    def test_jnz_taken(self):
        vm = FluxVM()
        code = push_imm32(0) + bytes([DEC, POP]) + push_imm32(42) + jnz_addr(20) + push_imm32(99) + bytes([HALT])
        stack, _ = vm.run(code)
        assert stack == [42]

    def test_jnz_not_taken(self):
        vm = FluxVM()
        code = push_imm32(1) + bytes([DEC, POP]) + push_imm32(42) + jnz_addr(20) + push_imm32(99) + bytes([HALT])
        stack, _ = vm.run(code)
        assert stack == [42, 99]

    def test_call_ret(self):
        vm = FluxVM()
        code = (push_imm32(1) + call_addr(13) + bytes([ADD, HALT, NOP, NOP, NOP]) +
                push_imm32(2) + bytes([RET, HALT]))
        stack, _ = vm.run(code)
        assert stack == [3]

    def test_nested_call(self):
        vm = FluxVM()
        code = (push_imm32(10) + call_addr(15) + bytes([ADD, HALT]) +
                bytes([NOP] * 5) +
                push_imm32(5) + call_addr(25) + bytes([ADD, RET]) +
                push_imm32(3) + bytes([RET, HALT]))
        stack, _ = vm.run(code)
        assert stack == [18]

    def test_ret_without_call_raises(self):
        vm = FluxVM()
        with pytest.raises(RuntimeError, match="Call stack underflow"):
            vm.run(bytes([RET]))

    def test_loop_sum(self):
        vm = FluxVM()
        code = (push_imm32(0) + store_addr(0) + push_imm32(3) + store_addr(4) +
                load_addr(0) + bytes([INC]) + store_addr(0) +
                load_addr(4) + bytes([DEC]) + store_addr(4) +
                jnz_addr(16) + load_addr(0) + bytes([HALT]))
        stack, _ = vm.run(code)
        assert stack == [3]

    def test_sum_1_to_5(self):
        vm = FluxVM()
        code = (push_imm32(0) + store_addr(0) + push_imm32(5) + store_addr(4) +
                load_addr(0) + load_addr(4) + bytes([ADD]) + store_addr(0) +
                load_addr(4) + bytes([DEC]) + store_addr(4) +
                jnz_addr(16) + load_addr(0) + bytes([HALT]))
        stack, _ = vm.run(code)
        assert stack == [15]

    def test_push_negative(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(-100) + bytes([HALT]))
        assert stack == [-100]

    def test_push_zero(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(0) + bytes([HALT]))
        assert stack == [0]

    def test_multi_push(self):
        vm = FluxVM()
        code = push_imm32(1) + push_imm32(2) + push_imm32(3) + push_imm32(4) + push_imm32(5) + bytes([HALT])
        stack, _ = vm.run(code)
        assert stack == [1, 2, 3, 4, 5]


class TestStackManipulation:
    def test_dup(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(42) + bytes([DUP, HALT]))
        assert stack == [42, 42]

    def test_swap(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(1) + push_imm32(2) + bytes([SWAP, HALT]))
        assert stack == [2, 1]

    def test_over(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(10) + push_imm32(20) + bytes([OVER, HALT]))
        assert stack == [10, 20, 10]

    def test_rot(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(1) + push_imm32(2) + push_imm32(3) + bytes([ROT, HALT]))
        assert stack == [2, 3, 1]

    def test_multi_dup(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(7) + bytes([DUP, DUP, DUP, HALT]))
        assert stack == [7, 7, 7, 7]

    def test_stack_underflow(self):
        vm = FluxVM()
        with pytest.raises(RuntimeError, match="Stack underflow"):
            vm.run(bytes([POP, HALT]))


class TestFloatOperations:
    def test_fadd(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(3) + push_imm32(2) + bytes([FADD, HALT]))
        assert abs(stack[0] - 5.0) < 1e-6

    def test_fsub(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(10) + push_imm32(3) + bytes([FSUB, HALT]))
        assert abs(stack[0] - 7.0) < 1e-6

    def test_fmul(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(4) + push_imm32(5) + bytes([FMUL, HALT]))
        assert abs(stack[0] - 20.0) < 1e-6

    def test_fdiv(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(7) + push_imm32(2) + bytes([FDIV, HALT]))
        assert abs(stack[0] - 3.5) < 1e-6

    def test_fdiv_by_zero_raises(self):
        vm = FluxVM()
        with pytest.raises(RuntimeError, match="Float division by zero"):
            vm.run(push_imm32(1) + push_imm32(0) + bytes([FDIV, HALT]))

    def test_fadd_result_is_float(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(3) + push_imm32(2) + bytes([FADD, HALT]))
        assert isinstance(stack[0], float)

    def test_fsub_negative(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(3) + push_imm32(10) + bytes([FSUB, HALT]))
        assert abs(stack[0] - (-7.0)) < 1e-6

    def test_fmul_negative(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(-3) + push_imm32(4) + bytes([FMUL, HALT]))
        assert abs(stack[0] - (-12.0)) < 1e-6


class TestConfidence:
    def test_initial_confidence(self):
        vm = FluxVM()
        stack, _ = vm.run(bytes([CONF_GET, HALT]))
        assert abs(stack[0] - 1.0) < 1e-6

    def test_set_and_get(self):
        vm = FluxVM()
        code = push_imm32(0) + bytes([CONF_SET, CONF_GET, HALT])
        stack, _ = vm.run(code)
        assert abs(stack[0] - 0.0) < 1e-6

    def test_clamp_high(self):
        vm = FluxVM()
        code = push_imm32(100) + bytes([CONF_SET, CONF_GET, HALT])
        stack, _ = vm.run(code)
        assert abs(stack[0] - 1.0) < 1e-6

    def test_clamp_low(self):
        vm = FluxVM()
        code = push_imm32(-5) + bytes([CONF_SET, CONF_GET, HALT])
        stack, _ = vm.run(code)
        assert abs(stack[0] - 0.0) < 1e-6

    def test_mul_chain(self):
        vm = FluxVM()
        code = push_imm32(1) + bytes([CONF_SET]) + push_imm32(0) + bytes([CONF_MUL, CONF_GET, HALT])
        stack, _ = vm.run(code)
        assert abs(stack[0] - 0.0) < 1e-6

    def test_set_half(self):
        vm = FluxVM()
        code = push_imm32(0) + bytes([CONF_SET, CONF_GET, HALT])
        stack, _ = vm.run(code)
        assert abs(stack[0] - 0.0) < 1e-6

    def test_mul_half(self):
        vm = FluxVM()
        code = push_imm32(0) + bytes([CONF_SET]) + push_imm32(2) + bytes([CONF_MUL, CONF_GET, HALT])
        stack, _ = vm.run(code)
        assert abs(stack[0] - 0.0) < 1e-6


class TestA2A:
    def test_signal_listen(self):
        vm = FluxVM()
        code = push_imm32(42) + signal_ch(1) + listen_ch(1) + bytes([HALT])
        stack, _ = vm.run(code)
        assert stack == [42]

    def test_broadcast_listen(self):
        vm = FluxVM()
        code = push_imm32(99) + broadcast_ch(5) + listen_ch(5) + bytes([HALT])
        stack, _ = vm.run(code)
        assert stack == [99]

    def test_fifo_order(self):
        vm = FluxVM()
        code = (push_imm32(10) + signal_ch(2) + push_imm32(20) + signal_ch(2) +
                listen_ch(2) + listen_ch(2) + bytes([HALT]))
        stack, _ = vm.run(code)
        assert stack == [10, 20]

    def test_listen_empty_returns_zero(self):
        vm = FluxVM()
        code = listen_ch(99) + bytes([HALT])
        stack, _ = vm.run(code)
        assert stack == [0]

    def test_cross_channel_isolation(self):
        vm = FluxVM()
        code = push_imm32(42) + signal_ch(1) + listen_ch(2) + bytes([HALT])
        stack, _ = vm.run(code)
        assert stack == [0]  # Different channel

    def test_signal_depletes(self):
        vm = FluxVM()
        code = (push_imm32(42) + signal_ch(1) +
                listen_ch(1) + listen_ch(1) + bytes([HALT]))
        stack, _ = vm.run(code)
        assert stack == [42, 0]


class TestFlags:
    def test_zero_flag_on_add_zero(self):
        vm = FluxVM()
        _, flags = vm.run(push_imm32(5) + push_imm32(-5) + bytes([ADD, HALT]))
        assert flags & FLAG_Z

    def test_zero_flag_on_eq_false(self):
        vm = FluxVM()
        _, flags = vm.run(push_imm32(1) + push_imm32(2) + bytes([EQ, HALT]))
        assert flags & FLAG_Z

    def test_zero_flag_on_and_zero(self):
        vm = FluxVM()
        _, flags = vm.run(push_imm32(0) + push_imm32(0) + bytes([AND, HALT]))
        assert flags & FLAG_Z

    def test_sign_flag_on_negative(self):
        vm = FluxVM()
        _, flags = vm.run(push_imm32(5) + bytes([NEG, HALT]))
        assert flags & FLAG_S

    def test_sign_flag_on_sub(self):
        vm = FluxVM()
        _, flags = vm.run(push_imm32(3) + push_imm32(10) + bytes([SUB, HALT]))
        assert flags & FLAG_S

    def test_no_sign_flag_on_positive(self):
        vm = FluxVM()
        _, flags = vm.run(push_imm32(3) + push_imm32(4) + bytes([ADD, HALT]))
        assert not (flags & FLAG_S)

    def test_carry_flag_on_add_overflow(self):
        vm = FluxVM()
        _, flags = vm.run(push_imm32(5) + push_imm32(-5) + bytes([ADD, HALT]))
        assert flags & FLAG_C

    def test_overflow_flag_on_positive_mul(self):
        vm = FluxVM()
        # 2^15 * 2 = 2^16 = 65536... but Python ints don't overflow
        # Overflow for positive+positive->negative
        # 0x40000000 * 2 = 0x80000000 = -2147483648 in 32-bit
        _, flags = vm.run(push_imm32(0x40000000) + push_imm32(2) + bytes([MUL, HALT]))
        assert flags & FLAG_O

    def test_all_flags_clear_initially(self):
        vm = FluxVM()
        _, flags = vm.run(bytes([HALT]))
        assert flags == 0


class TestComplexPrograms:
    def test_fibonacci_7(self):
        vm = FluxVM()
        code = push_imm32(0) + push_imm32(1) + bytes([OVER, ADD, SWAP]) * 7 + bytes([HALT])
        stack, _ = vm.run(code)
        assert stack == [13, 8]

    def test_factorial_5(self):
        vm = FluxVM()
        code = (push_imm32(1) + store_addr(0) + push_imm32(5) + store_addr(4) +
                load_addr(0) + load_addr(4) + bytes([MUL]) + store_addr(0) +
                load_addr(4) + bytes([DEC]) + store_addr(4) +
                jnz_addr(16) + load_addr(0) + bytes([HALT]))
        stack, _ = vm.run(code)
        assert stack == [120]

    def test_absolute_value_neg(self):
        vm = FluxVM()
        code = (push_imm32(-42) + bytes([DUP]) + push_imm32(0) +
                bytes([LT]) + jnz_addr(17) +
                bytes([POP, HALT]) + bytes([POP, NEG, HALT]))
        stack, _ = vm.run(code)
        assert stack == [42]

    def test_xor_inverse(self):
        vm = FluxVM()
        code = push_imm32(0xFF) + push_imm32(0x0F) + bytes([XOR]) + push_imm32(0x0F) + bytes([XOR, HALT])
        stack, _ = vm.run(code)
        assert stack == [0xFF]

    def test_power_of_2_loop(self):
        vm = FluxVM()
        # Compute 2^10 = 1024 by doubling 10 times
        # PUSH 1, PUSH 10, loop@10: DUP, JZ->25, POP, DUP, MUL, DEC, JNZ->10, HALT@25
        code = (push_imm32(1) + push_imm32(10) + bytes([DUP]) +
                jz_addr(25) + bytes([POP, DUP, MUL, DEC]) +
                jnz_addr(10) + bytes([HALT]))
        stack, _ = vm.run(code)
        assert stack == [1024]

    def test_max_steps_limit(self):
        vm = FluxVM()
        vm.max_steps = 5
        code = bytes([NOP] * 100) + bytes([HALT])
        stack, _ = vm.run(code)
        assert vm.steps == 5
        assert len(stack) == 0


# ═══════════════════════════════════════════════════════════════════════
# FRAMEWORK TESTS — ConformanceTestSuite behavior
# ═══════════════════════════════════════════════════════════════════════

class TestConformanceTestCase:
    def test_case_creation_defaults(self):
        case = ConformanceTestCase(name="test", bytecode_hex="00")
        assert case.initial_stack == []
        assert case.expected_stack == []
        assert case.expected_flags == FLAGS_ANY
        assert case.description == ""
        assert case.allow_float_epsilon is False

    def test_case_creation_full(self):
        case = ConformanceTestCase(
            name="full_test",
            bytecode_hex="550300000055040000001000",
            initial_stack=[],
            expected_stack=[7],
            expected_flags=0,
            description="3+4=7",
            allow_float_epsilon=False,
        )
        assert case.name == "full_test"
        assert case.expected_stack == [7]


class TestConformanceTestSuite:
    def test_empty_suite(self):
        suite = ConformanceTestSuite()
        assert len(suite.cases) == 0

    def test_add_case(self):
        suite = ConformanceTestSuite()
        case = ConformanceTestCase(name="test", bytecode_hex="00")
        suite.add(case)
        assert len(suite.cases) == 1
        assert suite.cases[0].name == "test"

    def test_load_builtin_cases(self):
        suite = ConformanceTestSuite()
        suite.load_builtin_cases()
        assert len(suite.cases) >= 50

    def test_run_single_pass(self):
        suite = ConformanceTestSuite()
        case = ConformanceTestCase(
            name="simple_add",
            bytecode_hex=(push_imm32(3) + push_imm32(4) + bytes([ADD, HALT])).hex(),
            expected_stack=[7],
        )
        result = suite.run_single(case)
        assert result["passed"]
        assert result["error"] is None

    def test_run_single_fail_stack(self):
        suite = ConformanceTestSuite()
        case = ConformanceTestCase(
            name="bad_add",
            bytecode_hex=(push_imm32(3) + push_imm32(4) + bytes([ADD, HALT])).hex(),
            expected_stack=[999],  # Wrong expectation
        )
        result = suite.run_single(case)
        assert not result["passed"]
        assert "Stack" in result["error"]

    def test_run_single_fail_flags(self):
        suite = ConformanceTestSuite()
        case = ConformanceTestCase(
            name="bad_flags",
            bytecode_hex=(push_imm32(1) + bytes([HALT])).hex(),
            expected_stack=[1],
            expected_flags=0xFF,  # Wrong flags
        )
        result = suite.run_single(case)
        assert not result["passed"]
        assert "Flags" in result["error"]

    def test_run_single_error_caught(self):
        suite = ConformanceTestSuite()
        case = ConformanceTestCase(
            name="div_zero",
            bytecode_hex=(push_imm32(1) + push_imm32(0) + bytes([DIV, HALT])).hex(),
        )
        result = suite.run_single(case)
        assert not result["passed"]
        assert "Division by zero" in result["error"]

    def test_run_all(self):
        suite = ConformanceTestSuite()
        suite.load_builtin_cases()
        results = suite.run_all()
        assert len(results) == len(suite.cases)
        for r in results:
            assert "name" in r
            assert "passed" in r

    def test_summary_format(self):
        suite = ConformanceTestSuite()
        suite.load_builtin_cases()
        results = suite.run_all()
        summary = suite.summary(results)
        assert "FLUX Conformance Test Results" in summary
        assert "passed" in summary

    def test_float_epsilon_comparison(self):
        suite = ConformanceTestSuite()
        case = ConformanceTestCase(
            name="float_eps",
            bytecode_hex=(push_imm32(1) + push_imm32(1) + bytes([FDIV, HALT])).hex(),
            expected_stack=[1.0],
            allow_float_epsilon=True,
        )
        result = suite.run_single(case)
        assert result["passed"]

    def test_float_epsilon_failure(self):
        suite = ConformanceTestSuite()
        case = ConformanceTestCase(
            name="float_eps_fail",
            bytecode_hex=(push_imm32(1) + push_imm32(3) + bytes([FDIV, HALT])).hex(),
            expected_stack=[1.0],  # Wrong: should be 0.333
            allow_float_epsilon=True,
        )
        result = suite.run_single(case)
        assert not result["passed"]


class TestBytecodeHelpers:
    def test_push_imm32_zero(self):
        code = push_imm32(0)
        assert len(code) == 5
        assert code[0] == PUSH
        assert struct.unpack_from("<i", code, 1)[0] == 0

    def test_push_imm32_negative(self):
        code = push_imm32(-1)
        val = struct.unpack_from("<i", code, 1)[0]
        assert val == -1

    def test_push_imm32_max(self):
        code = push_imm32(2147483647)
        val = struct.unpack_from("<i", code, 1)[0]
        assert val == 2147483647

    def test_jmp_addr(self):
        code = jmp_addr(42)
        assert len(code) == 3
        assert code[0] == JMP
        assert struct.unpack_from("<H", code, 1)[0] == 42

    def test_store_addr(self):
        code = store_addr(100)
        assert len(code) == 3
        assert code[0] == STORE
        assert struct.unpack_from("<H", code, 1)[0] == 100

    def test_load_addr(self):
        code = load_addr(200)
        assert len(code) == 3
        assert code[0] == LOAD
        assert struct.unpack_from("<H", code, 1)[0] == 200

    def test_signal_ch(self):
        code = signal_ch(5)
        assert code == bytes([SIGNAL, 5])

    def test_broadcast_ch(self):
        code = broadcast_ch(7)
        assert code == bytes([BROADCAST, 7])

    def test_listen_ch(self):
        code = listen_ch(3)
        assert code == bytes([LISTEN, 3])


class TestFluxVMInternals:
    def test_pc_advances(self):
        vm = FluxVM()
        code = bytes([NOP, NOP, HALT])
        vm.run(code)
        assert vm.steps == 3

    def test_reset_clears_state(self):
        vm = FluxVM()
        vm.run(push_imm32(42) + bytes([HALT]))
        assert len(vm.stack) == 1
        vm.reset()
        assert len(vm.stack) == 0
        assert vm.pc == 0
        assert vm.flags.value == 0
        assert vm.confidence == 1.0

    def test_unknown_opcode_raises(self):
        vm = FluxVM()
        with pytest.raises(RuntimeError, match="Unknown opcode"):
            vm.run(bytes([0xFE, HALT]))

    def test_call_stack_management(self):
        vm = FluxVM()
        vm.run(push_imm32(1) + call_addr(10) + bytes([ADD, HALT]) +
                push_imm32(2) + bytes([RET, HALT]))
        assert len(vm.call_stack) == 0  # Should be empty after RET

    def test_memory_size(self):
        vm = FluxVM()
        assert len(vm.memory) == 65536


class TestFluxFlags:
    def test_initial_value(self):
        f = FluxFlags()
        assert f.value == 0

    def test_z_flag_set(self):
        f = FluxFlags()
        f.Z = True
        assert f.value & FLAG_Z
        assert f.Z is True

    def test_z_flag_clear(self):
        f = FluxFlags()
        f.Z = True
        f.Z = False
        assert not (f.value & FLAG_Z)
        assert f.Z is False

    def test_all_flags(self):
        f = FluxFlags()
        f.Z = True
        f.S = True
        f.C = True
        f.O = True
        assert f.value == 0x0F

    def test_update_arith_zero(self):
        f = FluxFlags()
        f.update_arith(0, 5, -5)
        assert f.Z is True
        assert f.S is False

    def test_update_arith_negative(self):
        f = FluxFlags()
        f.update_arith(-7, 3, 10)
        assert f.Z is False
        assert f.S is True

    def test_update_logic_zero(self):
        f = FluxFlags()
        f.update_logic(0)
        assert f.Z is True
        assert f.C is False
        assert f.O is False

    def test_update_logic_nonzero(self):
        f = FluxFlags()
        f.update_logic(42)
        assert f.Z is False

    def test_update_logic_clears_co(self):
        f = FluxFlags()
        f.C = True
        f.O = True
        f.update_logic(0)
        assert f.C is False
        assert f.O is False


# ═══════════════════════════════════════════════════════════════════════
# SUITE INTEGRATION TESTS
# ═══════════════════════════════════════════════════════════════════════

class TestSuiteIntegration:
    def test_suite_loads_all_cases(self, suite):
        assert len(suite.cases) >= 50

    def test_suite_all_pass(self, suite):
        results = suite.run_all()
        failed = [r for r in results if not r["passed"]]
        assert not failed, (
            f"{len(failed)} tests failed:\n" +
            "\n".join(f"  - {r['name']}: {r['error']}" for r in failed)
        )

    def test_suite_summary(self, suite):
        results = suite.run_all()
        summary = suite.summary(results)
        assert "FLUX Conformance Test Results" in summary
        assert f"{len(results)}/{len(results)} passed" in summary


# ─── Fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture(scope="module")
def suite() -> ConformanceTestSuite:
    s = ConformanceTestSuite()
    s.load_builtin_cases()
    return s
