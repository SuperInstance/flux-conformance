"""Hand-crafted FLUX bytecode fixtures for conformance testing.

Each fixture is a BytecodeProgram with known expected results that can
be verified against any FLUX runtime implementation.
"""

from runtime_adapters.abstract_adapter import BytecodeProgram, ExecutionStatus, RegisterState


def euclidean_gcd() -> BytecodeProgram:
    """Euclidean GCD algorithm: GCD(48, 18) = 6.

    Uses: MOV, ICMP, JE, IGT, JZ, ISUB, JMP, HALT
    """
    return BytecodeProgram(
        name="euclidean_gcd",
        description="Compute GCD(48, 18) using Euclidean algorithm. Expected: R0 = 6",
        bytecode=bytes([
            0x01, 0x00, 48,     # MOV R0, 48  (a = 48)
            0x01, 0x01, 18,     # MOV R1, 18  (b = 18)
            # loop:
            0x18, 0x00, 0x01,   # ICMP R0, R1
            0x1C, 0x10,         # JE done (+16 bytes from here)
            0x1D, 0x00, 0x01,   # IGT R0, R1
            0x06, 0x08,         # JZ swap (+8 bytes)
            0x09, 0x00, 0x01,   # ISUB R0, R1  (a = a - b)
            0x04, 0xF2,         # JMP loop (-14 bytes back)
            # swap:
            0x09, 0x01, 0x00,   # ISUB R1, R0  (b = b - a)
            0x04, 0xF2,         # JMP loop
            # done:
            0x80,               # HALT
        ]),
        expected_status=ExecutionStatus.HALT,
        expected_registers=RegisterState(int_regs={0: 6, 1: 6}),
        category="arithmetic",
        opcodes_used=[0x01, 0x18, 0x1C, 0x1D, 0x06, 0x09, 0x04, 0x80],
    )


def fibonacci_sequence() -> BytecodeProgram:
    """Fibonacci: compute fib(10) = 55.

    Uses: MOV, IADD, MOV (register-to-register), ISUB, ICMP, JZ, JMP, HALT
    """
    return BytecodeProgram(
        name="fibonacci_10",
        description="Compute fib(10) = 55. R0=prev, R1=curr, R2=counter",
        bytecode=bytes([
            0x01, 0x00, 0,      # MOV R0, 0   (prev = 0)
            0x01, 0x01, 1,      # MOV R1, 1   (curr = 1)
            0x01, 0x02, 10,     # MOV R2, 10  (counter = 10)
            # loop:
            0x08, 0x03, 0x00, 0x01,  # IADD R3, R0, R1  (next = prev + curr)
            0x01, 0x00, 0x01,  # MOV R0, R1  (prev = curr) [simplified]
            0x01, 0x01, 0x03,  # MOV R1, R3  (curr = next)
            0x0E, 0x02,        # DEC R2      (counter--)
            0x18, 0x02, 0x00,  # ICMP R2, 0
            0x06, 0xF0,        # JNZ loop    (-16 bytes back)
            # done:
            0x80,               # HALT  (result in R1 = 55)
        ]),
        expected_status=ExecutionStatus.HALT,
        expected_registers=RegisterState(int_regs={1: 55}),
        category="arithmetic",
        opcodes_used=[0x01, 0x08, 0x0E, 0x18, 0x06, 0x80],
    )


def simple_loop() -> BytecodeProgram:
    """Simple counting loop: sum 1+2+3+4+5 = 15.

    Uses: MOV, IADD, INC, ICMP, JNZ, HALT
    """
    return BytecodeProgram(
        name="simple_loop_sum",
        description="Sum 1+2+3+4+5 = 15. R0=accumulator, R1=counter",
        bytecode=bytes([
            0x01, 0x00, 0,      # MOV R0, 0   (sum = 0)
            0x01, 0x01, 1,      # MOV R1, 1   (i = 1)
            # loop:
            0x08, 0x00, 0x00, 0x01,  # IADD R0, R0, R1  (sum += i)
            0x0D, 0x01,        # INC R1      (i++)
            0x01, 0x02, 6,     # MOV R2, 6   (limit)
            0x18, 0x01, 0x02,  # ICMP R1, R2
            0x06, 0xF0,        # JNZ loop
            0x80,               # HALT  (R0 = 15)
        ]),
        expected_status=ExecutionStatus.HALT,
        expected_registers=RegisterState(int_regs={0: 15, 1: 6}),
        category="control_flow",
        opcodes_used=[0x01, 0x08, 0x0D, 0x18, 0x06, 0x80],
    )


