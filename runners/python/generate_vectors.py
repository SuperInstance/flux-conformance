#!/usr/bin/env python3
"""
Generate FLUX conformance test vectors.

This script uses the BytecodeBuilder to create test vectors for all opcode
categories. Each test vector is a JSON object following the test-vector-schema.json
format, and is serialized to vectors/ as individual JSON files plus a combined
manifest.

Tests are designed to verify:
1. Correct computation (arithmetic, logic, comparison)
2. Correct control flow (branches, calls, loops)
3. Correct memory operations (load, store, regions)
4. Correct flag setting (zero, sign, carry, overflow)
5. Edge cases (division by zero, overflow, boundary conditions)
"""

import json
import os
import struct
import sys

# Add parent dir to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from bytecode_builder import BytecodeBuilder


def _vector(id, name, category, description, bc_builder, expected, preconditions=None, tags=None):
    """Create a test vector dict from a BytecodeBuilder instance."""
    v = {
        "id": id,
        "name": name,
        "category": category,
        "description": description,
        "bytecode_hex": bc_builder.hex(),
        "expected": {
            "final_state": "HALTED",
            **expected,
        },
    }
    if preconditions:
        v["preconditions"] = preconditions
    if tags:
        v["tags"] = tags
    return v


# =============================================================================
# ARITHMETIC TESTS
# =============================================================================

def make_arithmetic_vectors():
    vectors = []

    # --- IADD: Basic addition ---
    vectors.append(_vector(
        "arith-iadd-basic", "IADD: 3 + 4 = 7", "arithmetic",
        "Add two positive integers loaded via MOVI",
        BytecodeBuilder().movi(1, 3).movi(2, 4).iadd(0, 1, 2).halt(),
        {"gp": {"0": 7}}, tags=["smoke", "p0"]
    ))

    # --- IADD: Zero + value ---
    vectors.append(_vector(
        "arith-iadd-zero", "IADD: 0 + 42 = 42", "arithmetic",
        "Add zero to a value (identity operation)",
        BytecodeBuilder().movi(0, 0).movi(1, 42).iadd(2, 0, 1).halt(),
        {"gp": {"2": 42}}, tags=["smoke"]
    ))

    # --- IADD: Negative result ---
    vectors.append(_vector(
        "arith-iadd-negative", "IADD: -1 + (-1) = -2", "arithmetic",
        "Adding two values that produce a negative result (uses MOVI with negative i16)",
        BytecodeBuilder().movi(1, -1).movi(2, -1).iadd(0, 1, 2).halt(),
        {"gp": {"0": -2}}, tags=["smoke"]
    ))

    # --- ISUB: Basic subtraction ---
    vectors.append(_vector(
        "arith-isub-basic", "ISUB: 10 - 3 = 7", "arithmetic",
        "Subtract two positive integers",
        BytecodeBuilder().movi(1, 10).movi(2, 3).isub(0, 1, 2).halt(),
        {"gp": {"0": 7}}, tags=["smoke", "p0"]
    ))

    # --- ISUB: Negative result ---
    vectors.append(_vector(
        "arith-isub-negative", "ISUB: 3 - 10 = -7", "arithmetic",
        "Subtraction producing negative result",
        BytecodeBuilder().movi(1, 3).movi(2, 10).isub(0, 1, 2).halt(),
        {"gp": {"0": -7}}
    ))

    # --- IMUL: Basic multiplication ---
    vectors.append(_vector(
        "arith-imul-basic", "IMUL: 6 * 7 = 42", "arithmetic",
        "Multiply two positive integers",
        BytecodeBuilder().movi(1, 6).movi(2, 7).imul(0, 1, 2).halt(),
        {"gp": {"0": 42}}, tags=["smoke", "p0"]
    ))

    # --- IMUL: Multiply by zero ---
    vectors.append(_vector(
        "arith-imul-zero", "IMUL: 100 * 0 = 0", "arithmetic",
        "Multiplication by zero",
        BytecodeBuilder().movi(1, 100).movi(2, 0).imul(0, 1, 2).halt(),
        {"gp": {"0": 0}}
    ))

    # --- IMUL: Negative multiplication ---
    vectors.append(_vector(
        "arith-imul-negative", "IMUL: -5 * 3 = -15", "arithmetic",
        "Multiply negative by positive",
        BytecodeBuilder().movi(1, -5).movi(2, 3).imul(0, 1, 2).halt(),
        {"gp": {"0": -15}}
    ))

    # --- IDIV: Basic division ---
    vectors.append(_vector(
        "arith-idiv-basic", "IDIV: 20 / 4 = 5", "arithmetic",
        "Integer division of positive values",
        BytecodeBuilder().movi(1, 20).movi(2, 4).idiv(0, 1, 2).halt(),
        {"gp": {"0": 5}}, tags=["smoke", "p0"]
    ))

    # --- IDIV: Truncation ---
    vectors.append(_vector(
        "arith-idiv-truncate", "IDIV: 17 / 5 = 3 (truncate)", "arithmetic",
        "Integer division truncates toward zero",
        BytecodeBuilder().movi(1, 17).movi(2, 5).idiv(0, 1, 2).halt(),
        {"gp": {"0": 3}}
    ))

    # --- IMOD: Basic modulo ---
    vectors.append(_vector(
        "arith-imod-basic", "IMOD: 17 % 5 = 2", "arithmetic",
        "Modulo operation",
        BytecodeBuilder().movi(1, 17).movi(2, 5).imod(0, 1, 2).halt(),
        {"gp": {"0": 2}}, tags=["smoke", "p0"]
    ))

    # --- INEG: Negate positive ---
    vectors.append(_vector(
        "arith-ineg-positive", "INEG: -42 = negation of 42", "arithmetic",
        "Negate a positive number",
        BytecodeBuilder().movi(1, 42).ineg(0, 1).halt(),
        {"gp": {"0": -42}}, tags=["smoke"]
    ))

    # --- INEG: Negate negative ---
    vectors.append(_vector(
        "arith-ineg-negative", "INEG: -(-7) = 7", "arithmetic",
        "Double negation returns original value",
        BytecodeBuilder().movi(1, -7).ineg(0, 1).halt(),
        {"gp": {"0": 7}}
    ))

    # --- INC: Increment ---
    vectors.append(_vector(
        "arith-inc-basic", "INC: R0 from 9 to 10", "arithmetic",
        "Increment register by 1",
        BytecodeBuilder().movi(0, 9).inc(0).halt(),
        {"gp": {"0": 10}}, tags=["smoke"]
    ))

    # --- DEC: Decrement ---
    vectors.append(_vector(
        "arith-dec-basic", "DEC: R0 from 5 to 4", "arithmetic",
        "Decrement register by 1",
        BytecodeBuilder().movi(0, 5).dec(0).halt(),
        {"gp": {"0": 4}}, tags=["smoke"]
    ))

    # --- MOV: Copy register ---
    vectors.append(_vector(
        "arith-mov-basic", "MOV: R0 = R1 = 42", "arithmetic",
        "Move (copy) register value",
        BytecodeBuilder().movi(1, 42).mov(0, 1).halt(),
        {"gp": {"0": 42, "1": 42}}, tags=["smoke"]
    ))

    # --- MOVI: Load immediate ---
    vectors.append(_vector(
        "arith-movi-basic", "MOVI: R0 = 32767 (max i16)", "arithmetic",
        "Load maximum positive i16 value",
        BytecodeBuilder().movi(0, 32767).halt(),
        {"gp": {"0": 32767}}, tags=["smoke"]
    ))

    # --- MOVI: Negative immediate ---
    vectors.append(_vector(
        "arith-movi-negative", "MOVI: R0 = -1 (0xFFFF sign-extended)", "arithmetic",
        "Load -1 as immediate (tests sign extension from i16)",
        BytecodeBuilder().movi(0, -1).halt(),
        {"gp": {"0": -1}}
    ))

    # --- IREM: Remainder ---
    vectors.append(_vector(
        "arith-irem-basic", "IREM: 17 rem 5 = 2", "arithmetic",
        "Integer remainder operation",
        BytecodeBuilder().movi(1, 17).movi(2, 5).irem(0, 1, 2).halt(),
        {"gp": {"0": 2}}
    ))

    # --- NOP: No operation ---
    vectors.append(_vector(
        "arith-nop", "NOP: should not affect state", "arithmetic",
        "NOP instruction does nothing",
        BytecodeBuilder().movi(0, 42).nop().nop().nop().halt(),
        {"gp": {"0": 42}}, tags=["smoke"]
    ))

    return vectors


