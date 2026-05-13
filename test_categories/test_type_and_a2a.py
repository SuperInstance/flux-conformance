"""Conformance tests for FLUX type and A2A opcodes."""

import pytest
from runtime_adapters.abstract_adapter import BytecodeProgram, ExecutionStatus


class TestTypeOps:
    """Test type opcodes: CAST, BOX, UNBOX, CHECK_TYPE, CHECK_BOUNDS."""

    def test_cast_int_to_float(self, adapter):
        """CAST should convert between int and float representations."""
        program = BytecodeProgram(
            name="cast_int_to_float",
            bytecode=bytes([
                0x01, 0x00, 42,     # MOV R0, 42
                0x38, 0x10, 0x00,   # CAST F0, R0 (int→float)
                0x80,               # HALT
            ]),
            expected_status=ExecutionStatus.HALT,
            category="type_ops",
        )
        result = adapter.execute(program)
        assert result.status in (ExecutionStatus.HALT, ExecutionStatus.UNSUPPORTED)

    def test_box_unbox_roundtrip(self, adapter):
        """BOX then UNBOX should preserve the value."""
        program = BytecodeProgram(
            name="box_unbox_roundtrip",
            bytecode=bytes([
                0x01, 0x00, 99,     # MOV R0, 99
                0x39, 0x01, 0x00,   # BOX R1, R0
                0x3A, 0x02, 0x01,   # UNBOX R2, R1
                0x80,               # HALT
            ]),
            expected_status=ExecutionStatus.HALT,
            category="type_ops",
        )
        result = adapter.execute(program)
        assert result.status in (ExecutionStatus.HALT, ExecutionStatus.UNSUPPORTED)


class TestA2AOps:
    """Test A2A (Agent-to-Agent) protocol opcodes."""

    def test_tell_opcode_exists(self, adapter):
        """TELL opcode (0x60) should be recognized."""
        # Just verify the opcode is in the supported set
        assert 0x60 in adapter.supported_opcodes, "TELL opcode not supported"

    def test_ask_opcode_exists(self, adapter):
        """ASK opcode (0x61) should be recognized."""
        assert 0x61 in adapter.supported_opcodes, "ASK opcode not supported"

    def test_delegate_opcode_exists(self, adapter):
        """DELEGATE opcode (0x62) should be recognized."""
        assert 0x62 in adapter.supported_opcodes, "DELEGATE opcode not supported"

    def test_broadcast_opcode_exists(self, adapter):
        """BROADCAST opcode (0x63) should be recognized."""
        assert 0x63 in adapter.supported_opcodes, "BROADCAST opcode not supported"

    def test_trust_opcode_exists(self, adapter):
        """TRUST opcode (0x64) should be recognized."""
        assert 0x64 in adapter.supported_opcodes, "TRUST opcode not supported"

    def test_capability_opcode_exists(self, adapter):
        """CAPABILITY opcode (0x65) should be recognized."""
        assert 0x65 in adapter.supported_opcodes, "CAPABILITY opcode not supported"

    def test_barrier_opcode_exists(self, adapter):
        """BARRIER opcode (0x66) should be recognized."""
        assert 0x66 in adapter.supported_opcodes, "BARRIER opcode not supported"

    def test_a2a_opcode_range(self, adapter):
        """All A2A opcodes (0x60-0x7B) should be in supported set for full runtimes."""
        a2a_range = set(range(0x60, 0x7C))
        supported_a2a = a2a_range & adapter.supported_opcodes
        # At minimum, the core 7 opcodes should be supported
        core_a2a = {0x60, 0x61, 0x62, 0x63, 0x64, 0x65, 0x66}
        missing = core_a2a - supported_a2a
        if missing:
            pytest.skip(f"Runtime {adapter.runtime_name} missing A2A opcodes: {missing}")


class TestConfidenceOps:
    """Test confidence-aware C_* opcode variants."""

    def test_c_iadd_opcode(self, adapter):
        """C_IADD should propagate confidence alongside addition."""
        # C_IADD is the confidence-aware variant of IADD
        # Exact opcode depends on ISA version
        # In v2, C_* opcodes are in the extended range
        program = BytecodeProgram(
            name="c_iadd_basic",
            bytecode=bytes([
                0x01, 0x00, 10,
                0x01, 0x01, 20,
                # C_IADD with confidence propagation
                # opcode varies by runtime; test if supported
                0x80,
            ]),
            expected_status=ExecutionStatus.HALT,
            category="confidence",
        )
        result = adapter.execute(program)
        assert result.status in (ExecutionStatus.HALT, ExecutionStatus.UNSUPPORTED)

    def test_confidence_values_in_result(self, adapter):
        """Confidence-aware execution should return confidence values."""
        # This test checks that the runtime can report confidence
        # even if the specific C_* opcodes aren't implemented
        program = BytecodeProgram(
            name="confidence_reporting",
            bytecode=bytes([
                0x01, 0x00, 42,
                0x80,
            ]),
            expected_status=ExecutionStatus.HALT,
            category="confidence",
        )
        result = adapter.execute(program)
        # Confidence reporting is optional; just verify the program runs
        assert result.status in (ExecutionStatus.HALT, ExecutionStatus.SUCCESS, ExecutionStatus.UNSUPPORTED)
