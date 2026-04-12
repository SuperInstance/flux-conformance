# FLUX Conformance Test Suite

A comprehensive conformance test suite for the FLUX bytecode virtual machine.
Verifies that all FLUX runtimes (Python, C, Go, Zig, Rust, JS, Java, CUDA)
produce identical results for the same bytecode programs.

## Overview

The FLUX ISA defines **247 opcodes** across **7 encoding formats** (A–G).
This suite provides:

- A **reference VM** (`FluxVM`) — the golden standard for correct behaviour
- **116 conformance test cases** covering all opcode categories
- A **test runner** (`ConformanceTestSuite`) that any runtime can plug into
- **Pytest integration** with per-case and per-category tests

## Opcode Categories Covered

| # | Category       | Opcodes                                          | Test Count |
|---|---------------|--------------------------------------------------|-----------|
| 1 | System Control | `HALT`, `NOP`, `BREAK`                           | 4         |
| 2 | Integer Arith  | `ADD`, `SUB`, `MUL`, `DIV`, `MOD`, `NEG`, `INC`, `DEC` | 20 |
| 3 | Comparison     | `EQ`, `NE`, `LT`, `LE`, `GT`, `GE`               | 9         |
| 4 | Logic / Bit    | `AND`, `OR`, `XOR`, `NOT`, `SHL`, `SHR`          | 12        |
| 5 | Memory         | `LOAD`, `STORE`, `PEEK`, `POKE`                  | 7         |
| 6 | Control Flow   | `JMP`, `JZ`, `JNZ`, `CALL`, `RET`, `PUSH`, `POP` | 12        |
| 7 | Stack Manip    | `DUP`, `SWAP`, `OVER`, `ROT`                     | 6         |
| 8 | Float Ops      | `FADD`, `FSUB`, `FMUL`, `FDIV`                   | 8         |
| 9 | Confidence     | `CONF_GET`, `CONF_SET`, `CONF_MUL`               | 7         |
|10 | Agent-to-Agent | `SIGNAL`, `BROADCAST`, `LISTEN`                  | 7         |
|11 | Complex / Mixed| Fibonacci, factorial, absolute value, loops      | 24        |

## Quick Start

```bash
# Install dependencies
pip install pytest

# Run all tests
PYTHONPATH=. python -m pytest test_conformance.py -v

# Run with coverage
PYTHONPATH=. python -m pytest test_conformance.py -v --cov=conformance_core
```

## Architecture

```
conformance_core.py    # Opcode defs, reference VM, test case library
  ├─ FluxVM            # Reference VM implementation
  ├─ FluxFlags         # Flags register (Z, S, C, O)
  ├─ ConformanceTestCase  # Single test case definition
  └─ ConformanceTestSuite # Test runner & reporter

test_conformance.py    # Pytest tests (parametrized + categorized)
pyproject.toml         # Project configuration
```

## Encoding Format

| Format | Name     | Encoding                      | Example         |
|--------|----------|-------------------------------|-----------------|
| A      | Nullary  | 1 byte opcode                 | `HALT` → `0x00` |
| B      | Unary    | 1 byte opcode                 | `NEG` → `0x15`  |
| C      | Binary   | 1 byte opcode (stack operands)| `ADD` → `0x10`  |
| D      | Imm8     | opcode + 1 byte               | `SIGNAL ch`     |
| E      | Addr16   | opcode + 2 bytes LE           | `JMP addr`      |
| F      | MemAddr  | opcode + 2 bytes LE           | `LOAD addr`     |
| G      | Imm32    | opcode + 4 bytes LE           | `PUSH value`    |

## Adding a Runtime

To conformance-test a new FLUX runtime:

1. Implement a `run(bytecode_hex, initial_stack) -> (stack, flags)` function
2. Iterate over all `ConformanceTestCase` instances
3. Compare stack contents and flags — any mismatch is a non-conformance bug

```python
from conformance_core import ConformanceTestSuite

suite = ConformanceTestSuite()
suite.load_builtin_cases()

for case in suite.cases:
    stack, flags = my_runtime_run(case.bytecode_hex, case.initial_stack)
    assert stack == case.expected_stack
    assert flags == case.expected_flags
```

## Test Results

All 116 conformance tests pass against the reference VM:

```
FLUX Conformance Test Results: 116/116 passed
```

## License

MIT
