"""Conformance tests for FLUX confidence-aware C_* opcode variants.

The FLUX ISA defines confidence-aware variants of key opcodes (prefixed
with C_).  These opcodes perform the same computation as their base
counterparts but also modify a **confidence accumulator** that tracks
the reliability of the computed result.

Confidence semantics (ISA v1.0):
- Each C_* opcode applies a decay factor to the confidence accumulator.
- The accumulator starts at 1.0 (full confidence).
- The decay factor is opcode-specific (e.g., 0.95 for arithmetic, 0.90
  for communication, 0.85 for delegation/broadcast).

These tests verify:
1. C_* opcodes produce the same computational result as base opcodes.
2. The confidence accumulator decays correctly.
3. Multiple C_* operations compound the decay multiplicatively.
"""

from __future__ import annotations

import pytest

from runtime_adapters.abstract_adapter import RuntimeStatus
from runtime_adapters.python_adapter import FluxAssembler, FluxOpcode


# ===================================================================
# Confidence-aware arithmetic
# ===================================================================

class TestConfidenceArithmetic:
    """C_ADD, C_SUB, C_MUL: arithmetic with confidence decay."""

    def test_c_add_result(self, adapter) -> None:  # type: ignore[valid-type]
        """C_ADD should produce the same result as IADD."""
        op = FluxOpcode
        asm = FluxAssembler()

        asm.emit(op.MOVI, 0, 0, 10)
        asm.emit(op.MOVI, 1, 0, 20)
        asm.emit(op.C_ADD, 2, 0, 1)
        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert result.status in (RuntimeStatus.HALT, RuntimeStatus.OK)
        assert result.registers.get_int(2) == 30

    def test_c_add_confidence_decay(self, adapter) -> None:  # type: ignore[valid-type]
        """C_ADD should decay confidence by 0.95."""
        op = FluxOpcode
        asm = FluxAssembler()

        asm.emit(op.MOVI, 0, 0, 10)
        asm.emit(op.MOVI, 1, 0, 20)
        asm.emit(op.C_ADD, 2, 0, 1)
        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert abs(result.registers.confidence - 0.95) < 1e-6

    def test_c_sub_result(self, adapter) -> None:  # type: ignore[valid-type]
        """C_SUB should produce the same result as ISUB."""
        op = FluxOpcode
        asm = FluxAssembler()

        asm.emit(op.MOVI, 0, 0, 30)
        asm.emit(op.MOVI, 1, 0, 12)
        asm.emit(op.C_SUB, 2, 0, 1)
        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert result.status in (RuntimeStatus.HALT, RuntimeStatus.OK)
        assert result.registers.get_int(2) == 18

    def test_c_sub_confidence_decay(self, adapter) -> None:  # type: ignore[valid-type]
        """C_SUB should decay confidence by 0.95."""
        op = FluxOpcode
        asm = FluxAssembler()

        asm.emit(op.MOVI, 0, 0, 30)
        asm.emit(op.MOVI, 1, 0, 12)
        asm.emit(op.C_SUB, 2, 0, 1)
        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert abs(result.registers.confidence - 0.95) < 1e-6

    def test_c_mul_result(self, adapter) -> None:  # type: ignore[valid-type]
        """C_MUL should produce the same result as IMUL."""
        op = FluxOpcode
        asm = FluxAssembler()

        asm.emit(op.MOVI, 0, 0, 6)
        asm.emit(op.MOVI, 1, 0, 7)
        asm.emit(op.C_MUL, 2, 0, 1)
        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert result.status in (RuntimeStatus.HALT, RuntimeStatus.OK)
        assert result.registers.get_int(2) == 42

    def test_c_mul_confidence_decay(self, adapter) -> None:  # type: ignore[valid-type]
        """C_MUL should decay confidence by 0.95."""
        op = FluxOpcode
        asm = FluxAssembler()

        asm.emit(op.MOVI, 0, 0, 6)
        asm.emit(op.MOVI, 1, 0, 7)
        asm.emit(op.C_MUL, 2, 0, 1)
        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert abs(result.registers.confidence - 0.95) < 1e-6


# ===================================================================
# Confidence-aware data movement
# ===================================================================

