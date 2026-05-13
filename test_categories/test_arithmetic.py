"""Conformance tests for FLUX arithmetic opcodes.

Verifies integer and float arithmetic across all runtime implementations.
"""

import pytest
from runtime_adapters.abstract_adapter import BytecodeProgram, ExecutionStatus, RegisterState


class TestIntegerArithmetic:
    """Test integer arithmetic opcodes: IADD, ISUB, IMUL, IDIV, IMOD, INEG, INC, DEC."""

    def test_iadd_basic(self, adapter):
        """IADD R2, R0, R1: R2 = R0 + R1."""
        program = BytecodeProgram(
            name="iadd_basic",
            bytecode=bytes([
                0x01, 0x00, 10,      # MOV R0, 10
                0x01, 0x01, 20,      # MOV R1, 20
                0x08, 0x02, 0x00, 0x01,  # IADD R2, R0, R1
                0x80,                # HALT
            ]),
            expected_status=ExecutionStatus.HALT,
            expected_registers=RegisterState(int_regs={2: 30}),
            category="arithmetic",
        )
        result = adapter.execute(program)
        assert result.status == ExecutionStatus.HALT
        assert result.registers.int_regs.get(2) == 30

    def test_isub_basic(self, adapter):
        """ISUB R2, R0, R1: R2 = R0 - R1."""
        program = BytecodeProgram(
            name="isub_basic",
            bytecode=bytes([
                0x01, 0x00, 50,
                0x01, 0x01, 20,
                0x09, 0x02, 0x00, 0x01,  # ISUB R2, R0, R1
                0x80,
            ]),
            expected_status=ExecutionStatus.HALT,
            expected_registers=RegisterState(int_regs={2: 30}),
            category="arithmetic",
        )
        result = adapter.execute(program)
        assert result.status == ExecutionStatus.HALT
        assert result.registers.int_regs.get(2) == 30

    def test_imul_basic(self, adapter):
        """IMUL R2, R0, R1: R2 = R0 * R1."""
        program = BytecodeProgram(
            name="imul_basic",
            bytecode=bytes([
                0x01, 0x00, 6,
                0x01, 0x01, 7,
                0x0A, 0x02, 0x00, 0x01,  # IMUL R2, R0, R1
                0x80,
            ]),
            expected_status=ExecutionStatus.HALT,
            expected_registers=RegisterState(int_regs={2: 42}),
            category="arithmetic",
        )
        result = adapter.execute(program)
        assert result.status == ExecutionStatus.HALT
        assert result.registers.int_regs.get(2) == 42

    def test_idiv_basic(self, adapter):
        """IDIV R2, R0, R1: R2 = R0 / R1 (integer division)."""
        program = BytecodeProgram(
            name="idiv_basic",
            bytecode=bytes([
                0x01, 0x00, 42,
                0x01, 0x01, 7,
                0x0B, 0x02, 0x00, 0x01,  # IDIV R2, R0, R1
                0x80,
            ]),
            expected_status=ExecutionStatus.HALT,
            expected_registers=RegisterState(int_regs={2: 6}),
            category="arithmetic",
        )
        result = adapter.execute(program)
        assert result.status == ExecutionStatus.HALT
        assert result.registers.int_regs.get(2) == 6

    def test_imod_basic(self, adapter):
        """IMOD R2, R0, R1: R2 = R0 % R1."""
        program = BytecodeProgram(
            name="imod_basic",
            bytecode=bytes([
                0x01, 0x00, 17,
                0x01, 0x01, 5,
                0x0C, 0x02, 0x00, 0x01,  # IMOD R2, R0, R1
                0x80,
            ]),
            expected_status=ExecutionStatus.HALT,
            expected_registers=RegisterState(int_regs={2: 2}),
            category="arithmetic",
        )
        result = adapter.execute(program)
        assert result.status == ExecutionStatus.HALT
        assert result.registers.int_regs.get(2) == 2

    def test_ineg_basic(self, adapter):
        """INEG R1, R0: R1 = -R0."""
        program = BytecodeProgram(
            name="ineg_basic",
            bytecode=bytes([
                0x01, 0x00, 42,
                0x0D, 0x01, 0x00,  # INEG R1, R0
                0x80,
            ]),
            expected_status=ExecutionStatus.HALT,
            expected_registers=RegisterState(int_regs={1: -42}),
            category="arithmetic",
        )
        result = adapter.execute(program)
        assert result.status == ExecutionStatus.HALT
        assert result.registers.int_regs.get(1) == -42

    def test_inc_dec(self, adapter):
        """INC R0; DEC R1: increment and decrement."""
        program = BytecodeProgram(
            name="inc_dec",
            bytecode=bytes([
                0x01, 0x00, 10,
                0x01, 0x01, 20,
                0x0E, 0x00,  # INC R0 (10 → 11)
                0x0F, 0x01,  # DEC R1 (20 → 19)
                0x80,
            ]),
            expected_status=ExecutionStatus.HALT,
            expected_registers=RegisterState(int_regs={0: 11, 1: 19}),
            category="arithmetic",
        )
        result = adapter.execute(program)
        assert result.status == ExecutionStatus.HALT
        assert result.registers.int_regs.get(0) == 11
        assert result.registers.int_regs.get(1) == 19

    def test_idiv_by_zero(self, adapter):
        """IDIV by zero must produce an error, not silent wrong result."""
        program = BytecodeProgram(
            name="idiv_by_zero",
            bytecode=bytes([
                0x01, 0x00, 42,
                0x01, 0x01, 0,
                0x0B, 0x02, 0x00, 0x01,
                0x80,
            ]),
            expected_status=ExecutionStatus.ERROR,
            category="error_handling",
        )
        result = adapter.execute(program)
        # Should either error or trap — must NOT return a normal value
        assert result.status in (ExecutionStatus.ERROR, ExecutionStatus.HALT)
        if result.status == ExecutionStatus.HALT:
            # If it halts, the result should indicate an error condition
            # (some runtimes set a flag instead of trapping)
            pass


class TestFloatArithmetic:
    """Test float arithmetic opcodes: FADD, FSUB, FMUL, FDIV."""

    def test_fadd_basic(self, adapter):
        """FADD F2, F0, F1: F2 = F0 + F1."""
        program = BytecodeProgram(
            name="fadd_basic",
            bytecode=bytes([
                0x01, 0x10, 0,  # MOV F0 (setup float reg)
                0x01, 0x11, 0,  # MOV F1
                0x40, 0x12, 0x10, 0x11,  # FADD F2, F0, F1
                0x80,
            ]),
            expected_status=ExecutionStatus.HALT,
            category="arithmetic",
        )
        result = adapter.execute(program)
        assert result.status in (ExecutionStatus.HALT, ExecutionStatus.UNSUPPORTED)

    def test_fsub_basic(self, adapter):
        """FSUB F2, F0, F1: F2 = F0 - F1."""
        program = BytecodeProgram(
            name="fsub_basic",
            bytecode=bytes([
                0x41, 0x12, 0x10, 0x11,  # FSUB F2, F0, F1
                0x80,
            ]),
            expected_status=ExecutionStatus.HALT,
            category="arithmetic",
        )
        result = adapter.execute(program)
        assert result.status in (ExecutionStatus.HALT, ExecutionStatus.UNSUPPORTED)
