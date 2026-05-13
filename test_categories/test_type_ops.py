"""Conformance tests for FLUX type-operation opcodes.

Tests cover: CAST, BOX, UNBOX, CHECK_TYPE, CHECK_BOUNDS.
"""

from __future__ import annotations

import pytest

from runtime_adapters.abstract_adapter import RegisterState, RuntimeStatus
from runtime_adapters.python_adapter import FluxAssembler, FluxOpcode


class TestCast:
    """CAST: type conversion between register banks."""

    def test_cast_int_to_float(self, adapter) -> None:  # type: ignore[valid-type]
        """CAST should convert integer register to float."""
        op = FluxOpcode
        asm = FluxAssembler()

        asm.emit(op.MOVI, 0, 0, 42)
        asm.emit(op.CAST, 0, 0)    # F0 = float(R0) = 42.0
        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert result.status in (RuntimeStatus.HALT, RuntimeStatus.OK)
        assert abs(result.registers.get_float(0) - 42.0) < 1e-6

    def test_cast_preserves_source(self, adapter) -> None:  # type: ignore[valid-type]
        """CAST should not modify the source register."""
        op = FluxOpcode
        asm = FluxAssembler()

        asm.emit(op.MOVI, 0, 0, 100)
        asm.emit(op.CAST, 0, 0)    # F0 = float(R0)
        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert result.status in (RuntimeStatus.HALT, RuntimeStatus.OK)
        # R0 should still be 100
        assert result.registers.get_int(0) == 100


class TestBoxUnbox:
    """BOX and UNBOX: value boxing for dynamic typing."""

    def test_box_unbox_roundtrip(self, adapter) -> None:  # type: ignore[valid-type]
        """BOX then UNBOX should preserve the value."""
        op = FluxOpcode
        asm = FluxAssembler()

        asm.emit(op.MOVI, 0, 0, 42)
        asm.emit(op.BOX, 1, 0)      # box R0 → R1
        asm.emit(op.UNBOX, 2, 1)    # unbox R1 → R2
        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert result.status in (RuntimeStatus.HALT, RuntimeStatus.OK)
        assert result.registers.get_int(2) == 42

    def test_box_preserves_source(self, adapter) -> None:  # type: ignore[valid-type]
        """BOX should not modify the source register."""
        op = FluxOpcode
        asm = FluxAssembler()

        asm.emit(op.MOVI, 0, 0, 77)
        asm.emit(op.BOX, 1, 0)
        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert result.status in (RuntimeStatus.HALT, RuntimeStatus.OK)
        assert result.registers.get_int(0) == 77


class TestCheckType:
    """CHECK_TYPE: runtime type verification."""

    def test_check_type_int(self, adapter) -> None:  # type: ignore[valid-type]
        """CHECK_TYPE on an integer should succeed (return 1)."""
        op = FluxOpcode
        asm = FluxAssembler()

        asm.emit(op.MOVI, 0, 0, 42)
        asm.emit(op.CHECK_TYPE, 1, 0)
        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert result.status in (RuntimeStatus.HALT, RuntimeStatus.OK)
        # In the micro VM, CHECK_TYPE always returns 1
        assert result.registers.get_int(1) == 1


class TestCheckBounds:
    """CHECK_BOUNDS: bounds verification."""

    def test_check_bounds_in_range(self, adapter) -> None:  # type: ignore[valid-type]
        """CHECK_BOUNDS on an in-range value should succeed."""
        op = FluxOpcode
        asm = FluxAssembler()

        asm.emit(op.MOVI, 0, 0, 5)
        asm.emit(op.CHECK_BOUNDS, 1, 0)
        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert result.status in (RuntimeStatus.HALT, RuntimeStatus.OK)
        # In the micro VM, CHECK_BOUNDS always returns 1
        assert result.registers.get_int(1) == 1