class TestConfidenceMove:
    """C_MOV: move with confidence decay."""

    def test_c_mov_result(self, adapter) -> None:  # type: ignore[valid-type]
        """C_MOV should produce the same result as MOV."""
        op = FluxOpcode
        asm = FluxAssembler()

        asm.emit(op.MOVI, 0, 0, 42)
        asm.emit(op.C_MOV, 1, 0)
        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert result.status in (RuntimeStatus.HALT, RuntimeStatus.OK)
        assert result.registers.get_int(1) == 42

    def test_c_mov_confidence_decay(self, adapter) -> None:  # type: ignore[valid-type]
        """C_MOV should decay confidence by 0.95."""
        op = FluxOpcode
        asm = FluxAssembler()

        asm.emit(op.MOVI, 0, 0, 42)
        asm.emit(op.C_MOV, 1, 0)
        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert abs(result.registers.confidence - 0.95) < 1e-6


# ===================================================================
# Confidence-aware communication
# ===================================================================

class TestConfidenceCommunication:
    """C_TELL, C_ASK, C_DELEGATE, C_BROADCAST, C_TRUST, C_CAP."""

    def test_c_tell_confidence_decay(self, adapter) -> None:  # type: ignore[valid-type]
        """C_TELL should decay confidence by 0.90."""
        op = FluxOpcode
        asm = FluxAssembler()

        asm.emit(op.C_TELL, 0, 1)
        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert result.status in (RuntimeStatus.HALT, RuntimeStatus.OK)
        assert abs(result.registers.confidence - 0.90) < 1e-6

    def test_c_ask_confidence_decay(self, adapter) -> None:  # type: ignore[valid-type]
        """C_ASK should decay confidence by 0.90."""
        op = FluxOpcode
        asm = FluxAssembler()

        asm.emit(op.C_ASK, 0, 1)
        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert result.status in (RuntimeStatus.HALT, RuntimeStatus.OK)
        assert abs(result.registers.confidence - 0.90) < 1e-6

    def test_c_delegate_confidence_decay(self, adapter) -> None:  # type: ignore[valid-type]
        """C_DELEGATE should decay confidence by 0.85."""
        op = FluxOpcode
        asm = FluxAssembler()

        asm.emit(op.C_DELEGATE, 0, 1)
        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert result.status in (RuntimeStatus.HALT, RuntimeStatus.OK)
        assert abs(result.registers.confidence - 0.85) < 1e-6

    def test_c_broadcast_confidence_decay(self, adapter) -> None:  # type: ignore[valid-type]
        """C_BROADCAST should decay confidence by 0.85."""
        op = FluxOpcode
        asm = FluxAssembler()

        asm.emit(op.C_BROADCAST, 0, 1)
        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert result.status in (RuntimeStatus.HALT, RuntimeStatus.OK)
        assert abs(result.registers.confidence - 0.85) < 1e-6

    def test_c_trust_confidence_decay(self, adapter) -> None:  # type: ignore[valid-type]
        """C_TRUST should decay confidence by 0.95."""
        op = FluxOpcode
        asm = FluxAssembler()

        asm.emit(op.C_TRUST, 0, 1)
        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert result.status in (RuntimeStatus.HALT, RuntimeStatus.OK)
        assert abs(result.registers.confidence - 0.95) < 1e-6

    def test_c_cap_confidence_decay(self, adapter) -> None:  # type: ignore[valid-type]
        """C_CAP should decay confidence by 0.95."""
        op = FluxOpcode
        asm = FluxAssembler()

        asm.emit(op.C_CAP, 0, 1)
        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert result.status in (RuntimeStatus.HALT, RuntimeStatus.OK)
        assert abs(result.registers.confidence - 0.95) < 1e-6


# ===================================================================
# Compounding decay
# ===================================================================

