# Architecture

This document provides a detailed technical overview of the FLUX Conformance Test Suite architecture, including module descriptions, class hierarchies, data flow, extension points, and performance characteristics.

## System Architecture

The FLUX Conformance Test Suite is organized as a layered system with clear separation of concerns. At the foundation lies the reference VM implementation; above it, the test case library defines expected behaviors; and at the top, runner infrastructure enables testing against any FLUX runtime.

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                         USER / CI INTERFACE                               │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐   │
│  │   pytest    │  │   runner     │  │  benchmark    │  │  JSON export  │   │
│  │   CLI       │  │   script     │  │   harness     │  │  / import    │   │
│  └──────┬──────┘  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘   │
│         │                │                  │                  │            │
├─────────┼────────────────┼──────────────────┼──────────────────┼────────────┤
│         ▼                ▼                  ▼                  ▼            │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │                    TEST INFRASTRUCTURE LAYER                    │      │
│  │  ┌─────────────────────┐  ┌──────────────────────────────────┐  │      │
│  │  │ ConformanceTestSuite│  │    ConformanceRunner              │  │      │
│  │  │ - load_builtin_cases │  │ - discover_runtimes()             │  │      │
│  │  │ - run_single()       │  │ - run_all()                       │  │      │
│  │  │ - run_all()          │  │ - build_summaries()               │  │      │
│  │  │ - summary()          │  │ - output_json/markdown/terminal   │  │      │
│  │  └──────────┬──────────┘  └──────────┬───────────────────────┘  │      │
│  └─────────────┼────────────────────────┼─────────────────────────┘      │
│                │                        │                                 │
├────────────────┼────────────────────────┼─────────────────────────────────┤
│                ▼                        ▼                                 │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │                    RUNTIME ADAPTER LAYER                         │      │
│  │  ┌──────────────────────┐  ┌────────────────────────────────┐   │      │
│  │  │ PythonReferenceRuntime│  │ SubprocessRuntime              │   │      │
│  │  │ - is_available(): T  │  │ - is_available(): check cmd    │   │      │
│  │  │ - run_test()         │  │ - run_test(): JSON over stdin  │   │      │
│  │  └──────────┬───────────┘  └─────────────┬──────────────────┘   │      │
│  └─────────────┼────────────────────────────┼───────────────────────┘      │
│                │                            │                               │
├────────────────┼────────────────────────────┼───────────────────────────────┤
│                ▼                            ▼                               │
│  ┌──────────────────────────────────────────────────────────────────┐      │
│  │                    CORE IMPLEMENTATION LAYER                     │      │
│  │  ┌─────────────────┐  ┌──────────────┐  ┌────────────────────┐  │      │
│  │  │    FluxVM       │  │  FluxFlags    │  │ ConformanceTestCase│  │      │
│  │  │ (reference VM)  │  │ (Z,S,C,O)    │  │ (dataclass)        │  │      │
│  │  │ 37 opcodes      │  │              │  │ name, bytecode_hex │  │      │
│  │  │ 64KB memory     │  │ update_arith │  │ expected_stack     │  │      │
│  │  │ 100k step limit │  │ update_logic │  │ expected_flags     │  │      │
│  │  └─────────────────┘  └──────────────┘  └────────────────────┘  │      │
│  └──────────────────────────────────────────────────────────────────┘      │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Module Descriptions

### `conformance_core.py` — Core Module

The foundation of the entire suite. This single file contains all opcode definitions, the reference VM, flag register, test case data structure, test suite runner, and the complete built-in test case library. It is designed to be importable without any external dependencies beyond Python's standard library (`struct`, `dataclasses`, `typing`).

**Responsibilities:**
- Define all opcode constants (37 base opcodes + flag bits)
- Implement `FluxFlags` — the 4-bit condition code register
- Implement `FluxVM` — the golden reference virtual machine
- Define `ConformanceTestCase` — the test vector data structure
- Implement `ConformanceTestSuite` — the test runner with comparison logic
- Provide 113 built-in test cases via `_build_all_test_cases()`
- Export bytecode helper functions (`push_imm32`, `jmp_addr`, `jz_addr`, etc.)