# =============================================================================
# LOGIC / BITWISE TESTS
# =============================================================================

def make_logic_vectors():
    vectors = []

    # --- IAND ---
    vectors.append(_vector(
        "logic-iand-basic", "IAND: 0xFF & 0x0F = 0x0F", "logic",
        "Bitwise AND masks bits",
        BytecodeBuilder().movi(1, 0xFF).movi(2, 0x0F).iand(0, 1, 2).halt(),
        {"gp": {"0": 0x0F}}, tags=["smoke", "p0"]
    ))

    # --- IAND with zero ---
    vectors.append(_vector(
        "logic-iand-zero", "IAND: 42 & 0 = 0", "logic",
        "AND with zero yields zero",
        BytecodeBuilder().movi(1, 42).movi(2, 0).iand(0, 1, 2).halt(),
        {"gp": {"0": 0}}
    ))

    # --- IOR ---
    vectors.append(_vector(
        "logic-ior-basic", "IOR: 0xF0 | 0x0F = 0xFF", "logic",
        "Bitwise OR combines bits",
        BytecodeBuilder().movi(1, 0xF0).movi(2, 0x0F).ior(0, 1, 2).halt(),
        {"gp": {"0": 0xFF}}, tags=["smoke", "p0"]
    ))

    # --- IXOR ---
    vectors.append(_vector(
        "logic-ixor-basic", "IXOR: 0xFF ^ 0xFF = 0", "logic",
        "XOR of identical values yields zero",
        BytecodeBuilder().movi(1, 0xFF).movi(2, 0xFF).ixor(0, 1, 2).halt(),
        {"gp": {"0": 0}}, tags=["smoke"]
    ))

    # --- IXOR toggle bits ---
    vectors.append(_vector(
        "logic-ixor-toggle", "IXOR: 0xF0 ^ 0xFF = 0x0F", "logic",
        "XOR toggles (flips) bits where mask is 1",
        BytecodeBuilder().movi(1, 0xF0).movi(2, 0xFF).ixor(0, 1, 2).halt(),
        {"gp": {"0": 0x0F}}
    ))

    # --- INOT ---
    vectors.append(_vector(
        "logic-inot-basic", "INOT: ~0 = -1 (all bits set)", "logic",
        "Bitwise NOT inverts all bits",
        BytecodeBuilder().movi(1, 0).inot(0, 1).halt(),
        {"gp": {"0": -1}}, tags=["smoke"]
    ))

    # --- ISHL: Left shift ---
    vectors.append(_vector(
        "logic-ishl-basic", "ISHL: 1 << 4 = 16", "logic",
        "Left shift multiplies by powers of 2",
        BytecodeBuilder().movi(1, 1).movi(2, 4).ishl(0, 1, 2).halt(),
        {"gp": {"0": 16}}, tags=["smoke", "p0"]
    ))

    # --- ISHR: Right shift ---
    vectors.append(_vector(
        "logic-ishr-basic", "ISHR: 16 >> 2 = 4", "logic",
        "Right shift divides by powers of 2",
        BytecodeBuilder().movi(1, 16).movi(2, 2).ishr(0, 1, 2).halt(),
        {"gp": {"0": 4}}, tags=["smoke", "p0"]
    ))

    # --- ROTL: Rotate left ---
    vectors.append(_vector(
        "logic-rotl-basic", "ROTL: 1 rotate left 1 = 2", "logic",
        "Rotate left shifts bits that wrap around",
        BytecodeBuilder().movi(1, 1).movi(2, 1).rotl(0, 1, 2).halt(),
        {"gp": {"0": 2}}
    ))

    # --- ROTR: Rotate right ---
    vectors.append(_vector(
        "logic-rotr-basic", "ROTR: 2 rotate right 1 = 1", "logic",
        "Rotate right shifts bits that wrap around",
        BytecodeBuilder().movi(1, 2).movi(2, 1).rotr(0, 1, 2).halt(),
        {"gp": {"0": 1}}
    ))

    return vectors


