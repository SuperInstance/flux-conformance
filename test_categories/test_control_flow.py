"""Conformance tests for FLUX control flow opcodes.

Verifies JMP, JZ, JNZ, CALL, RET, JE, JNE across all runtimes.
"""

import pytest
from runtime_adapters.abstract_adapter import BytecodeProgram, ExecutionStatus, RegisterState


class TestControlFlow:
    """Test control flow opcodes."""

    def test_jmp_unconditional(self, adapter):
        """JMP should unconditionally jump to the target offset."""
        program = BytecodeProgram(
            name="jmp_unconditional",
            description="JMP skips over a HALT, reaches second HALT",
            bytecode=bytes([
                0x04, 0x02,   # JMP +2 (skip next 2 bytes)
                0x80,         # HALT (should be skipped)
                0x00,         # NOP
                0x80,         # HALT (should reach here)
            ]),
            expected_status=ExecutionStatus.HALT,
            category="control_flow",
        )
        result = adapter.execute(program)
        assert result.status == ExecutionStatus.HALT

    def test_jz_taken(self, adapter):
        """JZ should jump when condition is zero."""
        program = BytecodeProgram(
            name="jz_taken",
            description="JZ taken when R0 == 0",
            bytecode=bytes([
                0x01, 0x00, 0,   # MOV R0, 0
                0x05, 0x00,      # JZ R0, +2 (taken)
                0x01, 0x01, 99,  # MOV R1, 99 (should be skipped)
                0x80,            # HALT
            ]),
            expected_status=ExecutionStatus.HALT,
            expected_registers=RegisterState(int_regs={0: 0}),
            category="control_flow",
        )
        result = adapter.execute(program)
        assert result.status == ExecutionStatus.HALT
        # R1 should NOT be 99 (the MOV was skipped)
        assert result.registers.int_regs.get(1, 0) != 99

    def test_jz_not_taken(self, adapter):
        """JZ should not jump when condition is non-zero."""
        program = BytecodeProgram(
            name="jz_not_taken",
            description="JZ not taken when R0 != 0",
            bytecode=bytes([
                0x01, 0x00, 1,   # MOV R0, 1
                0x05, 0x02,      # JZ R0, +2 (not taken)
                0x01, 0x01, 42,  # MOV R1, 42 (should execute)
                0x80,            # HALT
            ]),
            expected_status=ExecutionStatus.HALT,
            expected_registers=RegisterState(int_regs={1: 42}),
            category="control_flow",
        )
        result = adapter.execute(program)
        assert result.status == ExecutionStatus.HALT
        assert result.registers.int_regs.get(1, 0) == 42

    def test_jnz_taken(self, adapter):
        """JNZ should jump when condition is non-zero."""
        program = BytecodeProgram(
            name="jnz_taken",
            description="JNZ taken when R0 != 0",
            bytecode=bytes([
                0x01, 0x00, 1,   # MOV R0, 1
                0x06, 0x02,      # JNZ R0, +2 (taken)
                0x01, 0x01, 99,  # MOV R1, 99 (should be skipped)
                0x80,            # HALT
            ]),
            expected_status=ExecutionStatus.HALT,
            category="control_flow",
        )
        result = adapter.execute(program)
        assert result.status == ExecutionStatus.HALT
        assert result.registers.int_regs.get(1, 0) != 99

    def test_call_ret(self, adapter):
        """CALL should save return address, RET should return."""
        program = BytecodeProgram(
            name="call_ret_basic",
            description="CALL a subroutine, RET back, then HALT",
            bytecode=bytes([
                0x01, 0x00, 10,  # MOV R0, 10
                0x07, 0x04,      # CALL +4 (subroutine at offset 8)
                0x80,            # HALT
                0x00,            # NOP (padding)
                0x0D, 0x00,     # INC R0 (subroutine: R0++)
                0x28,            # RET
            ]),
            expected_status=ExecutionStatus.HALT,
            expected_registers=RegisterState(int_regs={0: 11}),
            category="control_flow",
        )
        result = adapter.execute(program)
        assert result.status == ExecutionStatus.HALT
        assert result.registers.int_regs.get(0) == 11

    def test_nested_loops(self, adapter):
        """Nested loops: compute sum of 1..3 three times = 18."""
        program = BytecodeProgram(
            name="nested_loops",
            description="Outer loop 3x, inner loop sums 1+2+3. R0 = 18",
            bytecode=bytes([
                0x01, 0x00, 0,   # MOV R0, 0   (total = 0)
                0x01, 0x03, 3,   # MOV R3, 3   (outer counter)
                # outer_loop:
                0x01, 0x01, 3,   # MOV R1, 3   (inner counter)
                # inner_loop:
                0x08, 0x00, 0x00, 0x01,  # IADD R0, R0, R1
                0x0F, 0x01,      # DEC R1
                0x18, 0x01, 0x00,  # ICMP R1, 0
                0x06, 0xF6,      # JNZ inner_loop
                0x0F, 0x03,      # DEC R3
                0x18, 0x03, 0x00,  # ICMP R3, 0
                0x06, 0xF0,      # JNZ outer_loop
                0x80,            # HALT
            ]),
            expected_status=ExecutionStatus.HALT,
            expected_registers=RegisterState(int_regs={0: 18}),
            category="control_flow",
        )
        result = adapter.execute(program)
        assert result.status == ExecutionStatus.HALT
        assert result.registers.int_regs.get(0) == 18

    def test_je_jne(self, adapter):
        """JE and JNE conditional jumps based on equality."""
        program = BytecodeProgram(
            name="je_jne",
            description="Test JE (jump if equal) and JNE (jump if not equal)",
            bytecode=bytes([
                0x01, 0x00, 5,   # MOV R0, 5
                0x01, 0x01, 5,   # MOV R1, 5
                0x18, 0x00, 0x01,  # ICMP R0, R1
                0x2E, 0x02,      # JE +2 (taken: equal)
                0x01, 0x02, 0,   # MOV R2, 0 (skipped)
                0x01, 0x02, 1,   # MOV R2, 1 (reached)
                0x80,            # HALT
            ]),
            expected_status=ExecutionStatus.HALT,
            expected_registers=RegisterState(int_regs={2: 1}),
            category="control_flow",
        )
        result = adapter.execute(program)
        assert result.status == ExecutionStatus.HALT
        assert result.registers.int_regs.get(2, 0) == 1
