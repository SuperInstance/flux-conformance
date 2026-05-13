"""Abstract base class for FLUX runtime adapters.

Every runtime (Python, C, Rust, Go) must implement this interface
to participate in the conformance test suite.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Dict, List, Optional


class ExecutionStatus(Enum):
    """Result status of a single bytecode execution."""
    SUCCESS = "success"
    HALT = "halt"
    ERROR = "error"
    TIMEOUT = "timeout"
    UNSUPPORTED = "unsupported"


@dataclass
class RegisterState:
    """Snapshot of the VM register file after execution."""
    int_regs: Dict[int, int] = field(default_factory=dict)   # R0-R15
    float_regs: Dict[int, float] = field(default_factory=dict)  # F0-F15
    simd_regs: Dict[int, bytes] = field(default_factory=dict)   # V0-V15
    pc: int = 0
    sp: int = 0
    flags: Dict[str, bool] = field(default_factory=dict)


@dataclass
class ExecutionResult:
    """Complete result from executing a bytecode program on a runtime."""
    status: ExecutionStatus
    registers: RegisterState = field(default_factory=RegisterState)
    output: List[Any] = field(default_factory=list)
    error_message: Optional[str] = None
    cycles: int = 0
    memory_regions: Dict[int, bytes] = field(default_factory=dict)
    confidence_values: Dict[str, float] = field(default_factory=dict)


@dataclass
class BytecodeProgram:
    """A FLUX bytecode program with metadata for testing."""
    name: str
    bytecode: bytes
    description: str = ""
    expected_status: ExecutionStatus = ExecutionStatus.HALT
    expected_registers: Optional[RegisterState] = None
    expected_output: Optional[List[Any]] = None
    category: str = "general"
    opcodes_used: List[int] = field(default_factory=list)


class AbstractRuntimeAdapter(ABC):
    """Interface that all FLUX runtime adapters must implement.

    The conformance suite uses this interface to run the same bytecode
    programs against different runtime implementations and compare results.
    """

    @property
    @abstractmethod
    def runtime_name(self) -> str:
        """Human-readable name of this runtime (e.g., 'flux-runtime Python')."""

    @property
    @abstractmethod
    def runtime_version(self) -> str:
        """Version string of this runtime."""

    @property
    @abstractmethod
    def supported_opcodes(self) -> set[int]:
        """Set of opcode numbers this runtime supports."""

    @abstractmethod
    def execute(self, program: BytecodeProgram, timeout_ms: int = 5000) -> ExecutionResult:
        """Execute a bytecode program and return the result.

        Args:
            program: The bytecode program to execute.
            timeout_ms: Maximum execution time in milliseconds.

        Returns:
            ExecutionResult with register state, output, and status.
        """

    @abstractmethod
    def encode_instruction(self, opcode: int, operands: tuple) -> bytes:
        """Encode a single instruction into bytecode bytes.

        Args:
            opcode: The opcode number (0x00-0xFF).
            operands: Tuple of operand values.

        Returns:
            The encoded bytecode bytes for this instruction.
        """

    @abstractmethod
    def decode_instruction(self, bytecode: bytes, offset: int = 0) -> tuple:
        """Decode a single instruction from bytecode bytes.

        Args:
            bytecode: Raw bytecode bytes.
            offset: Starting offset in the bytecode.

        Returns:
            Tuple of (opcode, operands, byte_length).
        """

    def health_check(self) -> bool:
        """Verify the runtime is available and responsive.

        Returns:
            True if the runtime can execute bytecode, False otherwise.
        """
        try:
            # Try executing a simple NOP + HALT program
            nop_halt = BytecodeProgram(
                name="health_check",
                bytecode=bytes([0x00, 0x80]),  # NOP, HALT
                expected_status=ExecutionStatus.HALT,
            )
            result = self.execute(nop_halt, timeout_ms=1000)
            return result.status in (ExecutionStatus.HALT, ExecutionStatus.SUCCESS)
        except Exception:
            return False

    def get_opcode_coverage(self, tested_opcodes: set[int]) -> dict:
        """Calculate opcode coverage for this runtime.

        Args:
            tested_opcodes: Set of opcodes covered by the test suite.

        Returns:
            Dictionary with coverage statistics.
        """
        supported = self.supported_opcodes
        covered = tested_opcodes & supported
        missing = supported - tested_opcodes
        return {
            "runtime": self.runtime_name,
            "total_supported": len(supported),
            "covered": len(covered),
            "missing": len(missing),
            "coverage_pct": len(covered) / max(len(supported), 1) * 100,
            "missing_opcodes": sorted(missing),
        }
