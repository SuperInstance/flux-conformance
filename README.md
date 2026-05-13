# T-002: FLUX Cross-Runtime Conformance Test Suite

[![I2I:DELIVERY](https://img.shields.io/badge/I2I-DELIVERY-blue)](https://github.com/SuperInstance/fleet-contributing)
[![License: MIT](https://img.shields.io/badge/License-MIT-blue.svg)](https://opensource.org/licenses/MIT)

> `[I2I:DELIVERY] flux-conformance:initial — cross-runtime conformance test suite`

A comprehensive conformance test suite for the FLUX ISA that verifies all runtime implementations (Python, C, Rust, Go) behave consistently according to the ISA specification.

## What This Tests

The suite verifies that every FLUX runtime implementation:

1. **Encodes** instructions correctly per the ISA format spec (Formats A–G)
2. **Decodes** bytecode back to the correct opcode and operands
3. **Executes** bytecode programs with correct register state, memory state, and output
4. **Handles errors** consistently (division by zero, stack underflow, etc.)
5. **Supports A2A** protocol opcodes
6. **Propagates confidence** through C_* variants

## Architecture

```
T-002-flux-conformance/
├── conformance_suite.py         # Main test runner + pytest integration
├── bytecode_fixtures.py         # Hand-crafted bytecode programs with expected results
├── runtime_adapters/
│   ├── abstract_adapter.py      # Interface all runtimes must implement
│   ├── python_adapter.py        # flux-runtime Python adapter
│   └── c_adapter.py             # flux-runtime-c C11 adapter
├── test_categories/
│   ├── test_encoding.py         # Instruction encoding/decoding conformance
│   ├── test_arithmetic.py       # Integer and float arithmetic opcodes
│   ├── test_control_flow.py     # JMP, JZ, JNZ, CALL, RET, loops
│   ├── test_memory.py           # Memory and stack operations
│   └── test_type_and_a2a.py     # Type ops, A2A protocol, confidence variants
└── README.md                    # This file
```

## Test Fixtures

| Fixture | Category | Description | Expected |
|---------|----------|-------------|----------|
| `nop_halt` | control_flow | Simplest valid program | HALT |
| `euclidean_gcd` | arithmetic | GCD(48, 18) = 6 | R0=6 |
| `fibonacci_10` | arithmetic | fib(10) = 55 | R1=55 |
| `simple_loop_sum` | control_flow | Sum 1+2+3+4+5 = 15 | R0=15 |
| `function_call_return` | control_flow | double(5) = 10 | R0=10 |
| `stack_manipulation` | stack | PUSH/POP/SWAP | R0=7, R2=42 |
| `memory_store_load` | memory | Store 99, load back | R2=99 |
| `bitwise_ops` | arithmetic | AND/OR/XOR/SHL | R2=0x0F... |
| `comparison_ops` | arithmetic | IEQ/ILT/IGT | R2=0, R3=1, R4=0 |
| `type_ops` | type_ops | CAST/BOX/UNBOX | F0=42.0 |
| `div_by_zero` | error_handling | 42/0 | ERROR |

## Quick Start

```bash
# Install dependencies
pip install pytest flux-runtime

# Run the full suite
pytest conformance_suite.py -v

# Run specific test categories
pytest test_categories/test_arithmetic.py -v
pytest test_categories/test_control_flow.py -v

# Run against specific runtimes only
pytest conformance_suite.py -v --timeout=10

# Generate conformance report
python conformance_suite.py
```

## Adding a New Runtime

1. Create a new adapter in `runtime_adapters/` that implements `AbstractRuntimeAdapter`
2. Override: `runtime_name`, `runtime_version`, `supported_opcodes`, `execute()`, `encode_instruction()`, `decode_instruction()`
3. Register it in `conformance_suite.py`'s `discover_runtimes()` function
4. Run the suite to see conformance results

## Adding a New Fixture

1. Add a function in `bytecode_fixtures.py` that returns a `BytecodeProgram`
2. Add it to the `ALL_FIXTURES` list
3. Specify `expected_status`, `expected_registers`, and `opcodes_used`
4. The suite will automatically test it against all runtimes

## Fleet Context

- **Task ID**: T-002
- **Priority**: P0 (Critical)
- **Assigned**: Super Z 📋
- **Repo**: Part of the [SuperInstance](https://github.com/SuperInstance) fleet
- **Protocol**: I2I (Iron-to-Iron) commit format

## License

MIT — Part of the FLUX Fleet.