def function_call_return() -> BytecodeProgram:
    """Function call and return: call double(5), result = 10.

    Uses: MOV, CALL, IADD, RET, HALT
    """
    return BytecodeProgram(
        name="function_call_return",
        description="Call a function that doubles R0. Expected: R0 = 10",
        bytecode=bytes([
            0x01, 0x00, 5,      # MOV R0, 5   (arg = 5)
            0x07, 0x10,         # CALL double (+16 bytes)
            0x80,               # HALT  (R0 = 10)
            # padding
            0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00, 0x00,
            0x00, 0x00, 0x00,
            # double:
            0x08, 0x00, 0x00, 0x00,  # IADD R0, R0, R0  (double it)
            0x28,               # RET
        ]),
        expected_status=ExecutionStatus.HALT,
        expected_registers=RegisterState(int_regs={0: 10}),
        category="control_flow",
        opcodes_used=[0x01, 0x07, 0x08, 0x28, 0x80],
    )


def stack_manipulation() -> BytecodeProgram:
    """Stack operations: PUSH, POP, DUP, SWAP.

    Uses: MOV, PUSH, POP, DUP, SWAP, HALT
    """
    return BytecodeProgram(
        name="stack_manipulation",
        description="Push 42, push 7, swap, pop into R0. Expected: R0 = 42",
        bytecode=bytes([
            0x01, 0x00, 42,     # MOV R0, 42
            0x01, 0x01, 7,      # MOV R1, 7
            0x20, 0x00,         # PUSH R0  (stack: [42])
            0x20, 0x01,         # PUSH R1  (stack: [42, 7])
            0x23,               # SWAP     (stack: [7, 42])
            0x21, 0x02,         # POP R2   (R2 = 42, stack: [7])
            0x21, 0x00,         # POP R0   (R0 = 7, stack: [])
            0x80,               # HALT
        ]),
        expected_status=ExecutionStatus.HALT,
        expected_registers=RegisterState(int_regs={0: 7, 2: 42}),
        category="stack",
        opcodes_used=[0x01, 0x20, 0x21, 0x23, 0x80],
    )


def memory_operations() -> BytecodeProgram:
    """Memory store and load operations.

    Uses: MOV, STORE, LOAD, HALT
    """
    return BytecodeProgram(
        name="memory_store_load",
        description="Store 99 at address 100, load it back into R1. Expected: R1 = 99",
        bytecode=bytes([
            0x01, 0x00, 99,     # MOV R0, 99   (value)
            0x01, 0x01, 100,    # MOV R1, 100  (address)
            0x03, 0x00, 0x01,   # STORE R0, [R1]  (mem[100] = 99)
            0x02, 0x02, 0x01,   # LOAD R2, [R1]   (R2 = mem[100] = 99)
            0x80,               # HALT
        ]),
        expected_status=ExecutionStatus.HALT,
        expected_registers=RegisterState(int_regs={0: 99, 1: 100, 2: 99}),
        category="memory",
        opcodes_used=[0x01, 0x03, 0x02, 0x80],
    )


def bitwise_operations() -> BytecodeProgram:
    """Bitwise AND, OR, XOR, NOT, shift operations.

    Uses: MOV, IAND, IOR, IXOR, ISHL, ISHR, HALT
    """
    return BytecodeProgram(
        name="bitwise_ops",
        description="Bitwise ops on 0xFF and 0x0F. Expected results in R2-R5",
        bytecode=bytes([
            0x01, 0x00, 0xFF,   # MOV R0, 0xFF
            0x01, 0x01, 0x0F,   # MOV R1, 0x0F
            0x10, 0x02, 0x00, 0x01,  # IAND R2, R0, R1  (R2 = 0x0F)
            0x11, 0x03, 0x00, 0x01,  # IOR  R3, R0, R1  (R3 = 0xFF)
            0x12, 0x04, 0x00, 0x01,  # IXOR R4, R0, R1  (R4 = 0xF0)
            0x14, 0x05, 0x00, 0x04,  # ISHL R5, R0, 4   (R5 = 0xFF0)
            0x80,               # HALT
        ]),
        expected_status=ExecutionStatus.HALT,
        expected_registers=RegisterState(int_regs={
            0: 0xFF, 1: 0x0F,
            2: 0x0F, 3: 0xFF, 4: 0xF0, 5: 0xFF0,
        }),
        category="arithmetic",
        opcodes_used=[0x01, 0x10, 0x11, 0x12, 0x14, 0x80],
    )


