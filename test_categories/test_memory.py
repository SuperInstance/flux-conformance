"""Conformance tests for FLUX memory and stack opcodes."""

import pytest
from runtime_adapters.abstract_adapter import BytecodeProgram, ExecutionStatus, RegisterState


class TestMemoryOps:
    """Test memory opcodes: LOAD, STORE, REGION_CREATE, REGION_DESTROY, MEMCOPY."""

    def test_store_load_roundtrip(self, adapter):
        """STORE a value, then LOAD it back — must get the same value."""
        program = BytecodeProgram(
            name="store_load_roundtrip",
            bytecode=bytes([
                0x01, 0x00, 42,     # MOV R0, 42
                0x01, 0x01, 200,    # MOV R1, 200 (address)
                0x03, 0x00, 0x01,   # STORE R0, [R1]
                0x02, 0x02, 0x01,   # LOAD R2, [R1]
                0x80,               # HALT
            ]),
            expected_status=ExecutionStatus.HALT,
            expected_registers=RegisterState(int_regs={0: 42, 2: 42}),
            category="memory",
        )
        result = adapter.execute(program)
        assert result.status == ExecutionStatus.HALT
        assert result.registers.int_regs.get(2) == 42

    def test_multiple_stores(self, adapter):
        """Store multiple values at different addresses."""
        program = BytecodeProgram(
            name="multiple_stores",
            bytecode=bytes([
                0x01, 0x00, 10,     # MOV R0, 10
                0x01, 0x01, 100,    # MOV R1, 100
                0x01, 0x02, 20,     # MOV R2, 20
                0x01, 0x03, 200,    # MOV R3, 200
                0x03, 0x00, 0x01,   # STORE R0, [R1]  (mem[100] = 10)
                0x03, 0x02, 0x03,   # STORE R2, [R3]  (mem[200] = 20)
                0x02, 0x04, 0x01,   # LOAD R4, [R1]   (R4 = 10)
                0x02, 0x05, 0x03,   # LOAD R5, [R3]   (R5 = 20)
                0x80,               # HALT
            ]),
            expected_status=ExecutionStatus.HALT,
            expected_registers=RegisterState(int_regs={4: 10, 5: 20}),
            category="memory",
        )
        result = adapter.execute(program)
        assert result.status == ExecutionStatus.HALT
        assert result.registers.int_regs.get(4) == 10
        assert result.registers.int_regs.get(5) == 20


class TestStackOps:
    """Test stack opcodes: PUSH, POP, DUP, SWAP, ROT."""

    def test_push_pop_roundtrip(self, adapter):
        """PUSH then POP should preserve the value."""
        program = BytecodeProgram(
            name="push_pop_roundtrip",
            bytecode=bytes([
                0x01, 0x00, 42,     # MOV R0, 42
                0x20, 0x00,         # PUSH R0
                0x01, 0x00, 0,      # MOV R0, 0  (clobber R0)
                0x21, 0x01,         # POP R1  (R1 = 42)
                0x80,               # HALT
            ]),
            expected_status=ExecutionStatus.HALT,
            expected_registers=RegisterState(int_regs={0: 0, 1: 42}),
            category="stack",
        )
        result = adapter.execute(program)
        assert result.status == ExecutionStatus.HALT
        assert result.registers.int_regs.get(1) == 42

    def test_dup_top_of_stack(self, adapter):
        """DUP should duplicate the top of the stack."""
        program = BytecodeProgram(
            name="dup_top",
            bytecode=bytes([
                0x01, 0x00, 7,      # MOV R0, 7
                0x20, 0x00,         # PUSH R0  (stack: [7])
                0x22,               # DUP       (stack: [7, 7])
                0x21, 0x01,         # POP R1   (R1 = 7, stack: [7])
                0x21, 0x02,         # POP R2   (R2 = 7, stack: [])
                0x80,               # HALT
            ]),
            expected_status=ExecutionStatus.HALT,
            expected_registers=RegisterState(int_regs={1: 7, 2: 7}),
            category="stack",
        )
        result = adapter.execute(program)
        assert result.status == ExecutionStatus.HALT
        assert result.registers.int_regs.get(1) == 7
        assert result.registers.int_regs.get(2) == 7

    def test_swap_top_two(self, adapter):
        """SWAP should exchange the top two stack elements."""
        program = BytecodeProgram(
            name="swap_top_two",
            bytecode=bytes([
                0x01, 0x00, 1,      # MOV R0, 1
                0x01, 0x01, 2,      # MOV R1, 2
                0x20, 0x00,         # PUSH R0  (stack: [1])
                0x20, 0x01,         # PUSH R1  (stack: [1, 2])
                0x23,               # SWAP      (stack: [2, 1])
                0x21, 0x02,         # POP R2   (R2 = 1, top was 1 after swap)
                0x21, 0x03,         # POP R3   (R3 = 2)
                0x80,               # HALT
            ]),
            expected_status=ExecutionStatus.HALT,
            category="stack",
        )
        result = adapter.execute(program)
        assert result.status == ExecutionStatus.HALT

    def test_stack_lifo_order(self, adapter):
        """Stack must follow LIFO (last in, first out) order."""
        program = BytecodeProgram(
            name="stack_lifo",
            bytecode=bytes([
                0x01, 0x00, 1,
                0x01, 0x01, 2,
                0x01, 0x02, 3,
                0x20, 0x00,  # PUSH 1
                0x20, 0x01,  # PUSH 2
                0x20, 0x02,  # PUSH 3
                0x21, 0x03,  # POP → R3 = 3 (last pushed)
                0x21, 0x04,  # POP → R4 = 2
                0x21, 0x05,  # POP → R5 = 1 (first pushed)
                0x80,
            ]),
            expected_status=ExecutionStatus.HALT,
            expected_registers=RegisterState(int_regs={3: 3, 4: 2, 5: 1}),
            category="stack",
        )
        result = adapter.execute(program)
        assert result.status == ExecutionStatus.HALT
        assert result.registers.int_regs.get(3) == 3
        assert result.registers.int_regs.get(4) == 2
        assert result.registers.int_regs.get(5) == 1