### `test_conformance.py` — Pytest Integration (v2)

Provides pytest integration for the 113 base conformance test vectors. Uses `@pytest.mark.parametrize` to generate one test function per vector, plus manual category-level test classes with additional edge case assertions beyond what the built-in vectors cover.

**Test Structure:**
- `test_conformance(case)` — Parametrized test for all 113 built-in vectors
- `TestSystemControl` — 4 manual tests for HALT, NOP, BREAK
- `TestIntegerArithmetic` — 12 manual tests including error cases (div-by-zero)
- `TestComparison` — 7 manual tests
- `TestLogic` — 7 manual tests
- `TestMemory` — 3 manual tests
- `TestControlFlow` — 7 manual tests (loops, calls, jumps)
- `TestStackManipulation` — 4 manual tests
- `TestFloatOperations` — 5 manual tests including error cases
- `TestConfidence` — 5 manual tests (clamping, chaining)
- `TestA2A` — 4 manual tests (FIFO order, empty channels)
- `TestFlags` — 5 manual tests (zero, sign, carry verification)
- `TestComplexPrograms` — 4 manual tests (fibonacci, factorial, abs)
- `TestSuiteIntegration` — 3 integration tests (loads all, passes all, summary)

### `test_conformance_v3.py` — ISA v3 Extension Tests

Tests for the ISA v3 escape prefix mechanism and the three extension classes (temporal, security, async). Implements `FluxVMv3`, a subclass of `FluxVM` with additional state for temporal tracking, security enforcement, and async operations.

**Test Structure:**
- `TestTemporalExtension` — 8 tests (fuel check, deadline, time, yield, persist, sleep)
- `TestSecurityExtension` — 7 tests (identity, capability, sandbox, fuel, mem tag)
- `TestAsyncExtension` — 6 tests (suspend/resume, fork, cancel, await, join)
- `TestExtensionDiscovery` — 2 tests (probe, unsupported extension)
- `TestBackwardCompatibility` — 5 tests (v2 programs on v3 VM)

### `conformance-vectors.json` — Exported Test Vectors

A JSON file containing all 113 v2 test vectors in a portable format. Generated by `run_conformance.py --export`. Designed for consumption by non-Python runtimes that read the JSON and execute the hex-encoded bytecode directly.

### `benchmark_flux.py` — Performance Benchmark Harness

Measures VM performance across 12 benchmark categories with configurable iteration counts, warmup phases, and multiple output formats (terminal, JSON, Markdown). Each benchmark generates a synthetic loop program that exercises a specific opcode category.

### `run_conformance.py` — Unified Cross-Runtime Runner

A CLI tool that runs all test vectors against one or more FLUX runtime implementations. Supports auto-discovery of installed runtimes via subprocess probing, category filtering, JSON/Markdown/terminal output, and test vector export.

## Class Hierarchy

