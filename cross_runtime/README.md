# Cross-Runtime Conformance Tests

Proves that the **Python VM** and **Go VM** produce identical results for the same FLUX Unified ISA bytecode.

## Why Cross-Runtime Conformance Matters

FLUX targets multiple runtimes (Python reference, Go production, and potentially others). A bug in one runtime that doesn't exist in another causes silent data divergence — the worst kind of production failure. Cross-runtime conformance tests:

1. **Lock in semantics** — the test vectors define the *canonical* behavior for every instruction.
2. **Detect drift** — if a Go optimisation subtly changes an edge-case result, these tests catch it immediately.
3. **Enable safe refactors** — rewrite the Go execution engine with confidence that behaviour is preserved.
4. **Document the ISA** — each vector is a self-contained, machine-verifiable example of how an instruction works.

## Quick Start

### Run all tests (Python execution + Go test generation + Markdown report)

```bash
cd cross_runtime/
python3 run_cross_conformance.py
```

### Python only (no Go test file generated)

```bash
python3 run_cross_conformance.py --python-only
```

### Go test file only (no Python execution)

```bash
python3 run_cross_conformance.py --go-only
```

### Generate a Markdown report

```bash
python3 run_cross_conformance.py --report=cross_report.md
```

### Run with verbose output (disassembly + register dumps)

```bash
python3 run_cross_conformance.py --verbose
```

### Run only arithmetic tests

```bash
python3 run_cross_conformance.py --filter arith
```

### Include slow tests (e.g. cycle-limit)

```bash
python3 run_cross_conformance.py --include-slow
```

## File Layout

```
cross_runtime/
  unified_test_vectors.json   # 33 test vectors (source of truth)
  python_adapter.py           # Runs vectors against the Python FluxMiniVM
  go_adapter.py               # Generates Go test file from vectors
  run_cross_conformance.py    # Main entry point
  flux_vm_test.go             # [generated] Go test file
  README.md                   # This file
```

## Test Vectors

All vectors live in [`unified_test_vectors.json`](unified_test_vectors.json). Each vector contains:

| Field | Description |
|-------|-------------|
| `name` | Unique identifier, e.g. `arith-add-10-plus-20` |
| `description` | Human-readable summary |
| `bytecode_hex` | Space-separated hex bytes (Unified ISA encoding) |
| `expected_final.registers` | Map of `R<n>` to expected values |
| `expected_final.halted` | Expected VM halted state |
| `expected_final.error` | Expected error-flag state |
| `category` | One of: system, arithmetic, logic, comparison, branch, stack, edge, composite |
| `tags` | Optional; `["slow"]` skips the test by default |

### Categories

| Category | Count | Description |
|----------|-------|-------------|
| `system` | 3 | HALT, NOP, RET |
| `arithmetic` | 8 | ADD, SUB, MUL, DIV, MOD, INC, DEC, NEG |
| `logic` | 4 | AND, OR, XOR, NOT |
| `comparison` | 4 | CMP_EQ, CMP_LT, CMP_GT, CMP_NE |
| `branch` | 6 | JMP, JZ (taken/not-taken), JNZ (taken/not-taken), CALL/RET |
| `stack` | 1 | PUSH/POP round-trip |
| `edge` | 4 | Division by zero, R0 immutability, end-of-bytecode, cycle limit |
| `composite` | 3 | Countdown loop, sum 1..5, nested additions |
| **Total** | **33** | |

### Unified ISA Encoding Reference

```
Format A (1 byte):  [op]                    HALT=0x00  NOP=0x01  RET=0x02
Format B (2 bytes): [op][rd]                INC=0x08   DEC=0x09   NOT=0x0A   NEG=0x0B   PUSH=0x0C  POP=0x0D
Format E (4 bytes): [op][rd][rs1][rs2]      ADD=0x20   SUB=0x21   MUL=0x22   DIV=0x23   MOD=0x24
                                                AND=0x25   OR=0x26    XOR=0x27
                                                CMP_EQ=0x2C CMP_LT=0x2D CMP_GT=0x2E CMP_NE=0x2F
Format F (4 bytes): [op][rd][imm16_lo][imm16_hi]
                                                MOVI=0x18  ADDI=0x19  SUBI=0x1A
                                                JMP=0x43   JZ=0x44    JNZ=0x45   CALL=0x4A
```

All immediates are signed 16-bit, little-endian. Registers are 32-bit signed. R0 is hardwired to 0.

## Running on the Go VM

### Step 1: Generate the Go test file

```bash
python3 go_adapter.py --output /path/to/flux/pkg/vm/flux_vm_test.go
```

Or use the main runner:

```bash
python3 run_cross_conformance.py --go-output /path/to/flux/pkg/vm/flux_vm_test.go
```

### Step 2: Ensure the Go VM implements the expected interface

The generated test code expects the Go VM package to expose:

```go
package vm

type VM struct { ... }

func New() *VM
func (m *VM) Load(code []byte)
func (m *VM) Run()
func (m *VM) Halted() bool
func (m *VM) Error() bool
func (m *VM) GetReg(idx int) int32
func (m *VM) SetReg(idx int, val int)
```

Key behavioural requirements:
- `R0` must always read as `0`, regardless of writes
- Registers are 32-bit signed (wrap on overflow)
- `DIV`/`MOD` by zero must set the error flag and halt
- `RET` on empty stack must set the error flag and halt
- Falling off the end of bytecode must set `halted = false`
- A cycle limit (typically 10M instructions) must trigger error + halt

### Step 3: Run the Go tests

```bash
cd /path/to/flux/
go test -v -run TestCrossRuntime ./pkg/vm/
```

## Adding New Vectors

1. Open `unified_test_vectors.json`
2. Add a new entry to the `vectors` array:

```json
{
  "name": "my-new-test",
  "description": "What this test verifies",
  "bytecode_hex": "18 01 2a 00 0b 01 00",
  "expected_final": {
    "registers": {"R1": -42},
    "halted": true,
    "error": false
  },
  "category": "arithmetic"
}
```

3. Verify against Python:

```bash
python3 python_adapter.py --filter my-new-test
```

4. Regenerate the Go test file:

```bash
python3 go_adapter.py
```

5. Run the full suite to confirm nothing broke:

```bash
python3 run_cross_conformance.py --report=cross_report.md
```

### Bytecode Construction Tips

- **MOVI R1, 42**: `18 01 2a 00` (op=0x18, rd=1, imm16=42 in LE)
- **MOVI R1, -1**: `18 01 ff ff` (op=0x18, rd=1, imm16=-1 → 0xFFFF in LE)
- **ADD R3, R1, R2**: `20 03 01 02` (op=0x20, rd=3, rs1=1, rs2=2)
- **JZ R1, +2**: `44 01 02 00` (op=0x44, cond=1, offset=+2 in LE)
- **JNZ R1, -10**: `45 01 f6 ff` (op=0x45, cond=1, offset=-10 → 0xFFF6 in LE)

Use the Python adapter's `--verbose` flag to see disassembly of each vector.

## Current Status

| Runtime | Status | Date |
|---------|--------|------|
| Python (FluxMiniVM) | **32/32 pass** (1 slow skipped) | 2026-04-12 |
| Go (pkg/vm) | Pending — generate and run `flux_vm_test.go` | — |

All 33 vectors pass on the Python reference runtime. Go runtime conformance is validated by generating and running the Go test file.
