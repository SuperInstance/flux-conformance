# Contributing Guide

Thank you for your interest in contributing to the FLUX Conformance Test Suite! This guide covers everything you need to know to write new test vectors, test a new FLUX runtime, and submit contributions.

## Table of Contents

- [Code of Conduct](#code-of-conduct)
- [Getting Started](#getting-started)
- [Writing New Test Vectors](#writing-new-test-vectors)
- [Testing a New FLUX Runtime](#testing-a-new-flux-runtime)
- [Code Style Guide](#code-style-guide)
- [Pull Request Process](#pull-request-process)
- [Test Vector Review Criteria](#test-vector-review-criteria)

## Code of Conduct

- Be respectful and constructive in all interactions
- Focus on technical accuracy and correctness
- Test vectors must pass against the reference VM before submission
- All contributions must be licensed under MIT

## Getting Started

### Prerequisites

- Python 3.10 or later
- Git
- `pytest` 7.0+ (for running tests)

### Setup

```bash
# Clone the repository
git clone <repository-url> flux-conformance
cd flux-conformance

# Install in development mode
pip install -e ".[dev]"

# Verify the suite runs
python -m pytest test_conformance.py -v

# Verify v3 tests run
python -m pytest test_conformance_v3.py -v
```

### Project Structure

```
flux-conformance/
├── conformance_core.py        # Core: opcodes, reference VM, test cases
├── test_conformance.py        # Pytest tests for v2 (113 vectors)
├── test_conformance_v3.py     # Pytest tests for v3 (62 vectors)
├── conformance-vectors.json   # Exported test vectors (JSON)
├── benchmark_flux.py          # Performance benchmarks
├── run_conformance.py         # Cross-runtime runner
├── pyproject.toml             # Project configuration
├── README.md                  # Main documentation
├── ARCHITECTURE.md            # Technical architecture
├── CHANGELOG.md               # Version history
├── CONTRIBUTING.md            # This file
└── CROSS-RUNTIME-RESULTS.md   # Cross-runtime analysis
```

## Writing New Test Vectors

Test vectors are the fundamental unit of the conformance suite. Each vector defines a complete test: bytecode program, inputs, expected outputs, and metadata.

### Adding Vectors in Python

The primary way to add test vectors is by adding `ConformanceTestCase` instances to the `_build_all_test_cases()` function in `conformance_core.py`. This ensures the vectors are available both to pytest and to the cross-runtime runner.

#### Naming Convention

Test names follow the pattern `{category}_{operation}_{variant}`:

| Category | Prefix | Examples |
|----------|--------|----------|
| System Control | `sys_` | `sys_halt_empty`, `sys_nop_noop` |
| Integer Arithmetic | `arith_` | `arith_add_positive`, `arith_div_neg` |
| Comparison | `cmp_` | `cmp_eq_true`, `cmp_lt_negative` |
| Logic/Bitwise | `logic_` | `logic_and_basic`, `logic_shl_zero` |
| Memory | `mem_` | `mem_store_load`, `mem_poke_peek` |
| Control Flow | `ctrl_` | `ctrl_jz_taken`, `ctrl_factorial_5` |
| Stack Manipulation | `stack_` | `stack_dup`, `stack_multi_dup` |
| Float Operations | `float_` | `float_add`, `float_div_vs_int` |
| Confidence | `conf_` | `conf_get_initial`, `conf_mul_chain` |
| Agent-to-Agent | `a2a_` | `a2a_signal_listen`, `a2a_fifo_order` |
| Complex/Mixed | `complex_` | `complex_fibonacci`, `complex_abs_neg` |

#### Adding a Simple Test Case

```python
# In conformance_core.py, inside _build_all_test_cases():

cases.append(ConformanceTestCase(
    name="arith_xor_basic",           # Unique name following convention
    bytecode_hex=_h(P(0xAB) + P(0xCD) + bytes([XOR, H])),
    initial_stack=[],                  # Empty stack = no pre-loaded values
    expected_stack=[0x66],             # Expected stack after execution
    expected_flags=FLAGS_ANY,          # Don't check flags (-1)
    description="0xAB ^ 0xCD = 0x66"   # Human-readable description
))
```

#### Adding a Test with Flag Checking

```python
cases.append(ConformanceTestCase(
    name="arith_sub_zero",
    bytecode_hex=_h(P(3) + P(3) + bytes([SUB, H])),
    initial_stack=[],
    expected_stack=[0],
    expected_flags=FLAG_Z,             # Check that Z flag is set
    description="3 - 3 = 0, Z set"
))
```

#### Adding a Test with Initial Stack

Using `initial_stack` makes the bytecode shorter by pre-loading values:

```python
cases.append(ConformanceTestCase(
    name="arith_add_stack",
    bytecode_hex=_h(bytes([ADD, H])),  # Just ADD + HALT
    initial_stack=[5, 3],              # Pre-loaded: bottom=5, top=3
    expected_stack=[8],
    expected_flags=FLAGS_ANY,
    description="ADD with initial stack [5, 3]"
))
```

#### Adding a Float Test with Epsilon

```python
cases.append(ConformanceTestCase(
    name="float_mul_pi_approx",
    bytecode_hex=_h(P(31416) + P(10000) + bytes([FDIV, H])),
    initial_stack=[],
    expected_stack=[3.1416],
    expected_flags=FLAGS_ANY,
    allow_float_epsilon=True,           # Allow 1e-5 tolerance
    description="31416 / 10000 = 3.1416 (approximate)"
))
```

### Bytecode Construction

Use the provided helper functions to construct bytecode correctly:

```python
from conformance_core import push_imm32, jmp_addr, jz_addr, store_addr, load_addr

# PUSH uses Format G (1 byte opcode + 4 bytes LE signed integer)
push_imm32(42)    # -> b'\x55\x2a\x00\x00\x00'

# JMP uses Format E (1 byte opcode + 2 bytes LE address)
jmp_addr(20)      # -> b'\x50\x14\x00'

# STORE uses Format F (1 byte opcode + 2 bytes LE address)
store_addr(100)   # -> b'\x41\x64\x00'
```

### Computing Expected Bytecode Offsets

When writing control flow tests, you must manually compute the byte offsets for jump targets. This is error-prone, so double-check your math:

```python
# Example: Sum 1..5 loop
# Offset:  Bytes:
# 0-4:    PUSH 0       (5 bytes)
# 5-9:    PUSH 5       (5 bytes)
# 10-14:  LOAD [0]     (3 bytes)
# 15-19:  LOAD [4]     (3 bytes)
# 20:     ADD          (1 byte)
# 21-25:  STORE [0]    (3 bytes)
# 26-30:  LOAD [4]     (3 bytes)
# 31:     DEC          (1 byte)
# 32-36:  STORE [4]    (3 bytes)
# 37-39:  JNZ 10       (3 bytes)  <- jumps back to offset 10
# 40-44:  LOAD [0]     (3 bytes)
# 45:     HALT         (1 byte)
```

### Adding Vectors as JSON

You can also contribute test vectors in JSON format (for runtimes that can't read Python). The JSON format maps directly to the `ConformanceTestCase` dataclass:

```json
{
  "name": "arith_xor_basic",
  "bytecode_hex": "55ab00000055cd0000003200",
  "initial_stack": [],
  "expected_stack": [102],
  "expected_flags": -1,
  "allow_float_epsilon": false,
  "description": "0xAB ^ 0xCD = 0x66"
}
```

Place JSON vector contributions in a new file (e.g., `contrib-vectors/your-name.json`) and reference them in your pull request.

### What Makes a Good Test Vector?

1. **Deterministic:** The test must produce the same result every time on the reference VM. Avoid tests that depend on timing, random values, or external state.
2. **Minimal:** Each vector should test one concept. If you're testing ADD, don't also test MUL in the same vector (unless you're specifically testing chaining).
3. **Documented:** The `description` field should clearly state what the test verifies and why the expected result is correct.
4. **Flag-aware:** Whenever possible, include `expected_flags` rather than using `FLAGS_ANY`. Flag checking catches subtle implementation bugs.
5. **Boundary-testing:** Prefer edge cases (zero, negative, max values, overflow) over typical cases that are unlikely to reveal bugs.

## Testing a New FLUX Runtime

To conformance-test a new FLUX runtime implementation against this suite, you have two options:

### Option 1: In-Process Testing (Python Runtimes)

If your runtime is implemented in Python, subclass `FluxRuntime`:

```python
# my_runtime_test.py
from run_conformance import ConformanceRunner, PythonReferenceRuntime
from conformance_core import ConformanceTestCase

class MyRuntimeAdapter:
    name = "my-runtime"
    description = "My custom FLUX VM"

    def run_test(self, case: ConformanceTestCase):
        # Your runtime's execution function
        bytecode = bytes.fromhex(case.bytecode_hex)
        stack, flags = my_vm_execute(bytecode, case.initial_stack)

        # Compare against expected
        passed = (stack == case.expected_stack)
        if case.expected_flags != -1:
            passed = passed and (flags == case.expected_flags)

        return {
            "name": case.name,
            "passed": passed,
            "error": "" if passed else "Result mismatch",
            "actual_stack": stack,
            "actual_flags": flags
        }

# Run all tests
from conformance_core import ConformanceTestSuite
suite = ConformanceTestSuite()
suite.load_builtin_cases()

results = []
for case in suite.cases:
    results.append(MyRuntimeAdapter().run_test(case))

passed = sum(1 for r in results if r["passed"])
failed = len(results) - passed
print(f"My Runtime: {passed}/{len(results)} passed")
for r in results:
    if not r["passed"]:
        print(f"  FAIL: {r['name']} — {r['error']}")
```

### Option 2: Subprocess Testing (Any Language)

Implement a program that reads JSON from stdin and writes JSON to stdout:

```rust
// conformance_runner.rs (example structure)
fn main() {
    let input: serde_json::Value = serde_json::from_reader(io::stdin()).unwrap();
    let bytecode_hex = input["bytecode_hex"].as_str().unwrap();
    let initial_stack: Vec<i64> = serde_json::from_value(input["initial_stack"].clone()).unwrap();

    let bytecode = hex::decode(bytecode_hex).unwrap();
    let (stack, flags) = my_flux_vm(&bytecode, &initial_stack);

    let output = serde_json::json!({
        "passed": stack == expected_stack && flags == expected_flags,
        "actual_stack": stack,
        "actual_flags": flags,
        "error": if passed { "" } else { "Result mismatch" }
    });
    println!("{}", output);
}
```

Then test using the unified runner:

```bash
python run_conformance.py --all
```

### Step-by-Step Runtime Conformance Process

1. **Start with P0 opcodes** (HALT, NOP, PUSH, POP, ADD, SUB, MUL). These are the simplest and most universally portable.
2. **Run category by category:** Use `--category arith`, `--category ctrl`, etc. to isolate failures.
3. **Fix failures incrementally:** Each failure is a concrete bug in your runtime. The test vector name and description tell you exactly what's wrong.
4. **Check flags carefully:** Many failures are due to incorrect flag updates, not incorrect stack values.
5. **Verify float semantics:** Ensure your runtime truncates (not floors) negative division and handles float epsilon correctly.
6. **Run the full suite:** Once all categories pass individually, run the complete suite without filtering.

## Code Style Guide

### Python Style

- Follow PEP 8 conventions
- Use 4-space indentation (no tabs)
- Maximum line length: 100 characters
- Use type hints for function signatures
- Use docstrings for all public classes and functions
- Prefer `dataclasses` for data structures

### Test Vector Style

- Name test vectors using the `{category}_{operation}_{variant}` convention
- Always provide a `description` field
- Use `FLAGS_ANY` (-1) only when flag behavior is genuinely irrelevant
- Use `allow_float_epsilon=True` only for float operations
- Keep bytecode minimal — use `initial_stack` when possible

### Bytecode Encoding

- All multi-byte values are little-endian
- PUSH uses 32-bit signed integers (Format G)
- Addresses use 16-bit unsigned integers (Format E/F)
- Channel numbers use 8-bit unsigned integers (Format D)

## Pull Request Process

### Before Submitting

1. Ensure all existing tests pass: `python -m pytest test_conformance.py test_conformance_v3.py -v`
2. If adding test vectors, verify each one passes against the reference VM
3. Run the unified runner: `python run_conformance.py`
4. Update `CHANGELOG.md` with your changes under a new `[Unreleased]` section

### PR Description Template

```markdown
## Summary
Brief description of what this PR changes and why.

## Test Vectors Added
- `category_name_operation`: What it tests and why

## Testing
- [ ] All existing tests pass
- [ ] New test vectors pass against reference VM
- [ ] Cross-runtime runner reports correct results

## Related Issues
Link to related issues or spec changes
```

### Review Process

1. A maintainer will review your PR within 5 business days
2. Test vectors are reviewed for correctness, minimality, and naming
3. Code changes are reviewed for style and correctness
4. You may be asked to make revisions before merge

## Test Vector Review Criteria

When reviewing test vector contributions, maintainers evaluate against these criteria:

### Correctness (Required)
- The vector passes against the reference VM (`FluxVM`)
- The expected stack and flags are mathematically correct
- The bytecode encodes valid instructions with correct operand sizes
- Jump targets point to valid instruction boundaries

### Coverage Value (Required)
- The vector tests behavior not already covered by existing vectors
- The vector targets an opcode, edge case, or interaction that matters for cross-runtime conformance
- The vector helps catch a class of bugs (not just a single instance)

### Minimalism (Preferred)
- The vector is as short as possible while still being clear
- The vector tests one primary concept
- `initial_stack` is used to reduce bytecode size when appropriate

### Documentation (Preferred)
- The `description` field clearly explains what's being tested
- The name follows the `{category}_{operation}_{variant}` convention
- Flag expectations are explicit (not `FLAGS_ANY`) when meaningful

### Completeness (Nice to Have)
- The vector includes flag checking
- The vector tests a boundary condition (zero, negative, max, overflow)
- The vector has a corresponding manual pytest test in the category test class

### Red Flags (Reject)
- Vector fails against the reference VM
- Bytecode contains invalid instruction sequences
- Vector is a duplicate of an existing vector
- Description is missing or misleading
- Name doesn't follow the convention
