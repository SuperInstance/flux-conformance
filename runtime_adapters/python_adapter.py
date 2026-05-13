"""Python FLUX runtime adapter for conformance testing.

Connects to the flux-runtime Python package (pip install flux-runtime)
to execute bytecode programs and verify conformance with the ISA spec.
"""

import json
import subprocess
import sys
from typing import Optional

from .abstract_adapter import (
    AbstractRuntimeAdapter,
    BytecodeProgram,
    ExecutionResult,
    ExecutionStatus,
    RegisterState,
)


# All opcodes supported by flux-runtime Python (ISA v1.0 + v2.0 extensions)
PYTHON_SUPPORTED_OPCODES = set(range(0x100))  # Full 256-slot namespace


class PythonRuntimeAdapter(AbstractRuntimeAdapter):
    """Adapter for the Python flux-runtime implementation.

    This adapter communicates with the Python runtime by spawning a
    subprocess that loads flux-runtime, executes bytecode, and returns
    results as JSON.
    """

    def __init__(self, python_path: Optional[str] = None):
        """Initialize the Python runtime adapter.

        Args:
            python_path: Path to the Python interpreter. Defaults to sys.executable.
        """
        self._python = python_path or sys.executable
        self._version: Optional[str] = None

    @property
    def runtime_name(self) -> str:
        return "flux-runtime Python"

    @property
    def runtime_version(self) -> str:
        if self._version is None:
            try:
                result = subprocess.run(
                    [self._python, "-m", "flux_runtime", "--version"],
                    capture_output=True, text=True, timeout=5,
                )
                self._version = result.stdout.strip() or "unknown"
            except Exception:
                self._version = "unavailable"
        return self._version

    @property
    def supported_opcodes(self) -> set[int]:
        return PYTHON_SUPPORTED_OPCODES

    def execute(self, program: BytecodeProgram, timeout_ms: int = 5000) -> ExecutionResult:
        """Execute bytecode via the Python runtime.

        Writes the bytecode to a temp file, runs the Python VM, and
        parses the JSON result.
        """
        runner_script = self._build_runner_script(program)

        try:
            result = subprocess.run(
                [self._python, "-c", runner_script],
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
        except Exception as e:
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                error_message=str(e),
            )

    def encode_instruction(self, opcode: int, operands: tuple) -> bytes:
        """Encode using the Python runtime's encoder."""
        script = f"""
import json
from flux_runtime.encoder import encode
result = encode({opcode}, {list(operands)})
print(json.dumps({{"bytes": list(result)}}))
"""
        try:
            result = subprocess.run(
                [self._python, "-c", script],
                capture_output=True, text=True, timeout=5,
            )
            data = json.loads(result.stdout)
            return bytes(data["bytes"])
        except Exception:
            # Fallback: manual encoding based on ISA spec
            return self._manual_encode(opcode, operands)

    def decode_instruction(self, bytecode: bytes, offset: int = 0) -> tuple:
        """Decode using the Python runtime's decoder."""
        script = f"""
import json
from flux_runtime.decoder import decode
bc = bytes({list(bytecode[offset:])})
result = decode(bc)
print(json.dumps({{"opcode": result[0], "operands": result[1], "length": result[2]}}))
"""
        try:
            result = subprocess.run(
                [self._python, "-c", script],
                capture_output=True, text=True, timeout=5,
            )
            data = json.loads(result.stdout)
            return (data["opcode"], tuple(data["operands"]), data["length"])
        except Exception:
            return (bytecode[offset], (), 1)

    def _build_runner_script(self, program: BytecodeProgram) -> str:
        """Build a Python script that executes the bytecode and returns results."""
        bytecode_list = list(program.bytecode)
        return f"""
import json
import sys

try:
    from flux_runtime.vm import FluxVM

    vm = FluxVM()
    bytecode = bytes({bytecode_list})
    vm.load(bytecode)
    result = vm.run()

    output = {{
        "status": "halt",
        "registers": {{
            "int": {{i: vm.get_int_reg(i) for i in range(16)}},
            "float": {{i: vm.get_float_reg(i) for i in range(16)}},
        }},
        "pc": vm.pc,
        "sp": vm.sp,
        "cycles": vm.cycles,
        "output": vm.output if hasattr(vm, 'output') else [],
    }}
    print(json.dumps(output))

except ImportError:
    # Runtime not installed — return unavailable status
    print(json.dumps({{"status": "unavailable"}}))
except Exception as e:
    print(json.dumps({{"status": "error", "error": str(e)}}))
"""

    def _parse_result(self, stdout: str) -> ExecutionResult:
        """Parse the JSON output from the Python runner."""
        try:
            data = json.loads(stdout)
        except json.JSONDecodeError:
            return ExecutionResult(
                status=ExecutionStatus.ERROR,
                error_message=f"Invalid JSON output: {stdout[:200]}",
            )

        status_map = {
            "halt": ExecutionStatus.HALT,
            "success": ExecutionStatus.SUCCESS,
            "error": ExecutionStatus.ERROR,
            "timeout": ExecutionStatus.TIMEOUT,
            "unavailable": ExecutionStatus.UNSUPPORTED,
        }

        status = status_map.get(data.get("status", "error"), ExecutionStatus.ERROR)

        regs = data.get("registers", {})
        registers = RegisterState(
            int_regs={k: v for k, v in regs.get("int", {}).items()},
            float_regs={k: v for k, v in regs.get("float", {}).items()},
            pc=data.get("pc", 0),
            sp=data.get("sp", 0),
        )

        return ExecutionResult(
            status=status,
            registers=registers,
            output=data.get("output", []),
            error_message=data.get("error"),
            cycles=data.get("cycles", 0),
        )

    @staticmethod
    def _manual_encode(opcode: int, operands: tuple) -> bytes:
        """Fallback manual encoding per ISA spec formats."""
        # Format A: 1 byte (opcode only)
        if len(operands) == 0:
            return bytes([opcode])

        # Format B: 2 bytes (opcode + reg)
        if len(operands) == 1 and 0 <= operands[0] <= 63:
            return bytes([opcode, operands[0] & 0x3F])

        # Format C: 3 bytes (opcode + reg + imm8)
        if len(operands) == 2 and isinstance(operands[1], int) and -128 <= operands[1] <= 127:
            return bytes([opcode, operands[0] & 0x3F, operands[1] & 0xFF])

        # Format E: 4 bytes (opcode + rd + rs1 + rs2)
        if len(operands) == 3:
            return bytes([
                opcode,
                operands[0] & 0x3F,
                operands[1] & 0x3F,
                operands[2] & 0x3F,
            ])

        # Default: opcode + raw operands
        return bytes([opcode] + [o & 0xFF for o in operands])