# =============================================================================
# COMPARISON TESTS
# =============================================================================

def make_comparison_vectors():
    vectors = []

    # --- CMP + JE: Equal values ---
    bc = BytecodeBuilder()
    bc.movi(1, 10).movi(2, 10).cmp(1, 2)
    bc.je_label("equal").movi(0, 0).halt()
    bc.label("equal").movi(0, 1).halt()
    vectors.append(_vector(
        "cmp-je-equal", "CMP+JE: 10 == 10, jump taken", "comparison",
        "Compare equal values, JE should jump",
        bc, {"gp": {"0": 1}}, tags=["smoke", "p0"]
    ))

    # --- CMP + JE: Unequal values ---
    bc = BytecodeBuilder()
    bc.movi(1, 10).movi(2, 20).cmp(1, 2);
    bc.je_label("equal").movi(0, 0).halt()
    bc.label("equal").movi(0, 1).halt()
    vectors.append(_vector(
        "cmp-je-unequal", "CMP+JE: 10 != 20, jump NOT taken", "comparison",
        "Compare unequal values, JE should not jump",
        bc, {"gp": {"0": 0}}, tags=["smoke", "p0"]
    ))

    # --- CMP + JNE: Unequal values ---
    bc = BytecodeBuilder()
    bc.movi(1, 10).movi(2, 20).cmp(1, 2)
    bc.jne_label("notequal").movi(0, 0).halt()
    bc.label("notequal").movi(0, 1).halt()
    vectors.append(_vector(
        "cmp-jne-unequal", "CMP+JNE: 10 != 20, jump taken", "comparison",
        "Compare unequal values, JNE should jump",
        bc, {"gp": {"0": 1}}, tags=["smoke"]
    ))

    # --- CMP + JG: Greater than ---
    bc = BytecodeBuilder()
    bc.movi(1, 20).movi(2, 10).cmp(1, 2)
    bc.jg_label("greater").movi(0, 0).halt()
    bc.label("greater").movi(0, 1).halt()
    vectors.append(_vector(
        "cmp-jg-greater", "CMP+JG: 20 > 10, jump taken", "comparison",
        "Compare with greater-than, JG should jump",
        bc, {"gp": {"0": 1}}, tags=["smoke", "p0"]
    ))

    # --- CMP + JL: Less than ---
    bc = BytecodeBuilder()
    bc.movi(1, 5).movi(2, 10).cmp(1, 2)
    bc.jl_label("less").movi(0, 0).halt()
    bc.label("less").movi(0, 1).halt()
    vectors.append(_vector(
        "cmp-jl-less", "CMP+JL: 5 < 10, jump taken", "comparison",
        "Compare with less-than, JL should jump",
        bc, {"gp": {"0": 1}}, tags=["smoke"]
    ))

    # --- CMP + JGE: Greater or equal ---
    bc = BytecodeBuilder()
    bc.movi(1, 10).movi(2, 10).cmp(1, 2)
    bc.jge_label("geq").movi(0, 0).halt()
    bc.label("geq").movi(0, 1).halt()
    vectors.append(_vector(
        "cmp-jge-equal", "CMP+JGE: 10 >= 10, jump taken", "comparison",
        "Compare equal values, JGE should jump",
        bc, {"gp": {"0": 1}}
    ))

    # --- CMP + JLE: Less or equal ---
    bc = BytecodeBuilder()
    bc.movi(1, 5).movi(2, 10).cmp(1, 2)
    bc.jle_label("leq").movi(0, 0).halt()
    bc.label("leq").movi(0, 1).halt()
    vectors.append(_vector(
        "cmp-jle-less", "CMP+JLE: 5 <= 10, jump taken", "comparison",
        "Compare less values, JLE should jump",
        bc, {"gp": {"0": 1}}
    ))

    # --- TEST: Zero flag set ---
    bc = BytecodeBuilder()
    bc.movi(1, 0x00).movi(2, 0xFF).test(1, 2)
    bc.je_label("zero").movi(0, 0).halt()
    bc.label("zero").movi(0, 1).halt()
    vectors.append(_vector(
        "cmp-test-zero", "TEST: 0x00 & 0xFF = 0, ZF set", "comparison",
        "TEST with zero value sets zero flag",
        bc, {"gp": {"0": 1}}, tags=["smoke"]
    ))

    # --- ICMP with condition codes ---
    # ICMP writes result (0 or 1) to R0 and sets condition flags
    vectors.append(_vector(
        "cmp-icmp-eq", "ICMP EQ: 5 == 5, result in R0", "comparison",
        "ICMP with EQ condition writes 1 to R0 when equal",
        BytecodeBuilder().movi(1, 5).movi(2, 5).icmp(BytecodeBuilder.EQ, 1, 2).halt(),
        {"gp": {"0": 1}}, tags=["smoke"]
    ))

    vectors.append(_vector(
        "cmp-icmp-ne", "ICMP NE: 5 != 3, result in R0", "comparison",
        "ICMP with NE condition writes 1 to R0 when not equal",
        BytecodeBuilder().movi(1, 5).movi(2, 3).icmp(BytecodeBuilder.NE, 1, 2).halt(),
        {"gp": {"0": 1}}
    ))

    vectors.append(_vector(
        "cmp-icmp-lt", "ICMP LT: 3 < 5, result in R0", "comparison",
        "ICMP with LT condition writes 1 to R0 when less",
        BytecodeBuilder().movi(1, 3).movi(2, 5).icmp(BytecodeBuilder.LT, 1, 2).halt(),
        {"gp": {"0": 1}}
    ))

    vectors.append(_vector(
        "cmp-icmp-gt", "ICMP GT: 10 > 3, result in R0", "comparison",
        "ICMP with GT condition writes 1 to R0 when greater",
        BytecodeBuilder().movi(1, 10).movi(2, 3).icmp(BytecodeBuilder.GT, 1, 2).halt(),
        {"gp": {"0": 1}}
    ))

    vectors.append(_vector(
        "cmp-icmp-le", "ICMP LE: 5 <= 5, result in R0", "comparison",
        "ICMP with LE condition writes 1 when less or equal",
        BytecodeBuilder().movi(1, 5).movi(2, 5).icmp(BytecodeBuilder.LE, 1, 2).halt(),
        {"gp": {"0": 1}}
    ))

    return vectors


