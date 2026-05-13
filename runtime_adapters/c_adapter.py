"""C FLUX runtime adapter for conformance testing.

Connects to the flux-runtime-c binary to execute bytecode programs
and verify conformance with the ISA spec.
"""

import json
import os
import subprocess
import tempfile
from typing import Optional

from .abstract_adapter import (
    AbstractRuntimeAdapter,
    BytecodeProgram,
    ExecutionResult,
    ExecutionStatus,
    RegisterState,
)

# 85 opcodes supported by flux-runtime-c (C11 implementation)
C_SUPPORTED_OPCODES = set(
    list(range(0x00, 0x08))   # Control
    + list(range(0x08, 0x10))  # Int Arith
    + list(range(0x10, 0x18))  # Bitwise
    + list(range(0x18, 0x20))  # Compare
    + list(range(0x20, 0x28))  # Stack
    + list(range(0x28, 0x30))  # Function
    + list(range(0x30, 0x38))  # Memory
    + list(range(0x38, 0x40))  # Type
    + list(range(0x40, 0x50))  # Float/SIMD
    + list(range(0x60, 0x7C))  # A2A
    + list(range(0x80, 0x85))  # System
)


class CRuntimeAdapter(AbstractRuntimeAdapter):
    """Adapter for the C flux-runtime-c implementation.

    Communicates with the C VM binary by writing bytecode to a temp file
    and parsing the execution output.
    """

    def __init__(self, binary_path: Optional[str] = None):
        """Initialize the C runtime adapter.

        Args:
            binary_path: Path to the flux-runtime binary.
                         Defaults to 'flux-runtime' (assumes on PATH).
        """
        self._binary = binary_path or "flux-runtime"
        self._version: Optional[str] = None

    @property
    def runtime_name(self) -> str:
        return "flux-runtime-c (C11)"

    @property
    def runtime_version(self) -> str:
        if self._version is None:
            try:
                result = subprocess.run(
                    [self._binary, "--version"],
                    capture_output=True, text=True, timeout=5,
                )
                self._version = result.stdout.strip() or "unknown"
            except Exception:
                self._version = "unavailable"
        return self._version

    @property
    def supported_opcodes(self) -> set[int]:
        return C_SUPPORTED_OPCODES

    def execute(self, program: BytecodeProgram, timeout_ms: int = 5000) -> ExecutionResult:
        """Execute bytecode via the C runtime binary.

        Writes the bytecode to a temporary file, runs the C VM on it,
        and parses the output.
        """
        with tempfile.NamedTemporaryFile(suffix=".bin", delete=False) as f:
            f.write(program.bytecode)
            bytecode_path = f.name

        try:
            result = subprocess.run(
                [self._binary, bytecode_path, "--json-output"],
                capture_output=True, text=True,
                timeout=timeout_ms / 1000.0,
            )

            if result.returncode != 0:
                return ExecutionResult(
                    status=ExecutionStatus.ERROR,
                    error_message=result.stderr[:500],
                )

            return self._parse_result(result.stdout)

        except subprocess.TimeoutExpired:
            return ExecutionResult(status=ExecutionStatus.TIMEOUT)
        except FileNotFoundError:
            return ExecutionResult(
                status=ExecutionStatus.UNSUPPORTED,
                error_message=f"C runtime binary not found: {self._binary}",
            )
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                error_message=str(e),
            )
        finally:
            os.unlink(bytecode_path)

    def encode_instruction(self, opcode: int, operands: tuple) -> bytes:
        """Manual encoding based on the ISA spec for C runtime."""
        # Format A: 1 byte (opcode only)
        if len(operands) == 0:
            return bytes([opcode])

        # Format B: 2 bytes (opcode + reg)
        if len(operands) == 1 and isinstance(operands[0], int) and operands[0] <= 63:
            return bytes([opcode, operands[0] & 0x3F])

        # Format C: 3 bytes (opcode + reg + imm8)
        if len(operands) == 2:
            return bytes([opcode, operands[0] & 0x3F, operands[1] & 0xFF])

        # Format E: 4 bytes (opcode + rd + rs1 + rs2)
        if len(operands) == 3:
            return bytes([
                opcode,
                operands[0] & 0x3F,
                operands[1] & 0x3F,
                operands[2] & 0x3F,
            ])

        return bytes([opcode] + [o & 0xFF for o in operands])

    def decode_instruction(self, bytecode: bytes, offset: int = 0) -> tuple:
        """Manual decoding based on the ISA spec for C runtime."""
        if offset >= len(bytecode):
            return (0, (), 0)

        opcode = bytecode[offset]

        # Determine format from opcode range
        if opcode in range(0x00, 0x04):  # Format A (1 byte)
            return (opcode, (), 1)
        elif opcode in range(0x04, 0x10):  # Format B (2 bytes)
            if offset + 1 < len(bytecode):
                return (opcode, (bytecode[offset + 1],), 2)
            return (opcode, (), 1)
        elif opcode in range(0x20, 0x30):  # Format E (4 bytes)
            if offset + 3 < len(bytecode):
                return (opcode, (
                    bytecode[offset + 1],
                    bytecode[offset + 2],
                    bytecode[offset + 3],
                ), 4)
            return (opcode, (), 1)

        # Default: 1 byte
        return (opcode, (), 1)

    def _parse_result(self, stdout: str) -> ExecutionResult:
        """Parse C runtime output into an ExecutionResult."""
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            # C runtime might output plain text
            if "HALT" in stdout:
                return ExecutionResult(status=ExecutionStatus.HALT)
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                error_message=f"Unexpected output: {stdout[:200]}",
            )

        status_map = {
            "halt": ExecutionStatus.HALT,
            "success": ExecutionStatus.SUCCESS,
            "error": ExecutionStatus.ERROR,
        }

        regs = data.get("registers", {})
        registers = RegisterState(
            int_regs={i: regs.get("int", {}).get(str(i), 0) for i in range(16)},
            float_regs={i: regs.get("float", {}).get(str(i), 0.0) for i in range(16)},
            pc=data.get("pc", 0),
            sp=data.get("sp", 0),
        )

        return ExecutionResult(
            status=status_map.get(data.get("status", "error"), ExecutionStatus.ERROR),
            registers=registers,
            output=data.get("output", []),
            error_message=data.get("error"),
            cycles=data.get("cycles", 0),
        )
