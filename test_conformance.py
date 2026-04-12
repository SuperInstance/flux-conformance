"""
FLUX Conformance Test Suite — Pytest Runner

Runs every built-in conformance test case against the reference VM and
verifies stack output, flag state, and error conditions.
"""

import pytest
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


# ─── Category smoke tests ────────────────────────────────────────────────────

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


class TestComparison:
    def test_eq_true(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(5) + push_imm32(5) + bytes([EQ, HALT]))
        assert stack == [1]

    def test_eq_false(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(5) + push_imm32(6) + bytes([EQ, HALT]))
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

    def test_negatives_compare(self):
        vm = FluxVM()
        stack, _ = vm.run(push_imm32(-10) + push_imm32(-3) + bytes([LT, HALT]))
        assert stack == [1]

    def test_eq_with_stack(self):
        vm = FluxVM()
        stack, _ = vm.run(bytes([EQ, HALT]), initial_stack=[100, 100])
        assert stack == [1]


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
        # DEC 1->0 sets Z flag, POP removes 0, PUSH 42, JZ past PUSH 99
        code = push_imm32(1) + bytes([DEC, POP]) + push_imm32(42) + jz_addr(20) + push_imm32(99) + bytes([HALT])
        stack, _ = vm.run(code)
        assert stack == [42]

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
        # Start at 1, * 0 (clamp), still 0
        code = push_imm32(1) + bytes([CONF_SET]) + push_imm32(0) + bytes([CONF_MUL, CONF_GET, HALT])
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


class TestFlags:
    def test_zero_flag_on_add_zero(self):
        vm = FluxVM()
        code = push_imm32(5) + push_imm32(-5) + bytes([ADD, HALT])
        _, flags = vm.run(code)
        assert flags & FLAG_Z

    def test_zero_flag_on_eq_false(self):
        vm = FluxVM()
        code = push_imm32(1) + push_imm32(2) + bytes([EQ, HALT])
        _, flags = vm.run(code)
        assert flags & FLAG_Z

    def test_zero_flag_on_and_zero(self):
        vm = FluxVM()
        code = push_imm32(0) + push_imm32(0) + bytes([AND, HALT])
        _, flags = vm.run(code)
        assert flags & FLAG_Z

    def test_sign_flag_on_negative(self):
        vm = FluxVM()
        code = push_imm32(5) + bytes([NEG, HALT])
        _, flags = vm.run(code)
        assert flags & FLAG_S

    def test_sign_flag_on_sub(self):
        vm = FluxVM()
        code = push_imm32(3) + push_imm32(10) + bytes([SUB, HALT])
        _, flags = vm.run(code)
        assert flags & FLAG_S


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