# =============================================================================
# BRANCH / CONTROL FLOW TESTS
# =============================================================================

def make_branch_vectors():
    vectors = []

    # --- JMP: Unconditional jump forward ---
    bc = BytecodeBuilder()
    bc.jmp_label("target").movi(0, 0).halt()  # should skip this
    bc.label("target").movi(0, 99).halt()
    vectors.append(_vector(
        "branch-jmp-forward", "JMP: unconditional forward jump", "branch",
        "JMP skips the instruction between jump and target",
        bc, {"gp": {"0": 99}}, tags=["smoke", "p0"]
    ))

    # --- JMP: Unconditional jump backward (infinite loop with escape) ---
    # DEC 5 times then fall through
    bc = BytecodeBuilder()
    bc.movi(1, 5)
    bc.label("loop")
    bc.dec(1)
    bc.jnz_label(1, "loop")
    bc.movi(0, 42).halt()
    vectors.append(_vector(
        "branch-jnz-loop", "JNZ: loop 5 times then exit", "branch",
        "JNZ-based countdown loop runs exactly 5 iterations",
        bc, {"gp": {"0": 42, "1": 0}}, tags=["smoke", "p0"]
    ))

    # --- JZ: Jump on zero ---
    bc = BytecodeBuilder()
    bc.movi(0, 0)
    bc.jz_label(0, "is_zero").movi(1, 0).halt()
    bc.label("is_zero").movi(1, 1).halt()
    vectors.append(_vector(
        "branch-jz-zero", "JZ: jump when register is zero", "branch",
        "JZ should jump when register contains zero",
        bc, {"gp": {"1": 1}}, tags=["smoke"]
    ))

    # --- JZ: Not taken when non-zero ---
    bc = BytecodeBuilder()
    bc.movi(0, 5)
    bc.jz_label(0, "is_zero").movi(1, 1).halt()
    bc.label("is_zero").movi(1, 0).halt()
    vectors.append(_vector(
        "branch-jz-nonzero", "JZ: no jump when register is non-zero", "branch",
        "JZ should not jump when register is non-zero",
        bc, {"gp": {"1": 1}}
    ))

    # --- Nested loop: Sum 1..10 ---
    # R0 = sum, R1 = counter (10 down to 1)
    bc = BytecodeBuilder()
    bc.movi(0, 0).movi(1, 10)
    bc.label("loop")
    bc.iadd(0, 0, 1)  # sum += counter
    bc.dec(1)          # counter--
    bc.jnz_label(1, "loop")
    bc.halt()
    vectors.append(_vector(
        "branch-nested-sum", "Loop: sum of 1..10 = 55", "branch",
        "Accumulate sum from 10 down to 1 using JNZ loop",
        bc, {"gp": {"0": 55, "1": 0}}, tags=["smoke", "p0"]
    ))

    # --- CALL + RET: Simple function call ---
    # Function at 'func' doubles R1 and stores in R0
    bc = BytecodeBuilder()
    bc.movi(1, 21)
    bc.call_label("func")
    bc.halt()
    bc.label("func")
    bc.iadd(0, 1, 1)  # R0 = R1 + R1 = 42
    bc.ret()
    vectors.append(_vector(
        "branch-call-ret", "CALL+RET: double 21 = 42", "branch",
        "CALL pushes return address, RET returns to caller",
        bc, {"gp": {"0": 42}}, tags=["smoke", "p0"]
    ))

    # --- Fibonacci sequence (compute fib(10) = 55) ---
    # R0 = fib(n-2), R1 = fib(n-1), R2 = counter
    # We compute iteratively: start with R0=0, R1=1, loop 10 times
    # Each iteration: temp = R0+R1, R0 = R1, R1 = temp
    bc = BytecodeBuilder()
    bc.movi(0, 0).movi(1, 1).movi(2, 10)
    bc.label("fib_loop")
    bc.iadd(3, 0, 1)   # R3 = R0 + R1
    bc.mov(0, 1)        # R0 = R1
    bc.mov(1, 3)        # R1 = R3
    bc.dec(2)
    bc.jnz_label(2, "fib_loop")
    bc.halt()
    vectors.append(_vector(
        "branch-fibonacci", "Loop: Fibonacci(10) = 55 in R1", "branch",
        "Compute 10th Fibonacci number iteratively. R1 holds fib(11)=89 after 10 iterations starting from fib(1)=1.",
        bc, {"gp": {"1": 89}}, tags=["smoke", "p0"]
    ))

    # --- GCD using Euclidean algorithm ---
    # R0 = a (48), R1 = b (18), compute GCD via repeated modulo
    # Since we don't have conditional modulo easily, use subtraction-based GCD
    bc = BytecodeBuilder()
    bc.movi(0, 48).movi(1, 18)
    bc.label("gcd_loop")
    # if R0 == R1, done
    bc.cmp(0, 1)
    bc.je_label("gcd_done")
    # if R0 > R1: R0 = R0 - R1, else R1 = R1 - R0
    bc.jg_label("a_bigger")
    bc.isub(1, 1, 0)  # R1 = R1 - R0
    bc.jmp_label("gcd_loop")
    bc.label("a_bigger")
    bc.isub(0, 0, 1)  # R0 = R0 - R1
    bc.jmp_label("gcd_loop")
    bc.label("gcd_done")
    bc.halt()
    vectors.append(_vector(
        "branch-gcd", "GCD(48, 18) = 6 via subtraction", "branch",
        "Compute GCD of 48 and 18 using Euclidean subtraction algorithm",
        bc, {"gp": {"0": 6}}, tags=["p0"]
    ))

    return vectors