```
FluxFlags
├── value: int                  # Raw 4-bit flags value
├── Z: bool (property)          # Zero flag
├── S: bool (property)          # Sign flag
├── C: bool (property)          # Carry flag
├── O: bool (property)          # Overflow flag
├── update_arith(result, a, b, is_sub)  # After arithmetic ops
└── update_logic(result)        # After logic/comparison ops

FluxVM
├── stack: List                 # Data stack (unbounded)
├── memory: bytearray(65536)    # 64KB linear memory
├── flags: FluxFlags            # Condition code register
├── pc: int                     # Program counter (byte address)
├── code: bytes                 # Current bytecode program
├── call_stack: List[int]       # Return address stack
├── confidence: float           # Agent confidence [0.0, 1.0]
├── halted: bool                # True after HALT instruction
├── signals: dict               # Channel -> FIFO queue mapping
├── running: bool               # Main loop control
├── max_steps: int              # Safety limit (default: 100,000)
├── steps: int                  # Step counter
├── reset()                     # Initialize all state
├── push(value)                 # Push to data stack
├── pop() -> value              # Pop from data stack
├── read_u8/read_u16/read_i32() # Instruction operand readers
├── run(code, initial_stack) -> (stack, flags)  # Execute program
└── _step()                     # Execute one instruction

FluxVMv3(FluxVM)                # ISA v3 extension
├── start_time_ms: int          # Simulated start time
├── current_time_ms: int        # Simulated current time
├── fuel_limit: int             # Execution fuel budget
├── fuel_remaining: int         # Current fuel remaining
├── deadlines: dict             # addr -> timestamp mappings
├── resource_contention: dict   # resource_id -> bool
├── capabilities: set           # Granted capability IDs
├── memory_tags: dict           # (addr, addr+size) -> tag
├── sandbox_stack: list         # Nested sandbox contexts
├── active_sandbox: tuple       # Current sandbox (start, size, perms)
├── identity_handle: int        # Agent identity
├── continuations: list         # Saved execution states
├── contexts: dict              # context_id -> FluxVMv3
├── _check_sandbox_read(addr)   # Sandbox read access check
├── _check_sandbox_write(addr)  # Sandbox write access check
├── _handle_extension()         # 0xFF dispatch
├── _handle_temporal()          # EXT 0x01 sub-opcodes
├── _handle_security()          # EXT 0x02 sub-opcodes
├── _handle_async()             # EXT 0x03 sub-opcodes
└── read_u32() -> int           # 32-bit unsigned operand reader

ConformanceTestCase (dataclass)
├── name: str                   # Unique test identifier
├── bytecode_hex: str           # Hex-encoded bytecode
├── initial_stack: list         # Pre-execution stack state
├── expected_stack: list        # Post-execution stack state
├── expected_flags: int         # Expected flags (-1 = skip)
├── description: str            # Human-readable description
└── allow_float_epsilon: bool   # Float comparison tolerance

ConformanceTestSuite
├── cases: List[ConformanceTestCase]
├── add(case)                   # Register a test case
├── load_builtin_cases()        # Load all 113 built-in vectors
├── run_single(case, vm) -> dict
├── run_all(vm) -> List[dict]
└── summary(results) -> str

FluxRuntime (abstract base)
├── name: str
├── description: str
├── is_available() -> bool
└── run_test(case) -> RuntimeResult

PythonReferenceRuntime(FluxRuntime)
└── Directly uses FluxVM in-process

SubprocessRuntime(FluxRuntime)
├── cmd: List[str]              # Command to execute
├── test_format: str            # "json" (default)
├── is_available() -> bool      # Probe via --version
└── run_test(case) -> RuntimeResult  # JSON over stdin/stdout
```

## Data Flow

The following diagram shows the complete data flow from test vector definition through execution to result reporting:

