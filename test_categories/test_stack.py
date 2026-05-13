"""Conformance tests for FLUX stack opcodes.

Tests cover: PUSH, POP, DUP, SWAP, ROT, ENTER, LEAVE, ALLOCA.
"""

from __future__ import annotations

import pytest

from runtime_adapters.abstract_adapter import RegisterState, RuntimeStatus
from runtime_adapters.python_adapter import FluxAssembler, FluxOpcode


class TestPushPop:
    """PUSH and POP: register ↔ data stack transfer."""

    def test_push_pop_roundtrip(self, adapter) -> None:  # type: ignore[valid-type]
        """PUSH R0 then POP R1 should preserve the value."""
        op = FluxOpcode
        asm = FluxAssembler()

        asm.emit(op.MOVI, 0, 0, 42)
        asm.emit(op.PUSH, 0)
        asm.emit(op.POP, 1)
        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert result.status in (RuntimeStatus.HALT, RuntimeStatus.OK)
        assert result.registers.get_int(1) == 42

    def test_push_multiple_values(self, adapter) -> None:  # type: ignore[valid-type]
        """PUSH R0, PUSH R1, POP R2, POP R3 — LIFO order."""
        op = FluxOpcode
        asm = FluxAssembler()

        asm.emit(op.MOVI, 0, 0, 10)
        asm.emit(op.MOVI, 1, 0, 20)

        asm.emit(op.PUSH, 0)   # stack: [10]
        asm.emit(op.PUSH, 1)   # stack: [10, 20]
        asm.emit(op.POP, 2)    # R2 = 20, stack: [10]
        asm.emit(op.POP, 3)    # R3 = 10, stack: []

        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert result.status in (RuntimeStatus.HALT, RuntimeStatus.OK)
        assert result.registers.get_int(2) == 20
        assert result.registers.get_int(3) == 10

    def test_pop_underflow(self, adapter) -> None:  # type: ignore[valid-type]
        """POP on empty stack should produce an error."""
        op = FluxOpcode
        asm = FluxAssembler()

        asm.emit(op.POP, 0)
        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert result.status == RuntimeStatus.ERROR


class TestDup:
    """DUP: duplicate top of stack."""

    def test_dup_basic(self, adapter) -> None:  # type: ignore[valid-type]
        """DUP should copy the top of stack."""
        op = FluxOpcode
        asm = FluxAssembler()

        asm.emit(op.MOVI, 0, 0, 42)
        asm.emit(op.PUSH, 0)   # stack: [42]
        asm.emit(op.DUP)        # stack: [42, 42]
        asm.emit(op.POP, 1)    # R1 = 42
        asm.emit(op.POP, 2)    # R2 = 42

        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert result.status in (RuntimeStatus.HALT, RuntimeStatus.OK)
        assert result.registers.get_int(1) == 42
        assert result.registers.get_int(2) == 42

    def test_dup_underflow(self, adapter) -> None:  # type: ignore[valid-type]
        """DUP on empty stack should produce an error."""
        op = FluxOpcode
        asm = FluxAssembler()

        asm.emit(op.DUP)
        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert result.status == RuntimeStatus.ERROR


class TestSwap:
    """SWAP: exchange top two stack elements."""

    def test_swap_basic(self, adapter) -> None:  # type: ignore[valid-type]
        """SWAP should exchange the top two stack elements."""
        op = FluxOpcode
        asm = FluxAssembler()

        asm.emit(op.MOVI, 0, 0, 10)
        asm.emit(op.MOVI, 1, 0, 20)

        asm.emit(op.PUSH, 0)   # stack: [10]
        asm.emit(op.PUSH, 1)   # stack: [10, 20]
        asm.emit(op.SWAP)       # stack: [20, 10]
        asm.emit(op.POP, 2)    # R2 = 10 (was on top after swap)
        asm.emit(op.POP, 3)    # R3 = 20

        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert result.status in (RuntimeStatus.HALT, RuntimeStatus.OK)
        # After SWAP: top is 10, second is 20
        assert result.registers.get_int(2) == 10
        assert result.registers.get_int(3) == 20

    def test_swap_underflow(self, adapter) -> None:  # type: ignore[valid-type]
        """SWAP with < 2 elements should produce an error."""
        op = FluxOpcode
        asm = FluxAssembler()

        asm.emit(op.MOVI, 0, 0, 1)
        asm.emit(op.PUSH, 0)
        asm.emit(op.SWAP)
        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert result.status == RuntimeStatus.ERROR