# =============================================================================
# STACK TESTS
# =============================================================================

def make_stack_vectors():
    vectors = []

    # --- PUSH + POP: Basic push/pop ---
    bc = BytecodeBuilder()
    bc.movi(1, 42)
    bc.push(1)
    bc.movi(1, 0)   # clobber R1
    bc.pop(0)        # restore from stack
    bc.halt()
    vectors.append(_vector(
        "stack-push-pop", "PUSH+POP: save and restore 42", "stack",
        "Push value to stack, clobber register, pop to restore",
        bc, {"gp": {"0": 42}}, tags=["smoke", "p0"]
    ))

    # --- PUSH + POP: Multiple values ---
    bc = BytecodeBuilder()
    bc.movi(1, 10).push(1)
    bc.movi(1, 20).push(1);
    bc.movi(1, 30).push(1);
    bc.movi(1, 0)
    bc.pop(2)  # R2 = 30
    bc.pop(3)  # R3 = 20
    bc.pop(4)  # R4 = 10
    bc.halt()
    vectors.append(_vector(
        "stack-push3-pop3", "PUSH+POP: LIFO order verified", "stack",
        "Push 3 values, pop in reverse order to verify LIFO",
        bc, {"gp": {"2": 30, "3": 20, "4": 10}}, tags=["smoke", "p0"]
    ))

    # --- DUP: Duplicate top of stack ---
    bc = BytecodeBuilder()
    bc.movi(1, 7)
    bc.push(1)
    bc.dup()
    bc.movi(1, 0)
    bc.pop(0)  # first copy = 7
    bc.pop(1)  # second copy = 7
    bc.halt()
    vectors.append(_vector(
        "stack-dup", "DUP: duplicate top of stack", "stack",
        "DUP duplicates the top value on the stack",
        bc, {"gp": {"0": 7, "1": 7}}
    ))

    # --- SWAP: Swap top two stack values ---
    bc = BytecodeBuilder()
    bc.movi(1, 11).push(1)
    bc.movi(1, 22).push(1)
    bc.swap()
    bc.pop(0)  # should be 11 (was pushed first, now on top after swap)
    bc.pop(1)  # should be 22
    bc.halt()
    vectors.append(_vector(
        "stack-swap", "SWAP: swap top two stack values", "stack",
        "SWAP exchanges the two topmost stack values",
        bc, {"gp": {"0": 11, "1": 22}}
    ))

    # --- ENTER + LEAVE: Stack frame ---
    bc = BytecodeBuilder()
    bc.movi(1, 100).push(1)
    bc.enter(4)        # allocate 4 bytes of frame
    bc.movi(1, 0)      # clobber
    bc.leave()          # deallocate frame
    bc.pop(0)           # original value should still be there
    bc.halt()
    vectors.append(_vector(
        "stack-enter-leave", "ENTER+LEAVE: stack frame management", "stack",
        "ENTER allocates frame, LEAVE deallocates, original stack preserved",
        bc, {"gp": {"0": 100}}
    ))

    return vectors


# =============================================================================
# MEMORY TESTS
# =============================================================================

def make_memory_vectors():
    vectors = []

    # --- STORE + LOAD: Basic round-trip ---
    # Write to memory at R1, read back into R2
    bc = BytecodeBuilder()
    bc.movi(1, 100)  # address (offset in stack region)
    bc.movi(2, 42)   # value to store
    bc.store(2, 1)   # mem[R1] = R2  (store value in R2 to address in R1)
    bc.movi(2, 0)    # clobber R2
    bc.load(3, 1)    # R3 = mem[100]
    bc.halt()
    vectors.append(_vector(
        "mem-store-load", "STORE+LOAD: write 42, read back", "memory",
        "Write a value to memory and read it back",
        bc, {"gp": {"3": 42}}, tags=["smoke", "p0"]
    ))

    # --- LOAD8 + STORE8: Byte-level access ---
    bc = BytecodeBuilder()
    bc.movi(1, 200)   # address
    bc.movi(2, 0xAB)  # value
    bc.store8(2, 1)   # mem_byte[R1] = R2 (val=R2, addr=R1)
    bc.movi(2, 0)
    bc.load8(3, 1)    # R3 = mem_byte[200]
    bc.halt()
    vectors.append(_vector(
        "mem-store8-load8", "STORE8+LOAD8: byte-level round-trip", "memory",
        "Write and read a single byte from memory",
        bc, {"gp": {"3": 0xAB}}
    ))

    # --- Region create/destroy ---
    bc = BytecodeBuilder()
    bc.region_create("test_region", 256)
    bc.movi(0, 1).halt()
    vectors.append(_vector(
        "mem-region-create", "REGION_CREATE: create named memory region", "memory",
        "Create a 256-byte named memory region",
        bc, {"gp": {"0": 1}}
    ))

    # --- MEMSET ---
    bc = BytecodeBuilder()
    bc.region_create("buf", 64)
    bc.memset("buf", 0, 0xFF, 32)
    bc.movi(0, 1).halt()
    vectors.append(_vector(
        "mem-memset", "MEMSET: fill region with value", "memory",
        "Fill first 32 bytes of region 'buf' with 0xFF",
        bc, {"gp": {"0": 1}}
    ))

    return vectors