```
┌──────────────────────────────────────────────────────────────────────────┐
│                        DATA FLOW DIAGRAM                                │
├──────────────────────────────────────────────────────────────────────────┤
│                                                                          │
│  1. TEST VECTOR DEFINITION                                               │
│  ┌─────────────┐     ┌─────────────────────┐     ┌─────────────────┐   │
│  │ conformance │     │ conformance-vectors │     │ External vector │   │
│  │ _core.py    │────>│ .json               │────>│ contribution    │   │
│  │ (Python)    │     │ (portable JSON)     │     │ (community PR)  │   │
│  └──────┬──────┘     └─────────┬───────────┘     └────────┬────────┘   │
│         │                      │                          │             │
│         ▼                      ▼                          ▼             │
│  2. TEST LOADING                                                         │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  ConformanceTestSuite.load_builtin_cases() / add(case)           │   │
│  │  - Parse bytecode hex -> bytes                                    │   │
│  │  - Validate initial_stack, expected_stack types                    │   │
│  │  - Store in self.cases: List[ConformanceTestCase]                 │   │
│  └──────────────────────────────┬───────────────────────────────────┘   │
│                                 │                                        │
│  3. EXECUTION                   ▼                                        │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  For each case in suite.cases:                                    │   │
│  │                                                                    │   │
│  │  ┌─────────────┐    bytes.fromhex()    ┌──────────────────┐      │   │
│  │  │bytecode_hex │──────────────────────>│ raw bytecode     │      │   │
│  │  └─────────────┘                        └────────┬─────────┘      │   │
│  │                                                  │                  │   │
│  │                                                  ▼                  │   │
│  │  ┌─────────────────────────────────────────────────────────────┐  │   │
│  │  │                    RUNTIME EXECUTION                        │  │   │
│  │  │                                                             │  │   │
│  │  │  PythonReferenceRuntime:                                    │  │   │
│  │  │    FluxVM.run(code, initial_stack) -> (stack, flags)         │  │   │
│  │  │                                                             │  │   │
│  │  │  SubprocessRuntime:                                         │  │   │
│  │  │    stdin: {"bytecode_hex":..., "initial_stack":...}          │  │   │
│  │  │    stdout: {"passed":bool, "actual_stack":[...], ...}        │  │   │
│  │  └──────────────────────────────┬──────────────────────────────┘  │   │
│  │                                 │                                  │   │
│  4. COMPARISON                     ▼                                  │
│  ┌──────────────────────────────────────────────────────────────────┐   │
│  │  Compare actual vs expected:                                     │   │
│  │                                                                    │   │
│  │  - Stack length match?                                           │   │
│  │  - Each stack element match? (exact or float epsilon)             │   │
│  │  - Flags match? (unless expected_flags == FLAGS_ANY)             │   │
│  │                                                                    │   │
│  │  Result: RuntimeResult {passed, error, actual_stack, ...}        │   │
│  └──────────────────────────────┬───────────────────────────────────┘   │
│                                 │                                        │
│  5. REPORTING                    ▼                                        │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────┐  ┌────────────┐  │
│  │  Terminal   │  │    JSON      │  │  Markdown    │  │  pytest    │  │
│  │  (summary)  │  │  (--json)    │  │  (--markdown)│  │  (-v)      │  │
│  └─────────────┘  └──────────────┘  └──────────────┘  └────────────┘  │
│                                                                          │
└──────────────────────────────────────────────────────────────────────────┘
```

## Extension Points for New Runtimes

The suite provides two mechanisms for adding a new FLUX runtime to the test infrastructure:

### 1. In-Process Adapter (Python Runtimes)

For runtimes implemented in Python, create a subclass of `FluxRuntime`:

```python
from run_conformance import FluxRuntime, RuntimeResult
from conformance_core import ConformanceTestCase
import time

class MyFluxRuntime(FluxRuntime):
    name = "my-flux-runtime"
    description = "My custom FLUX VM implementation"

    def is_available(self) -> bool:
        return True  # Always available if in-process

    def run_test(self, case: ConformanceTestCase) -> RuntimeResult:
        start = time.monotonic()
        try:
            stack, flags = my_vm_execute(
                bytes.fromhex(case.bytecode_hex),
                case.initial_stack
            )
        except Exception as e:
            return RuntimeResult(
                runtime_name=self.name,
                test_name=case.name,
                passed=False,
                error=str(e),
                duration_ms=(time.monotonic() - start) * 1000
            )
        # Compare against expected values...
```

### 2. Subprocess Adapter (Non-Python Runtimes)

For runtimes in other languages, use `SubprocessRuntime` with a JSON protocol. The external runtime reads a JSON test case from stdin and writes a JSON result to stdout:

```json
// Input (stdin):
{
  "bytecode_hex": "550300000055040000001000",
  "initial_stack": [],
  "expected_stack": [7],
  "expected_flags": -1,
  "allow_float_epsilon": false
}

// Output (stdout):
{
  "passed": true,
  "actual_stack": [7],
  "actual_flags": -1,
  "error": ""
}
```

### 3. Runtime Registration in Runner

