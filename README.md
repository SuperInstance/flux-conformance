# FLUX Conformance Test Suite

![Tests Passing](https://img.shields.io/badge/tests-113%2F113-brightgreen)
![Coverage](https://img.shields.io/badge/coverage-100%25-brightgreen)
![Version](https://img.shields.io/badge/version-2.0.0-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![ISA v3](https://img.shields.io/badge/ISA-v3%20ready-orange)
![Runtimes](https://img.shields.io/badge/runtimes-8-purple)

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

### Prerequisites

- Python 3.10 or later
- `pytest` 7.0+ (for running the test suite)

### Installation

```bash
# Clone the repository
git clone <repository-url> flux-conformance
cd flux-conformance

# Install with pip (editable mode)
pip install -e ".[dev]"
```

### Running Tests

```bash
# Run all v2 conformance tests (113 test vectors)
PYTHONPATH=. python -m pytest test_conformance.py -v

# Run ISA v3 extension tests
PYTHONPATH=. python -m pytest test_conformance_v3.py -v

# Run all tests with coverage report
PYTHONPATH=. python -m pytest test_conformance.py test_conformance_v3.py -v --cov=conformance_core

# Run using the unified runner script
python run_conformance.py                       # Python reference VM only
python run_conformance.py --all                 # All available runtimes
python run_conformance.py --json                # JSON output
python run_conformance.py --markdown            # Markdown report
python run_conformance.py --category arith      # Arithmetic tests only
python run_conformance.py --list                # List all test vector names
python run_conformance.py --export vectors.json # Export test vectors as JSON
```

### Running Benchmarks

```bash
# Run the full performance benchmark suite
python benchmark_flux.py

# Specific category benchmark
python benchmark_flux.py --category arith

# JSON output for CI integration
python benchmark_flux.py --json --iterations 50000

# Markdown table output
python benchmark_flux.py --markdown --output benchmark-results.md
```

## Architecture Overview

The conformance test suite follows a layered architecture where the reference VM serves as the golden standard, test cases define expected behavior, and a pluggable runner infrastructure enables testing against any FLUX runtime implementation.

```
┌─────────────────────────────────────────────────────────────────────┐
│                     FLUX CONFORMANCE SUITE                         │
├─────────────────────────────────────────────────────────────────────┤
│                                                                     │
│  ┌──────────────┐    ┌─────────────────────┐    ┌───────────────┐  │
│  │  Test Vector  │───>│   Conformance Test   │───>│   Test        │  │
│  │  JSON Files   │    │   Runner (Python)    │    │   Reports     │  │
│  │  (113 v2 +    │    │   run_conformance.py │    │   (JSON/MD/   │  │
│  │   62 v3)      │    │                      │    │    terminal)  │  │
│  └──────────────┘    └─────────┬───────────┘    └───────────────┘  │
│                                │                                     │
│                     ┌──────────▼──────────┐                         │
│                     │  FluxVM (Reference)  │                         │
│                     │  conformance_core.py │                         │
│                     │  - Stack machine     │                         │
│                     │  - Flags register    │                         │
│                     │  - 64KB memory       │                         │
│                     │  - 37 base opcodes   │                         │
│                     │  - ISA v3 extensions │                         │
│                     └──────────┬──────────┘                         │
│                                │                                     │
│  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐           │
│  │ Python   │  │  Rust    │  │    C     │  │   Go     │  ...      │
│  │ Runtime  │  │ Runtime  │  │ Runtime  │  │ Runtime  │           │
│  └──────────┘  └──────────┘  └──────────┘  └──────────┘           │
│                                                                     │
├─────────────────────────────────────────────────────────────────────┤
│  Extension Points: SubprocessRuntime, FluxRuntime base class        │
│  Output Formats:   Terminal, JSON, Markdown                         │
│  CI Integration:   Non-zero exit on failure, JSON reports           │
└─────────────────────────────────────────────────────────────────────┘
```

### Module Layout

```
conformance_core.py    # Opcode defs, reference VM, test case library
  ├─ FluxVM            # Reference VM implementation (v2 base)
  ├─ FluxFlags         # Flags register (Z, S, C, O)
  ├─ ConformanceTestCase  # Single test case definition
  └─ ConformanceTestSuite # Test runner & reporter

test_conformance.py    # Pytest tests (parametrized + categorized) — 113 vectors
test_conformance_v3.py # ISA v3 extension tests — 62 vectors
conformance-vectors.json # Exported test vectors (v2 only, JSON format)
benchmark_flux.py      # Performance benchmarking harness (PERF-001)
run_conformance.py     # Unified cross-runtime conformance runner (CONF-001)
pyproject.toml         # Project configuration
```

## Design Philosophy

Conformance testing is the foundation of trust in a multi-runtime ecosystem. When the same bytecode program executes on eight different runtimes written in different languages — Python, C, Rust, Go, Zig, JavaScript, Java, and CUDA — every single runtime must produce byte-for-byte identical results. Any deviation, no matter how small, represents a potential consensus failure in the broader FLUX agent network.

This suite embodies three core design principles that guide every architectural decision:

**Determinism above all.** Every test vector specifies not just the expected stack output, but also the exact flags register state after execution. There is no room for "approximately correct" or "implementation-defined behavior." When a test says `5 + (-5) = 0` with flags `Z|C`, every runtime on every platform must produce precisely that result. This deterministic guarantee is what allows FLUX agents to coordinate across heterogeneous infrastructure without a central authority.

**Reference VM as golden standard.** The `FluxVM` class in `conformance_core.py` is not merely a test utility — it is the canonical definition of correct FLUX behavior. If a test passes against the reference VM and fails against your runtime, your runtime has a bug. The reference VM implements the complete ISA specification including edge cases like signed integer division truncation semantics, flag register update rules for carry and overflow, and the confidence register clamping behavior. This eliminates ambiguity in the specification by providing a working, auditable implementation.

**Portable by construction.** Test vectors are expressed as pure data — hex-encoded bytecode, initial stack state, expected stack output, and expected flags. This data-driven approach means any runtime in any language can consume the test vectors without Python dependencies. The JSON export format (`conformance-vectors.json`) is designed for cross-language tooling, and the `SubprocessRuntime` adapter pattern in `run_conformance.py` provides a universal interface for testing runtimes that communicate via standard input/output.

## Test Vector Format

Test vectors are the fundamental unit of the conformance suite. Each vector defines a complete, self-contained test: a bytecode program, its inputs, and its expected outputs. Vectors are stored both as Python `ConformanceTestCase` dataclass instances (in `conformance_core.py`) and as portable JSON objects (in `conformance-vectors.json`).

### JSON Schema

Every test vector in the JSON export conforms to the following schema:

```json
{
  "name": "string",                // Unique identifier (naming convention: category_operation)
  "bytecode_hex": "string",        // Hex-encoded bytecode (e.g., "550300000055040000001000")
  "initial_stack": [number, ...],  // Stack values before execution (bottom to top)
  "expected_stack": [number, ...], // Expected stack values after execution
  "expected_flags": number,        // Expected flags register (-1 = skip check, or 0x00-0x0F)
  "allow_float_epsilon": boolean,  // Allow floating-point tolerance (1e-5)
  "description": "string"          // Human-readable description of the test
}
```

### Flags Register Encoding

The flags register is a 4-bit value where each bit represents a CPU-style condition flag:

| Bit | Name | Value | Meaning |
|-----|------|-------|---------|
| 0   | Z    | 0x01  | Zero flag — set when the last arithmetic/logic result is zero |
| 1   | S    | 0x02  | Sign flag — set when the last result is negative |
| 2   | C    | 0x04  | Carry flag — set on unsigned overflow in addition |
| 3   | O    | 0x08  | Overflow flag — set on signed overflow |

The sentinel value `-1` (FLAGS_ANY) means "do not check flags for this test case."

### Example Vectors

**Simple addition with flag checking:**
```json
{
  "name": "arith_add_positive",
  "bytecode_hex": "550300000055040000001000",
  "initial_stack": [],
  "expected_stack": [7],
  "expected_flags": -1,
  "allow_float_epsilon": false,
  "description": "3 + 4 = 7"
}
```
Bytecode breakdown: `55 03000000` (PUSH 3) `55 04000000` (PUSH 4) `10` (ADD) `00` (HALT)

**Addition producing zero with flags:**
```json
{
  "name": "arith_add_zero",
  "bytecode_hex": "550500000055fbffffff1000",
  "initial_stack": [],
  "expected_stack": [0],
  "expected_flags": 5,
  "allow_float_epsilon": false,
  "description": "5 + (-5) = 0, Z and C set"
}
```
Flags `0x05` = Z(0x01) | C(0x04), meaning the result is zero and an unsigned carry occurred.

**Using initial stack for compact tests:**
```json
{
  "name": "arith_add_stack",
  "bytecode_hex": "1000",
  "initial_stack": [5, 3],
  "expected_stack": [8],
  "expected_flags": -1,
  "allow_float_epsilon": false,
  "description": "ADD with initial stack [5, 3]"
}
```
Bytecode breakdown: `10` (ADD — pops 3 and 5, pushes 8) `00` (HALT).

**Floating-point with epsilon tolerance:**
```json
{
  "name": "float_div",
  "bytecode_hex": "550700000055020000007300",
  "initial_stack": [],
  "expected_stack": [3.5],
  "expected_flags": -1,
  "allow_float_epsilon": true,
  "description": "FDIV: 7.0 / 2.0 = 3.5"
}
```

## Opcode Coverage Matrix

The conformance suite covers all 37 implemented opcodes of the FLUX ISA v2 specification (out of 247 total opcode slots allocated across the encoding space). The following matrix shows which test categories exercise each opcode:

| Opcode | Hex | Category | System | Arith | Cmp | Logic | Mem | Ctrl | Stack | Float | Conf | A2A |
|--------|-----|----------|--------|-------|-----|-------|-----|------|-------|-------|------|-----|
| HALT   | 0x00| Control  |   ✓    |       |     |       |     |      |       |       |      |     |
| NOP    | 0x01| Control  |   ✓    |       |     |       |     |      |       |       |      |     |
| BREAK  | 0x02| Control  |   ✓    |       |     |       |     |      |       |       |      |     |
| ADD    | 0x10| Arith    |        |   ✓   |     |       |     |  ✓   |       |       |      |     |
| SUB    | 0x11| Arith    |        |   ✓   |     |       |     |  ✓   |       |       |      |     |
| MUL    | 0x12| Arith    |        |   ✓   |     |       |     |  ✓   |       |       |      |     |
| DIV    | 0x13| Arith    |        |   ✓   |     |       |     |  ✓   |       |       |      |     |
| MOD    | 0x14| Arith    |        |   ✓   |     |       |     |  ✓   |       |       |      |     |
| NEG    | 0x15| Arith    |        |   ✓   |     |       |     |      |       |       |      |     |
| INC    | 0x16| Arith    |        |   ✓   |     |       |     |  ✓   |       |       |      |     |
| DEC    | 0x17| Arith    |        |   ✓   |     |       |     |  ✓   |       |       |      |     |
| EQ     | 0x20| Compare  |        |       |  ✓  |       |     |      |       |       |      |     |
| NE     | 0x21| Compare  |        |       |  ✓  |       |     |      |       |       |      |     |
| LT     | 0x22| Compare  |        |       |  ✓  |       |     |      |       |       |      |     |
| LE     | 0x23| Compare  |        |       |  ✓  |       |     |      |       |       |      |     |
| GT     | 0x24| Compare  |        |       |  ✓  |       |     |      |       |       |      |     |
| GE     | 0x25| Compare  |        |       |  ✓  |       |     |      |       |       |      |     |
| AND    | 0x30| Logic    |        |       |     |   ✓   |     |      |       |       |      |     |
| OR     | 0x31| Logic    |        |       |     |   ✓   |     |      |       |       |      |     |
| XOR    | 0x32| Logic    |        |       |     |   ✓   |     |      |       |       |      |     |
| NOT    | 0x33| Logic    |        |       |     |   ✓   |     |      |       |       |      |     |
| SHL    | 0x34| Logic    |        |       |     |   ✓   |     |      |       |       |      |     |
| SHR    | 0x35| Logic    |        |       |     |   ✓   |     |      |       |       |      |     |
| LOAD   | 0x40| Memory   |        |       |     |       |  ✓  |  ✓   |       |       |      |     |
| STORE  | 0x41| Memory   |        |       |     |       |  ✓  |  ✓   |       |       |      |     |
| PEEK   | 0x43| Memory   |        |       |     |       |  ✓  |      |       |       |      |     |
| POKE   | 0x44| Memory   |        |       |     |       |  ✓  |      |       |       |      |     |
| JMP    | 0x50| Control  |        |       |     |       |     |  ✓   |       |       |      |     |
| JZ     | 0x51| Control  |        |       |     |       |     |  ✓   |       |       |      |     |
| JNZ    | 0x52| Control  |        |       |     |       |     |  ✓   |       |       |      |     |
| CALL   | 0x53| Control  |        |       |     |       |     |  ✓   |       |       |      |     |
| RET    | 0x54| Control  |        |       |     |       |     |  ✓   |       |       |      |     |
| PUSH   | 0x55| Control  |        |       |     |       |     |  ✓   |       |       |      |     |
| POP    | 0x56| Control  |        |       |     |       |     |  ✓   |       |       |      |     |
| DUP    | 0x60| Stack    |        |       |     |       |     |      |   ✓   |       |      |     |
| SWAP   | 0x61| Stack    |        |       |     |       |     |      |   ✓   |       |      |     |
| OVER   | 0x62| Stack    |        |       |     |       |     |      |   ✓   |       |      |     |
| ROT    | 0x63| Stack    |        |       |     |       |     |      |   ✓   |       |      |     |
| FADD   | 0x70| Float    |        |       |     |       |     |      |       |   ✓   |      |     |
| FSUB   | 0x71| Float    |        |       |     |       |     |      |       |   ✓   |      |     |
| FMUL   | 0x72| Float    |        |       |     |       |     |      |       |   ✓   |      |     |
| FDIV   | 0x73| Float    |        |       |     |       |     |      |       |   ✓   |      |     |
| CONF_GET|0x80| Conf     |        |       |     |       |     |      |       |       |  ✓   |     |
| CONF_SET|0x81| Conf     |        |       |     |       |     |      |       |       |  ✓   |     |
| CONF_MUL|0x82| Conf     |        |       |     |       |     |      |       |       |  ✓   |     |
| SIGNAL | 0x90| A2A      |        |       |     |       |     |      |       |       |      |  ✓  |
| BROADCAST|0x91| A2A     |        |       |     |       |     |      |       |       |      |  ✓  |
| LISTEN | 0x92| A2A      |        |       |     |       |     |      |       |       |      |  ✓  |

## Cross-Runtime Results

The conformance suite has been designed to test any FLUX runtime implementation. The following table summarizes the current and predicted pass rates across target runtimes:

| Runtime | Language | Status | Pass Rate | Notes |
|---------|----------|--------|-----------|-------|
| Python Reference | Python 3.10+ | ✅ Verified | 113/113 (100%) | Golden reference implementation |
| TypeScript/WASM | TypeScript | 🔧 In Progress | ~66% (predicted) | Integer arith, logic, control flow passing |
| Rust | Rust | 🔧 In Progress | ~40% (predicted) | Core arithmetic and stack operations |
| C | C11 | 📋 Planned | ~27% (predicted) | Basic arithmetic subset |
| Go | Go 1.21+ | 📋 Planned | ~20% (predicted) | Integer operations only |
| Zig | Zig 0.11+ | 📋 Planned | TBD | Awaiting runtime implementation |
| Java | Java 17+ | 📋 Planned | TBD | Awaiting runtime implementation |
| CUDA | CUDA 12+ | 📋 Planned | TBD | GPU-accelerated parallel execution |

### Portability Classification

Opcodes are classified into four portability tiers based on cross-runtime analysis:

- **P0 — Universal (7 opcodes):** `HALT`, `NOP`, `PUSH`, `POP`, `ADD`, `SUB`, `MUL` — trivially implementable in any language with basic arithmetic.
- **P1 — High (12 opcodes):** `BREAK`, `NEG`, `INC`, `DEC`, `EQ`, `NE`, `LT`, `GT`, `DUP`, `SWAP`, `JMP`, `JZ` — straightforward semantics, minor flag behavior variations.
- **P2 — Medium (10 opcodes):** `DIV`, `MOD`, `LE`, `GE`, `AND`, `OR`, `XOR`, `NOT`, `JNZ`, `CALL` — signed division truncation and carry flag semantics require careful implementation.
- **P3 — Complex (8 opcodes):** `SHL`, `SHR`, `LOAD`, `STORE`, `PEEK`, `POKE`, `RET`, `ROT` — memory addressing and shift semantics vary across platforms.

See [CROSS-RUNTIME-RESULTS.md](CROSS-RUNTIME-RESULTS.md) for detailed per-runtime failure analysis and the complete CONF-002 audit results.

## Reference VM Implementation

The `FluxVM` class in `conformance_core.py` is the canonical FLUX virtual machine. It serves as the golden reference for all conformance testing — if a program produces different results on your runtime versus `FluxVM`, your runtime has a bug.

### Stack Machine Architecture

`FluxVM` is a stack-based virtual machine with the following components:

- **Data Stack:** An unbounded Python list used as a LIFO stack. Values are pushed and popped by instructions. There is no fixed stack size limit in the reference implementation, though runtimes may impose limits for safety.
- **Return Stack (call_stack):** A separate stack used by `CALL` and `RET` for subroutine linkage. Each `CALL` pushes the current PC onto the call stack; each `RET` pops it back.
- **Flags Register (`FluxFlags`):** A 4-bit register with individual Z, S, C, O flags accessible as boolean properties. Updated by arithmetic instructions (`update_arith`) and logic instructions (`update_logic`).
- **Memory:** A 64KB `bytearray` addressed by 16-bit little-endian addresses. `LOAD`/`STORE` use embedded addresses; `PEEK`/`POKE` use stack-derived addresses. All memory operations use 32-bit little-endian signed integers.
- **Program Counter (PC):** A byte-level instruction pointer that advances through the bytecode stream. Control flow instructions modify the PC directly.
- **Confidence Register:** A floating-point value in [0.0, 1.0] representing the agent's confidence level. Modified by `CONF_GET`, `CONF_SET`, and `CONF_MUL` with clamping semantics.
- **Signal Channels:** A dictionary mapping channel numbers (0-255) to FIFO queues of integer values, used by `SIGNAL`, `BROADCAST`, and `LISTEN` for agent-to-agent communication.

### Execution Model

The VM operates in a simple fetch-decode-execute loop:

1. Fetch the next opcode byte at `PC`
2. Decode and dispatch to the appropriate handler
3. Execute the instruction (modifying stack, memory, flags, or PC)
4. Advance `PC` past any instruction operands
5. Check `max_steps` safety limit

Execution terminates when `HALT` is reached, `BREAK` is executed, the PC advances past the end of the bytecode, or the step limit is exceeded.

### Flag Update Rules

Arithmetic operations (`ADD`, `SUB`, `MUL`, `DIV`, `MOD`, `NEG`, `INC`, `DEC`) update all four flags:

- **Z (Zero):** Set if the result is exactly zero.
- **S (Sign):** Set if the result is negative.
- **C (Carry):** For addition, set if the unsigned sum exceeds 32 bits. For subtraction, set if the unsigned minuend is less than the subtrahend (both non-negative).
- **O (Overflow):** For addition, set if both operands have the same sign but the result has a different sign. For subtraction, currently always cleared in the reference implementation (a known spec ambiguity).

Logic operations (`AND`, `OR`, `XOR`, `NOT`, `SHL`, `SHR`) and comparison operations (`EQ`, `NE`, `LT`, `LE`, `GT`, `GE`) update only Z and S, clearing C and O.

## ISA v3 Extension Testing

The ISA v3 specification extends the FLUX instruction set with three new primitive classes accessible through an escape prefix mechanism. The test file `test_conformance_v3.py` provides 62 additional test vectors covering these extensions.

### Escape Prefix Encoding

v3 extensions use the `0xFF` escape prefix followed by an extension ID (1 byte), a sub-opcode (1 byte), and variable-length payload:

```
┌──────────┬────────────────┬───────────┬──────────────┐
│ 0xFF     │ extension_id   │ sub_opcode│   payload    │
│ (escape) │ (1 byte)       │ (1 byte)  │ (variable)   │
└──────────┴────────────────┴───────────┴──────────────┘
```

### Extension Classes

**EXT 0x01 — Temporal Primitives (6 sub-opcodes):**
`FUEL_CHECK` (remaining fuel), `DEADLINE_BEFORE` (conditional jump based on wall-clock time), `YIELD_IF_CONTENTION` (cooperative multitasking), `PERSIST_CRITICAL_STATE` (snapshot memory region), `TIME_NOW` (monotonic clock), `SLEEP_UNTIL` (advance simulated clock).

**EXT 0x02 — Security Primitives (6 sub-opcodes):**
`CAP_INVOKE` (capability-based authorization), `MEM_TAG` (memory region tagging), `SANDBOX_ENTER`/`SANDBOX_EXIT` (memory access restriction), `FUEL_SET` (execution budget), `IDENTITY_GET` (agent identity handle).

**EXT 0x03 — Async Primitives (6 sub-opcodes):**
`SUSPEND` (save execution state to continuation), `RESUME` (restore from continuation), `FORK` (create child context), `JOIN` (wait for context completion), `CANCEL` (abort context), `AWAIT_CHANNEL` (channel read with timeout).

### v3 Reference Implementation

The `FluxVMv3` class extends the base `FluxVM` with additional state for temporal tracking (simulated clock, fuel budget), security (capability sets, sandbox stack, memory tags), and async (continuation list, context map). All v3 extensions maintain backward compatibility — any valid v2 program runs identically on `FluxVMv3`.

## Canonical Opcode Translation

The cross-runtime translation shim (`canonical_opcode_shim.py`) provides a compatibility layer that maps between different runtime-specific opcode encodings and the canonical FLUX ISA encoding. This is essential when runtimes use internal opcode numbering that differs from the published specification.

The translation shim:

1. Reads bytecode from the test vector (canonical hex encoding)
2. Applies a per-runtime opcode remapping table
3. Adjusts operand sizes and endianness if needed
4. Emits the runtime's native bytecode format

This ensures that even runtimes with different internal architectures can consume the same test vectors without modification.

## Benchmarking

The `benchmark_flux.py` module (PERF-001) provides a comprehensive performance benchmarking harness for measuring FLUX VM throughput across multiple dimensions.

### Methodology

Each benchmark runs a synthetic program that exercises a specific opcode category in a tight loop, with warmup iterations, multiple timed runs, and statistical aggregation. The harness measures:

- **Total operations:** Number of VM instructions executed
- **Wall-clock time:** Elapsed time in milliseconds (median of 5 runs)
- **Throughput:** Operations per second
- **Per-instruction latency:** Nanoseconds per operation

### Benchmark Categories

| Category | Benchmarks | What it measures |
|----------|-----------|-----------------|
| decode | NOP loop, PUSH+HALT | Raw instruction fetch/decode speed |
| arith | ADD, MUL, DIV+MOD loops | Integer arithmetic throughput |
| float | FADD+FMUL loop | Floating-point arithmetic throughput |
| logic | AND/OR/XOR/SHL loop | Bitwise operation throughput |
| comparison | EQ/LT/GT loop | Comparison operation throughput |
| memory | STORE/LOAD, POKE/PEEK loops | Memory access latency |
| stack | DUP/SWAP/OVER/ROT loop | Stack manipulation throughput |
| control | CALL/RET, nested CALL, factorial | Control flow overhead |
| confidence | CONF_SET/GET/MUL loop | Confidence register throughput |
| a2a | SIGNAL/LISTEN loop | Agent-to-agent messaging throughput |
| complex | Fibonacci | Mixed-operation programs |
| startup | 1000x PUSH+HALT | VM initialization cost |

### Usage

```bash
# Full benchmark suite (default 10,000 iterations)
python benchmark_flux.py

# Specific category
python benchmark_flux.py --category memory

# Custom iteration count
python benchmark_flux.py --iterations 50000

# Output formats
python benchmark_flux.py --json          # Machine-readable JSON
python benchmark_flux.py --markdown      # Markdown tables
python benchmark_flux.py --json --output results.json
```

## Contributing

We welcome contributions to the FLUX conformance test suite! Please see [CONTRIBUTING.md](CONTRIBUTING.md) for detailed guidelines on:

- Writing new test vectors
- Testing a new FLUX runtime
- Code style and PR process
- Test vector review criteria

## Known Issues

### Confidence Opcode Spec Ambiguity (CONF-002)

The overflow flag behavior for `CONF_MUL` and `CONF_SET` operations has a specification ambiguity. The ISA specification does not clearly define whether confidence operations should update the overflow flag (O) in the same way as arithmetic operations. The reference VM currently does **not** update flags for confidence operations, but at least one alternative interpretation exists that would set the overflow flag when confidence is clamped from a value > 1.0 or < 0.0.

**Impact:** 5 test cases in the CONF-002 cross-runtime audit may produce different flag values depending on interpretation. The stack values are always correct regardless of flag interpretation.

**Resolution path:** A formal ISA clarification is pending. Once resolved, the affected test vectors will be updated with explicit `expected_flags` values.

### Integer Division Truncation

The reference VM uses Python's `int(a / b)` for division, which performs true division followed by truncation toward zero. This differs from Python's native `//` floor division operator for negative numbers: `int(-7 / 2) = -3` (truncation) vs `-7 // 2 = -4` (floor). Runtimes using floor division semantics will fail `arith_div_neg`. The test vector explicitly documents this as "truncation toward zero" behavior.

### Unlimited Stack in Reference VM

The reference VM uses an unbounded Python list for the data stack. Production runtimes may impose stack size limits. No test vector currently tests stack overflow behavior, as this is considered a runtime-specific safety constraint rather than an ISA correctness concern.

## License

MIT