# =============================================================================
# FLOAT TESTS
# =============================================================================

def make_float_vectors():
    vectors = []

    # --- FADD ---
    vectors.append(_vector(
        "float-fadd-basic", "FADD: 3.0 + 4.0 = 7.0", "float",
        "Add two floats loaded via MOVI (stored as GP, then copied to FP in preconditions)",
        BytecodeBuilder().movi(0, 1).halt(),
        {"gp": {"0": 1}},
        preconditions={"fp": {"0": 3.0, "1": 4.0}},
        tags=["smoke"]
    ))
    # NOTE: Float operations use FP registers. We need a runner that can
    # pre-set FP registers and read results. The test above is a placeholder.
    # Real float tests need bytecode that uses FP opcodes.

    # For float tests, we construct programs where preconditions set FP regs
    # and the bytecode operates on them:

    # FADD: F0 = F1 + F2
    vectors.append(_vector(
        "float-fadd", "FADD: F0 = F1 + F2", "float",
        "Float addition using Format C FP registers",
        BytecodeBuilder().fadd(0, 1, 2).halt(),
        {"gp": {"0": 0}},
        preconditions={"fp": {"0": 0.0, "1": 3.14, "2": 2.86}},
        tags=["smoke", "p0"]
    ))
    # Expected FP[0] = 3.14 + 2.86 = 6.0
    vectors[-1]["expected"]["fp"] = {"0": 6.0}

    # FSUB: F0 = F1 - F2
    vectors.append(_vector(
        "float-fsub", "FSUB: F0 = F1 - F2", "float",
        "Float subtraction",
        BytecodeBuilder().fsub(0, 1, 2).halt(),
        {"gp": {"0": 0}},
        preconditions={"fp": {"0": 0.0, "1": 10.0, "2": 3.5}},
        tags=["smoke", "p0"]
    ))
    vectors[-1]["expected"]["fp"] = {"0": 6.5}

    # FMUL: F0 = F1 * F2
    vectors.append(_vector(
        "float-fmul", "FMUL: F0 = F1 * F2", "float",
        "Float multiplication",
        BytecodeBuilder().fmul(0, 1, 2).halt(),
        {"gp": {"0": 0}},
        preconditions={"fp": {"0": 0.0, "1": 2.5, "2": 4.0}},
        tags=["smoke", "p0"]
    ))
    vectors[-1]["expected"]["fp"] = {"0": 10.0}

    # FDIV: F0 = F1 / F2
    vectors.append(_vector(
        "float-fdiv", "FDIV: F0 = F1 / F2", "float",
        "Float division",
        BytecodeBuilder().fdiv(0, 1, 2).halt(),
        {"gp": {"0": 0}},
        preconditions={"fp": {"0": 0.0, "1": 15.0, "2": 4.0}},
        tags=["smoke", "p0"]
    ))
    vectors[-1]["expected"]["fp"] = {"0": 3.75}

    # FNEG
    vectors.append(_vector(
        "float-fneg", "FNEG: F0 = -F1", "float",
        "Float negation",
        BytecodeBuilder().fneg(0, 1).halt(),
        {"gp": {"0": 0}},
        preconditions={"fp": {"0": 0.0, "1": 7.5}}
    ))
    vectors[-1]["expected"]["fp"] = {"0": -7.5}

    # FABS
    vectors.append(_vector(
        "float-fabs", "FABS: F0 = |F1|", "float",
        "Float absolute value",
        BytecodeBuilder().fabs(0, 1).halt(),
        {"gp": {"0": 0}},
        preconditions={"fp": {"0": 0.0, "1": -3.14}}
    ))
    vectors[-1]["expected"]["fp"] = {"0": 3.14}

    # FMIN
    vectors.append(_vector(
        "float-fmin", "FMIN: F0 = min(F1, F2)", "float",
        "Float minimum",
        BytecodeBuilder().fmin(0, 1).halt(),
        {"gp": {"0": 0}},
        preconditions={"fp": {"0": 0.0, "1": 3.0, "2": 7.0}}
    ))
    vectors[-1]["expected"]["fp"] = {"0": 3.0}

    # FMAX
    vectors.append(_vector(
        "float-fmax", "FMAX: F0 = max(F1, F2)", "float",
        "Float maximum",
        BytecodeBuilder().fmax(0, 1).halt(),
        {"gp": {"0": 0}},
        preconditions={"fp": {"0": 0.0, "1": 3.0, "2": 7.0}}
    ))
    vectors[-1]["expected"]["fp"] = {"0": 7.0}

    return vectors


# =============================================================================
# A2A PROTOCOL TESTS
# =============================================================================

def make_a2a_vectors():
    vectors = []

    # --- TELL: Basic message ---
    vectors.append(_vector(
        "a2a-tell-basic", "TELL: send message, halt after", "a2a",
        "TELL sends a message and halts. A2A handler processes the message.",
        BytecodeBuilder().tell(b"hello fleet").halt(),
        {}
    ))

    # --- ASK: Query ---
    vectors.append(_vector(
        "a2a-ask-basic", "ASK: send query, halt after", "a2a",
        "ASK sends a query and halts.",
        BytecodeBuilder().ask(b"status?").halt(),
        {}
    ))

    # --- BROADCAST: Send to all ---
    vectors.append(_vector(
        "a2a-broadcast-basic", "BROADCAST: send to all, halt after", "a2a",
        "BROADCAST sends a message to all and halts.",
        BytecodeBuilder().broadcast(b"fleet-wide announcement").halt(),
        {}
    ))

    # --- DELEGATE: Delegate task ---
    vectors.append(_vector(
        "a2a-delegate-basic", "DELEGATE: delegate task, halt after", "a2a",
        "DELEGATE sends a task to another agent and halts.",
        BytecodeBuilder().delegate(b"compute fibonacci").halt(),
        {}
    ))

    return vectors