class TestCompoundingConfidence:
    """Multiple C_* operations compound confidence decay multiplicatively."""

    def test_two_c_adds(self, adapter) -> None:  # type: ignore[valid-type]
        """Two C_ADD operations: confidence = 1.0 * 0.95 * 0.95 = 0.9025."""
        op = FluxOpcode
        asm = FluxAssembler()

        asm.emit(op.MOVI, 0, 0, 10)
        asm.emit(op.MOVI, 1, 0, 5)
        asm.emit(op.C_ADD, 2, 0, 1)    # confidence = 0.95
        asm.emit(op.C_ADD, 3, 2, 1)    # confidence = 0.95 * 0.95 = 0.9025
        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert result.status in (RuntimeStatus.HALT, RuntimeStatus.OK)
        assert result.registers.get_int(2) == 15
        assert result.registers.get_int(3) == 20
        assert abs(result.registers.confidence - 0.9025) < 1e-4

    def test_mixed_confidence_ops(self, adapter) -> None:  # type: ignore[valid-type]
        """C_ADD then C_TELL: confidence = 1.0 * 0.95 * 0.90 = 0.855."""
        op = FluxOpcode
        asm = FluxAssembler()

        asm.emit(op.MOVI, 0, 0, 10)
        asm.emit(op.MOVI, 1, 0, 5)
        asm.emit(op.C_ADD, 2, 0, 1)    # confidence = 0.95
        asm.emit(op.C_TELL, 0, 1)      # confidence = 0.95 * 0.90 = 0.855
        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert result.status in (RuntimeStatus.HALT, RuntimeStatus.OK)
        assert abs(result.registers.confidence - 0.855) < 1e-4

    def test_base_ops_no_confidence_decay(self, adapter) -> None:  # type: ignore[valid-type]
        """Regular (non-C_) opcodes should NOT decay confidence."""
        op = FluxOpcode
        asm = FluxAssembler()

        asm.emit(op.MOVI, 0, 0, 10)
        asm.emit(op.MOVI, 1, 0, 5)
        asm.emit(op.IADD, 2, 0, 1)    # no confidence decay
        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert result.status in (RuntimeStatus.HALT, RuntimeStatus.OK)
        assert result.registers.get_int(2) == 15
        assert abs(result.registers.confidence - 1.0) < 1e-6


# ===================================================================
# C_* opcode encoding
# ===================================================================

class TestConfidenceOpcodeEncoding:
    """Verify C_* opcode byte values match the ISA spec."""

    def test_c_tell_opcode_value(self) -> None:
        """C_TELL must be 0x70."""
        assert FluxOpcode.C_TELL == 0x70

    def test_c_ask_opcode_value(self) -> None:
        """C_ASK must be 0x71."""
        assert FluxOpcode.C_ASK == 0x71

    def test_c_delegate_opcode_value(self) -> None:
        """C_DELEGATE must be 0x72."""
        assert FluxOpcode.C_DELEGATE == 0x72

    def test_c_broadcast_opcode_value(self) -> None:
        """C_BROADCAST must be 0x73."""
        assert FluxOpcode.C_BROADCAST == 0x73

    def test_c_trust_opcode_value(self) -> None:
        """C_TRUST must be 0x74."""
        assert FluxOpcode.C_TRUST == 0x74

    def test_c_cap_opcode_value(self) -> None:
        """C_CAP must be 0x75."""
        assert FluxOpcode.C_CAP == 0x75

    def test_c_share_opcode_value(self) -> None:
        """C_SHARE must be 0x76."""
        assert FluxOpcode.C_SHARE == 0x76

    def test_c_revoke_opcode_value(self) -> None:
        """C_REVOKE must be 0x77."""
        assert FluxOpcode.C_REVOKE == 0x77

    def test_c_add_opcode_value(self) -> None:
        """C_ADD must be 0x78."""
        assert FluxOpcode.C_ADD == 0x78

    def test_c_sub_opcode_value(self) -> None:
        """C_SUB must be 0x79."""
        assert FluxOpcode.C_SUB == 0x79

    def test_c_mul_opcode_value(self) -> None:
        """C_MUL must be 0x7A."""
        assert FluxOpcode.C_MUL == 0x7A

    def test_c_mov_opcode_value(self) -> None:
        """C_MOV must be 0x7B."""
        assert FluxOpcode.C_MOV == 0x7B

    def test_c_add_encoding(self) -> None:
        """C_ADD R2, R0, R1 must encode as 0x78 0x02 0x00 0x01."""
        asm = FluxAssembler()
        asm.emit(FluxOpcode.C_ADD, 2, 0, 1)
        assert asm.to_bytes() == bytes([0x78, 0x02, 0x00, 0x01])

    def test_c_mov_encoding(self) -> None:
        """C_MOV R1, R0 must encode as 0x7B 0x01 0x00."""
        asm = FluxAssembler()
        asm.emit(FluxOpcode.C_MOV, 1, 0)
        assert asm.to_bytes() == bytes([0x7B, 0x01, 0x00])
