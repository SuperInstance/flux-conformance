"""Conformance tests for FLUX instruction encoding and decoding.

Verifies that all runtime adapters encode and decode instructions
consistently with the ISA specification.
"""

import pytest
from runtime_adapters.abstract_adapter import BytecodeProgram, ExecutionStatus, RegisterState
from bytecode_fixtures import ALL_FIXTURES


class TestEncodingFormats:
    """Test that instruction encoding matches ISA spec formats."""

    def test_format_a_single_byte(self, adapter):
        """Format A: 1-byte instructions (NOP, HALT, RET)."""
        # NOP = 0x00
        encoded = adapter.encode_instruction(0x00, ())
        assert encoded == bytes([0x00])
        assert len(encoded) == 1

        # HALT = 0x80
        encoded = adapter.encode_instruction(0x80, ())
        assert encoded == bytes([0x80])
        assert len(encoded) == 1

    def test_format_b_two_bytes(self, adapter):
        """Format B: 2-byte instructions (opcode + register)."""
        # PUSH R0 = 0x20 0x00
        encoded = adapter.encode_instruction(0x20, (0,))
        assert encoded == bytes([0x20, 0x00])
        assert len(encoded) == 2

        # POP R5 = 0x21 0x05
        encoded = adapter.encode_instruction(0x21, (5,))
        assert encoded == bytes([0x21, 0x05])

    def test_format_c_three_bytes(self, adapter):
        """Format C: 3-byte instructions (opcode + register + imm8)."""
        # MOV R0, 42 = 0x01 0x00 0x2A
        encoded = adapter.encode_instruction(0x01, (0, 42))
        assert encoded == bytes([0x01, 0x00, 42])
        assert len(encoded) == 3

    def test_format_e_four_bytes(self, adapter):
        """Format E: 4-byte three-register format (opcode + rd + rs1 + rs2)."""
        # IADD R2, R0, R1 = 0x08 0x02 0x00 0x01
        encoded = adapter.encode_instruction(0x08, (2, 0, 1))
        assert encoded == bytes([0x08, 0x02, 0x00, 0x01])
        assert len(encoded) == 4

    def test_encode_decode_roundtrip(self, adapter):
        """Encode then decode should return the original instruction."""
        test_cases = [
            (0x00, ()),        # NOP
            (0x80, ()),        # HALT
            (0x01, (0, 42)),   # MOV R0, 42
            (0x08, (2, 0, 1)), # IADD R2, R0, R1
        ]

        for opcode, operands in test_cases:
            encoded = adapter.encode_instruction(opcode, operands)
            decoded_opcode, decoded_operands, length = adapter.decode_instruction(encoded)
            assert decoded_opcode == opcode, f"Opcode mismatch for {opcode:#x}"
            assert length == len(encoded), f"Length mismatch for {opcode:#x}"


class TestLittleEndian:
    """Verify little-endian encoding for multi-byte immediates."""

    def test_imm16_little_endian(self, adapter):
        """All multi-byte immediate values must be little-endian."""
        # MOVI R0, 0x1234 → opcode, reg, 0x34, 0x12 (little-endian)
        encoded = adapter.encode_instruction(0x2C, (0, 0x1234))
        if len(encoded) >= 4:
            # The immediate portion should be LE
            imm_bytes = encoded[2:4]
            assert imm_bytes[0] == 0x34  # low byte first
            assert imm_bytes[1] == 0x12  # high byte second


class TestBytecodeFixtures:
    """Verify all bytecode fixtures have valid structure."""

    def test_all_fixtures_have_names(self):
        """Every fixture must have a descriptive name."""
        for fixture in ALL_FIXTURES:
            assert fixture.name, f"Fixture missing name"
            assert len(fixture.name) > 0

    def test_all_fixtures_have_bytecode(self):
        """Every fixture must have non-empty bytecode."""
        for fixture in ALL_FIXTURES:
            assert len(fixture.bytecode) > 0, f"Fixture {fixture.name} has empty bytecode"

    def test_all_fixtures_have_expected_status(self):
        """Every fixture must declare an expected execution status."""
        for fixture in ALL_FIXTURES:
            assert fixture.expected_status is not None, f"Fixture {fixture.name} missing expected status"

    def test_all_fixtures_list_opcodes_used(self):
        """Every fixture should list the opcodes it exercises."""
        for fixture in ALL_FIXTURES:
            assert len(fixture.opcodes_used) > 0, f"Fixture {fixture.name} has no opcodes listed"

    def test_fixtures_cover_key_categories(self):
        """The fixture set should cover the main opcode categories."""
        categories = {f.category for f in ALL_FIXTURES}
        required = {"arithmetic", "control_flow", "stack", "memory"}
        for cat in required:
            assert cat in categories, f"Missing fixture category: {cat}"