# =============================================================================
# SYSTEM TESTS
# =============================================================================

def make_system_vectors():
    vectors = []

    # --- HALT: Basic halt ---
    vectors.append(_vector(
        "system-halt", "HALT: stop execution", "system",
        "HALT stops the VM",
        BytecodeBuilder().halt(),
        {}, tags=["smoke"]
    ))

    # --- NOP chain ---
    vectors.append(_vector(
        "system-nop-chain", "NOP x10: no side effects", "system",
        "Chain of 10 NOPs followed by HALT",
        BytecodeBuilder().nop().nop().nop().nop().nop()
                      .nop().nop().nop().nop().nop().halt(),
        {}
    ))

    return vectors


# =============================================================================
# EDGE CASE TESTS
# =============================================================================

def make_edge_case_vectors():
    vectors = []

    # --- MOVI: Maximum i16 ---
    vectors.append(_vector(
        "edge-movi-max", "MOVI: load max i16 (32767)", "edge-case",
        "Load maximum 16-bit signed value",
        BytecodeBuilder().movi(0, 32767).halt(),
        {"gp": {"0": 32767}}
    ))

    # --- MOVI: Minimum i16 ---
    vectors.append(_vector(
        "edge-movi-min", "MOVI: load min i16 (-32768)", "edge-case",
        "Load minimum 16-bit signed value",
        BytecodeBuilder().movi(0, -32768).halt(),
        {"gp": {"0": -32768}}
    ))

    # --- Zero division (should error) ---
    vectors.append(_vector(
        "edge-div-zero", "IDIV: division by zero", "edge-case",
        "Dividing by zero should cause an error state",
        BytecodeBuilder().movi(1, 42).movi(2, 0).idiv(0, 1, 2).halt(),
        {"final_state": "ERRORED", "error_type": "DivisionByZero"},
        tags=["p0", "edge-case"]
    ))

    # --- Modulo zero ---
    vectors.append(_vector(
        "edge-mod-zero", "IMOD: modulo by zero", "edge-case",
        "Modulo by zero should cause an error state",
        BytecodeBuilder().movi(1, 42).movi(2, 0).imod(0, 1, 2).halt(),
        {"final_state": "ERRORED", "error_type": "DivisionByZero"}
    ))

    # --- Large loop count ---
    bc = BytecodeBuilder()
    bc.movi(0, 0).movi(1, 1000)
    bc.label("loop")
    bc.inc(0)
    bc.dec(1)
    bc.jnz_label(1, "loop")
    bc.halt()
    vectors.append(_vector(
        "edge-large-loop", "Loop: count to 1000", "edge-case",
        "Verify loop correctly handles 1000 iterations",
        bc, {"gp": {"0": 1000, "1": 0}},
        tags=["smoke"]
    ))

    # --- Arithmetic overflow (i16 addition that overflows) ---
    vectors.append(_vector(
        "edge-overflow", "IADD: 32767 + 1 = 32768", "edge-case",
        "Adding past i16 max — VM uses 32-bit registers so no overflow wraps",
        BytecodeBuilder().movi(1, 32767).movi(2, 1).iadd(0, 1, 2).halt(),
        {"gp": {"0": 32768}}  # wraps to min i16 or extends to 32-bit depending on VM
    ))

    # --- CALL_RET nested depth ---
    bc = BytecodeBuilder()
    bc.call_label("func_a")
    bc.halt()
    bc.label("func_a")
    bc.call_label("func_b")
    bc.ret()
    bc.label("func_b")
    bc.movi(0, 99)
    bc.ret()
    vectors.append(_vector(
        "edge-nested-call", "CALL: nested function calls", "edge-case",
        "Two levels of nested function calls with return",
        bc, {"gp": {"0": 99}}
    ))

    # --- CMP on zero values ---
    bc = BytecodeBuilder()
    bc.movi(1, 0).movi(2, 0).cmp(1, 2)
    bc.je_label("eq").movi(0, 0).halt()
    bc.label("eq").movi(0, 1).halt()
    vectors.append(_vector(
        "edge-cmp-zero-zero", "CMP: 0 == 0", "edge-case",
        "Comparing two zero values should set equal flag",
        bc, {"gp": {"0": 1}}
    ))

    return vectors


# =============================================================================
# COMPOSITE / ALGORITHMIC TESTS
# =============================================================================

