"""Conformance tests for FLUX A2A (Agent-to-Agent) protocol opcodes.

The A2A opcodes implement the agent coordination protocol described in the
FLUX ISA v1.0 specification.  These tests verify that:

1. Each A2A opcode is recognised and does not crash the VM.
2. The opcode encoding is correct.
3. The basic register/stack side-effects (if any) are consistent.

Note: In the micro VM, most A2A opcodes are **stubs** that simply advance
the program counter.  Full behavioural tests require a runtime with A2A
support.  These conformance tests therefore focus on **opcode recognition**
and **encoding correctness**.
"""

from __future__ import annotations

import pytest

from runtime_adapters.abstract_adapter import RuntimeStatus
from runtime_adapters.python_adapter import FluxAssembler, FluxOpcode


class TestA2ABasicOps:
    """Basic A2A opcodes: TELL, ASK, DELEGATE, BROADCAST."""

    def test_tell_recognised(self, adapter) -> None:  # type: ignore[valid-type]
        """TELL opcode should be recognised and not crash."""
        op = FluxOpcode
        asm = FluxAssembler()
        asm.emit(op.TELL, 0, 1)
        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert result.status in (RuntimeStatus.HALT, RuntimeStatus.OK)

    def test_ask_recognised(self, adapter) -> None:  # type: ignore[valid-type]
        """ASK opcode should be recognised and not crash."""
        op = FluxOpcode
        asm = FluxAssembler()
        asm.emit(op.ASK, 0, 1)
        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert result.status in (RuntimeStatus.HALT, RuntimeStatus.OK)

    def test_delegate_recognised(self, adapter) -> None:  # type: ignore[valid-type]
        """DELEGATE opcode should be recognised and not crash."""
        op = FluxOpcode
        asm = FluxAssembler()
        asm.emit(op.DELEGATE, 0, 1)
        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert result.status in (RuntimeStatus.HALT, RuntimeStatus.OK)

    def test_broadcast_recognised(self, adapter) -> None:  # type: ignore[valid-type]
        """BROADCAST opcode should be recognised and not crash."""
        op = FluxOpcode
        asm = FluxAssembler()
        asm.emit(op.BROADCAST, 0, 1)
        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert result.status in (RuntimeStatus.HALT, RuntimeStatus.OK)


class TestA2ATrust:
    """A2A trust and capability opcodes: TRUST, CAP."""

    def test_trust_recognised(self, adapter) -> None:  # type: ignore[valid-type]
        """TRUST opcode should be recognised."""
        op = FluxOpcode
        asm = FluxAssembler()
        asm.emit(op.TRUST, 0, 1)
        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert result.status in (RuntimeStatus.HALT, RuntimeStatus.OK)

    def test_cap_recognised(self, adapter) -> None:  # type: ignore[valid-type]
        """CAP opcode should be recognised."""
        op = FluxOpcode
        asm = FluxAssembler()
        asm.emit(op.CAP, 0, 1)
        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert result.status in (RuntimeStatus.HALT, RuntimeStatus.OK)


class TestA2ABarrier:
    """A2A synchronisation: BARRIER."""

    def test_barrier_recognised(self, adapter) -> None:  # type: ignore[valid-type]
        """BARRIER opcode should be recognised."""
        op = FluxOpcode
        asm = FluxAssembler()
        asm.emit(op.BARRIER, 0)
        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert result.status in (RuntimeStatus.HALT, RuntimeStatus.OK)


class TestA2AMailbox:
    """A2A mailbox opcodes: MAILBOX_SEND, MAILBOX_RECV."""

    def test_mailbox_send_recognised(self, adapter) -> None:  # type: ignore[valid-type]
        """MAILBOX_SEND should be recognised."""
        op = FluxOpcode
        asm = FluxAssembler()
        asm.emit(op.MAILBOX_SEND, 0, 1)
        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert result.status in (RuntimeStatus.HALT, RuntimeStatus.OK)

    def test_mailbox_recv_recognised(self, adapter) -> None:  # type: ignore[valid-type]
        """MAILBOX_RECV should be recognised."""
        op = FluxOpcode
        asm = FluxAssembler()
        asm.emit(op.MAILBOX_RECV, 0, 1)
        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert result.status in (RuntimeStatus.HALT, RuntimeStatus.OK)


class TestA2AShareRevoke:
    """A2A sharing opcodes: SHARE, REVOKE."""

    def test_share_recognised(self, adapter) -> None:  # type: ignore[valid-type]
        """SHARE should be recognised."""
        op = FluxOpcode
        asm = FluxAssembler()
        asm.emit(op.SHARE, 0, 1)
        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert result.status in (RuntimeStatus.HALT, RuntimeStatus.OK)

    def test_revoke_recognised(self, adapter) -> None:  # type: ignore[valid-type]
        """REVOKE should be recognised."""
        op = FluxOpcode
        asm = FluxAssembler()
        asm.emit(op.REVOKE, 0, 1)
        asm.emit(op.HALT)

        result = adapter.execute(asm.to_bytes())
        assert result.status in (RuntimeStatus.HALT, RuntimeStatus.OK)


class TestA2AEncoding:
    """Verify A2A opcode byte encoding."""

    def test_tell_encoding(self) -> None:
        """TELL R0, R1 = 0x60 0x00 0x01."""
        asm = FluxAssembler()
        asm.emit(FluxOpcode.TELL, 0, 1)
        assert asm.to_bytes() == bytes([0x60, 0x00, 0x01])

    def test_ask_encoding(self) -> None:
        """ASK R2, R3 = 0x61 0x02 0x03."""
        asm = FluxAssembler()
        asm.emit(FluxOpcode.ASK, 2, 3)
        assert asm.to_bytes() == bytes([0x61, 0x02, 0x03])

    def test_delegate_encoding(self) -> None:
        """DELEGATE R4, R5 = 0x62 0x04 0x05."""
        asm = FluxAssembler()
        asm.emit(FluxOpcode.DELEGATE, 4, 5)
        assert asm.to_bytes() == bytes([0x62, 0x04, 0x05])

    def test_broadcast_encoding(self) -> None:
        """BROADCAST R6, R7 = 0x63 0x06 0x07."""
        asm = FluxAssembler()
        asm.emit(FluxOpcode.BROADCAST, 6, 7)
        assert asm.to_bytes() == bytes([0x63, 0x06, 0x07])

    def test_trust_encoding(self) -> None:
        """TRUST R0, R1 = 0x64 0x00 0x01."""
        asm = FluxAssembler()
        asm.emit(FluxOpcode.TRUST, 0, 1)
        assert asm.to_bytes() == bytes([0x64, 0x00, 0x01])

    def test_barrier_encoding(self) -> None:
        """BARRIER 0 = 0x66 0x00."""
        asm = FluxAssembler()
        asm.emit(FluxOpcode.BARRIER, 0)
        assert asm.to_bytes() == bytes([0x66, 0x00])