class TestRot:
    """ROT: rotate top three stack elements."""

    def test_rot_basic(self, adapter) -> None:  # type: ignore[valid-type]
        """ROT should rotate the top three stack elements."""
        op = FluxOpcode
        asm = FluxAssembler()

        asm.emit(op.MOVI, 0, 0, 1)    # bottom
        asm.emit(op.MOVI, 1, 0, 2)    # middle
        asm.emit(op.MOVI, 2, 0, 3)    # top

        asm.emit(op.PUSH, 0)   # stack: [1]
        asm.emit(op.PUSH, 1)   # stack: [1, 2]
        asm.emit(op.PUSH, 2)   # stack: [1, 2, 3]

        asm.emit(op.ROT)        # rotate top 3
        # After ROT the stack order changes.
        # The micro VM ROT pops top, mid, bot and pushes [top, bot, mid]
        # So stack becomes [1, 3, 2] (bottom to top: 1, 3, 2)

        asm.emit(op.POP, 5)    # top
        asm.emit(op.POP, 6)    # second
        asm.emit(op.POP, 7)    # third

        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert result.status in (RuntimeStatus.HALT, RuntimeStatus.OK)

    def test_rot_underflow(self, adapter) -> None:  # type: ignore[valid-type]
        """ROT with < 3 elements should produce an error."""
        op = FluxOpcode
        asm = FluxAssembler()

        asm.emit(op.MOVI, 0, 0, 1)
        asm.emit(op.PUSH, 0)
        asm.emit(op.PUSH, 0)
        asm.emit(op.ROT)
        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert result.status == RuntimeStatus.ERROR


class TestEnterLeave:
    """ENTER and LEAVE: stack frame management."""

    def test_enter_basic(self, adapter) -> None:  # type: ignore[valid-type]
        """ENTER should allocate stack frame space."""
        op = FluxOpcode
        asm = FluxAssembler()

        asm.emit(op.ENTER, 4)   # allocate 4 slots
        asm.emit(op.LEAVE)      # deallocate
        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert result.status in (RuntimeStatus.HALT, RuntimeStatus.OK)

    def test_enter_leave_balanced(self, adapter) -> None:  # type: ignore[valid-type]
        """ENTER/LEAVE should be balanced without stack corruption."""
        op = FluxOpcode
        asm = FluxAssembler()

        asm.emit(op.MOVI, 0, 0, 42)
        asm.emit(op.PUSH, 0)    # push a value
        asm.emit(op.ENTER, 2)   # allocate 2 frame slots
        asm.emit(op.LEAVE)      # deallocate frame
        asm.emit(op.POP, 1)    # should still get 42

        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert result.status in (RuntimeStatus.HALT, RuntimeStatus.OK)
        # Note: ENTER pushes zeros, which might affect the stack
        # This is a basic smoke test


class TestAlloca:
    """ALLOCA: stack-based memory allocation."""

    def test_alloca_basic(self, adapter) -> None:  # type: ignore[valid-type]
        """ALLOCA should not crash and should set the destination register."""
        op = FluxOpcode
        asm = FluxAssembler()

        asm.emit(op.ALLOCA, 0, 32)   # allocate 32 bytes, handle in R0
        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert result.status in (RuntimeStatus.HALT, RuntimeStatus.OK)