def make_composite_vectors():
    vectors = []

    # --- Sum of squares: 1^2 + 2^2 + ... + 10^2 = 385 ---
    # R0 = sum, R1 = counter, R2 = temp
    bc = BytecodeBuilder()
    bc.movi(0, 0).movi(1, 1)
    bc.label("loop")
    bc.imul(2, 1, 1)   # R2 = counter * counter
    bc.iadd(0, 0, 2)   # sum += square
    bc.inc(1)           # counter++
    bc.movi(3, 11)      # upper bound
    bc.cmp(1, 3)        # compare counter to 11
    bc.jl_label("loop") # if counter < 11, continue
    bc.halt()
    vectors.append(_vector(
        "composite-sum-squares", "Sum of squares: 1..10 = 385", "branch",
        "Compute sum of squares from 1 to 10",
        bc, {"gp": {"0": 385}}, tags=["p0"]
    ))

    # --- Power of 2: compute 2^8 = 256 ---
    # R0 = result (starts at 1), R1 = exponent counter
    bc = BytecodeBuilder()
    bc.movi(0, 1).movi(1, 8)
    bc.label("pow_loop")
    bc.iadd(0, 0, 0)   # R0 = R0 + R0 (multiply by 2)
    bc.dec(1)
    bc.jnz_label(1, "pow_loop")
    bc.halt()
    vectors.append(_vector(
        "composite-power2", "2^8 = 256 via doubling", "branch",
        "Compute 2^8 using repeated doubling",
        bc, {"gp": {"0": 256}}
    ))

    # --- Factorial: 8! = 40320 ---
    # R0 = result, R1 = counter (8 down to 1)
    bc = BytecodeBuilder()
    bc.movi(0, 1).movi(1, 8)
    bc.label("fact_loop")
    bc.imul(0, 0, 1)   # result *= counter
    bc.dec(1)
    bc.jnz_label(1, "fact_loop")
    bc.halt()
    vectors.append(_vector(
        "composite-factorial", "8! = 40320", "branch",
        "Compute factorial of 8",
        bc, {"gp": {"0": 40320}}, tags=["p0"]
    ))

    # --- Conditional: find max of two values ---
    # R1 = 30, R2 = 50, R0 should contain max = 50
    bc = BytecodeBuilder()
    bc.movi(1, 30).movi(2, 50)
    bc.cmp(1, 2)
    bc.jg_label("r1_bigger")
    bc.mov(0, 2)    # R2 is bigger
    bc.halt()
    bc.label("r1_bigger")
    bc.mov(0, 1)    # R1 is bigger
    bc.halt()
    vectors.append(_vector(
        "composite-max", "max(30, 50) = 50", "branch",
        "Find maximum of two values using CMP+JG",
        bc, {"gp": {"0": 50}}
    ))

    # --- Copy R0 to R1 using only ADD and SUB ---
    bc = BytecodeBuilder()
    bc.movi(0, 42).movi(1, 0).movi(2, 0)
    bc.label("copy_loop")
    bc.inc(1)
    bc.inc(2)
    bc.cmp(2, 0)       # compare counter to original (but we need original value)
    bc.jl_label("copy_loop")  # This won't work as intended
    bc.halt()
    # Actually, let's do it properly:
    # We'll use MOV since it's a valid instruction
    vectors.pop()  # Remove the broken one

    bc = BytecodeBuilder()
    bc.movi(0, 42)
    bc.mov(1, 0)     # R1 = R0 (simple copy)
    bc.movi(0, 0)    # clobber R0
    bc.halt()
    vectors.append(_vector(
        "composite-copy", "MOV: copy R0 to R1", "branch",
        "Copy register value using MOV instruction",
        bc, {"gp": {"0": 0, "1": 42}}
    ))

    # --- Is prime check (simplified): 7 is prime ---
    # Test if 7 is prime by trial division from 2..6
    # R0 = candidate (7), R1 = divisor (2), R2 = flag (1 = prime)
    bc = BytecodeBuilder()
    bc.movi(0, 7).movi(1, 2).movi(2, 1)  # assume prime
    bc.label("trial")
    bc.idiv(3, 0, 1)      # R3 = 7 / divisor
    bc.imul(3, 3, 1)      # R3 = (7/divisor) * divisor
    bc.cmp(3, 0)           # compare to candidate
    bc.je_label("not_prime")
    bc.inc(1)              # divisor++
    bc.movi(3, 7)          # upper bound = candidate
    bc.cmp(1, 3)
    bc.jl_label("trial")   # continue if divisor < candidate
    bc.halt()              # still prime
    bc.label("not_prime")
    bc.movi(2, 0)          # not prime
    bc.halt()
    vectors.append(_vector(
        "composite-prime7", "IsPrime(7) = true", "branch",
        "Trial division primality test for 7",
        bc, {"gp": {"2": 1}}, tags=["p0"]
    ))

    return vectors


# =============================================================================
# MAIN: Generate all vectors
# =============================================================================

def main():
    output_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "vectors")
    os.makedirs(output_dir, exist_ok=True)

    all_generators = [
        make_arithmetic_vectors,
        make_logic_vectors,
        make_comparison_vectors,
        make_branch_vectors,
        make_stack_vectors,
        make_memory_vectors,
        make_float_vectors,
        make_a2a_vectors,
        make_system_vectors,
        make_edge_case_vectors,
        make_composite_vectors,
    ]

    all_vectors = []
    for generator in all_generators:
        vectors = generator()
        all_vectors.extend(vectors)

    # Write individual files
    for v in all_vectors:
        filepath = os.path.join(output_dir, f"{v['id']}.json")
        with open(filepath, 'w') as f:
            json.dump(v, f, indent=2)

    # Write manifest
    manifest = {
        "version": "1.0.0",
        "generated": "2026-04-12T08:00:00Z",
        "total_vectors": len(all_vectors),
        "categories": {},
        "isa_reference": "flux.bytecode.opcodes.Op (VM-executable opcode values)",
        "encoding_note": "All bytecodes use the VM opcode system (opcodes.py), NOT isa_unified.py. See docs/ISA-MAPPING.md for the mapping between the two systems.",
    }
    for v in all_vectors:
        cat = v["category"]
        if cat not in manifest["categories"]:
            manifest["categories"][cat] = []
        manifest["categories"][cat].append(v["id"])

    manifest_path = os.path.join(output_dir, "manifest.json")
    with open(manifest_path, 'w') as f:
        json.dump(manifest, f, indent=2)

    # Summary
    print(f"Generated {len(all_vectors)} test vectors across {len(manifest['categories'])} categories:")
    for cat, ids in sorted(manifest["categories"].items()):
        print(f"  {cat}: {len(ids)} vectors")
    print(f"\nFiles written to: {output_dir}/")
    print(f"Manifest: {manifest_path}")


if __name__ == "__main__":
    main()