def comparison_operations() -> BytecodeProgram:
    """Comparison operations: IEQ, ILT, IGT, ILE, IGE.

    Uses: MOV, IEQ, ILT, IGT, HALT
    """
    return BytecodeProgram(
        name="comparison_ops",
        description="Compare 5 and 10. Expected: IEQ=0, ILT=1, IGT=0",
        bytecode=bytes([
            0x01, 0x00, 5,      # MOV R0, 5
            0x01, 0x01, 10,     # MOV R1, 10
            0x19, 0x02, 0x00, 0x01,  # IEQ R2, R0, R1  (R2 = 0, not equal)
            0x1A, 0x03, 0x00, 0x01,  # ILT R3, R0, R1  (R3 = 1, 5 < 10)
            0x1D, 0x04, 0x00, 0x01,  # IGT R4, R0, R1  (R4 = 0, 5 > 10 is false)
            0x80,               # HALT
        ]),
        expected_status=ExecutionStatus.HALT,
        expected_registers=RegisterState(int_regs={0: 5, 1: 10, 2: 0, 3: 1, 4: 0}),
        category="arithmetic",
        opcodes_used=[0x01, 0x19, 0x1A, 0x1D, 0x80],
    )


def type_operations() -> BytecodeProgram:
    """Type operations: CAST, BOX, UNBOX.

    Uses: MOV, CAST, BOX, UNBOX, HALT
    """
    return BytecodeProgram(
        name="type_ops",
        description="Cast int to float, box/unbox. Expected: F0 = 42.0",
        bytecode=bytes([
            0x01, 0x00, 42,     # MOV R0, 42  (int)
            0x38, 0x00, 0x00,   # CAST R0, int→float  (F0 = 42.0)
            0x39, 0x01, 0x00,   # BOX R1, R0   (R1 = boxed(42))
            0x3A, 0x02, 0x01,   # UNBOX R2, R1 (R2 = unboxed(42))
            0x80,               # HALT
        ]),
        expected_status=ExecutionStatus.HALT,
        expected_registers=RegisterState(
            int_regs={0: 42},
            float_regs={0: 42.0},
        ),
        category="type_ops",
        opcodes_used=[0x01, 0x38, 0x39, 0x3A, 0x80],
    )


def nop_halt() -> BytecodeProgram:
    """Simplest valid program: NOP + HALT."""
    return BytecodeProgram(
        name="nop_halt",
        description="Simplest valid FLUX program: NOP then HALT",
        bytecode=bytes([0x00, 0x80]),
        expected_status=ExecutionStatus.HALT,
        category="control_flow",
        opcodes_used=[0x00, 0x80],
    )


def div_by_zero() -> BytecodeProgram:
    """Division by zero: should produce an error or trap.

    Uses: MOV, IDIV, HALT
    """
    return BytecodeProgram(
        name="div_by_zero",
        description="IDIV by zero. Expected: error or trap, not normal halt",
        bytecode=bytes([
            0x01, 0x00, 42,     # MOV R0, 42
            0x01, 0x01, 0,      # MOV R1, 0
            0x0B, 0x02, 0x00, 0x01,  # IDIV R2, R0, R1  (42 / 0)
            0x80,               # HALT (should not reach here)
        ]),
        expected_status=ExecutionStatus.ERROR,
        category="error_handling",
        opcodes_used=[0x01, 0x0B, 0x80],
    )


# All fixtures as a list for easy iteration
ALL_FIXTURES = [
    nop_halt(),
    euclidean_gcd(),
    fibonacci_sequence(),
    simple_loop(),
    function_call_return(),
    stack_manipulation(),
    memory_operations(),
    bitwise_operations(),
    comparison_operations(),
    type_operations(),
    div_by_zero(),
]