Register the runtime in the `ConformanceRunner.discover_runtimes()` method or directly:

```python
runner = ConformanceRunner()
runner.add_runtime(PythonReferenceRuntime())
runner.add_runtime(SubprocessRuntime(
    name="rust-flux",
    description="Rust FLUX VM (flux-core)",
    cmd=["cargo", "run", "--", "--conformance"]
))
results = runner.run_all()
```

## Error Handling and Reporting Pipeline

The error handling pipeline follows a structured approach from low-level VM errors to high-level reporting:

```
VM Execution Error (RuntimeError)
│
├─ Stack underflow          → "Stack underflow at PC=N"
├─ Division by zero         → "Division by zero"
├─ Modulo by zero           → "Modulo by zero"
├─ Float division by zero   → "Float division by zero"
├─ Call stack underflow     → "Call stack underflow"
├─ Unknown opcode           → "Unknown opcode 0xNN at PC=N"
├─ Fuel exhausted (v3)      → "FUEL_EXHAUSTED (0xE2)"
├─ Capability denied (v3)   → "CAPABILITY_DENIED (0xE0)"
├─ Sandbox violation (v3)   → "SANDBOX_VIOLATION (0xE1)"
└─ Extension not supported  → "EXTENSION_NOT_SUPPORTED (0xE4)"
         │
         ▼
RuntimeResult {passed: False, error: "..."}
         │
         ▼
ConformanceRunner.build_summaries()
├─ Per-runtime pass/fail counts
├─ Failed test name list
├─ Per-category breakdown
└─ Cross-runtime divergence detection
         │
         ▼
Output Formatting
├─ Terminal: Human-readable table with PASS/FAIL per test
├─ JSON: Machine-readable for CI systems
├─ Markdown: Documentation-ready tables
└─ Exit code: 0 (all pass) or 1 (any failure)
```

### Error Severity Classification

| Level | Description | Example | Test Result |
|-------|-------------|---------|-------------|
| Fatal | VM cannot execute the program | Unknown opcode | FAIL |
| Runtime | Program crashes during execution | Division by zero | FAIL |
| Semantic | Program completes but wrong result | Wrong stack value | FAIL |
| Flag | Program completes, stack correct, flags differ | Wrong carry flag | FAIL (if flags checked) |
| Tolerance | Float values within epsilon | 3.5 vs 3.500000001 | PASS (if epsilon allowed) |

## Performance Characteristics

### Throughput

The Python reference VM is an interpreted implementation with no JIT compilation. Typical throughput on modern hardware:

| Category | Approximate Throughput | Notes |
|----------|----------------------|-------|
| NOP loop | ~500K ops/sec | Raw decode overhead |
| Integer arithmetic | ~200K ops/sec | ADD/SUB/MUL |
| Memory access | ~150K ops/sec | LOAD/STORE with struct.unpack |
| Float arithmetic | ~100K ops/sec | Float casting overhead |
| Control flow | ~180K ops/sec | CALL/RET with stack management |
| Stack manipulation | ~250K ops/sec | List operations |
| Startup | ~50K programs/sec | Full VM initialization per program |

### Memory Usage

The reference VM has the following memory characteristics:

- **Code storage:** `bytes` object, 1:1 with bytecode size (typically < 1KB per test)
- **Data stack:** Python `list` of `int`/`float` objects, grows dynamically
- **Call stack:** Python `list` of `int` objects, grows with nesting depth
- **Memory:** Fixed 64KB `bytearray` per VM instance
- **Signals:** `dict` mapping int to `list`, grows with channel usage
- **Per-instance overhead:** ~65KB (64KB memory + overhead)

### Safety Limits

- **max_steps:** 100,000 instructions per program execution (configurable)
- **Stack depth:** Unbounded in reference implementation
- **Memory size:** Fixed at 64KB
- **Subprocess timeout:** 30 seconds per test case
- **Call stack depth:** Unbounded (limited by Python recursion)

These limits are intentionally conservative. Production runtimes may implement stricter limits for security and resource management.
