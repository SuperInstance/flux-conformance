# FLUX Conformance — Master Roadmap

> **One test suite to rule them all.**
> Any runtime that passes is certified FLUX-compatible.

**Author:** Datum, Fleet Quartermaster
**Created:** 2026-04-14
**Status:** Active Planning
**Version:** 1.0.0

---

## Table of Contents

1. [Vision](#1-vision)
2. [Current State Assessment](#2-current-state-assessment)
3. [Phase 1 — Consolidate (Week 1)](#3-phase-1--consolidate-week-1)
4. [Phase 2 — Cover the Gaps (Week 2)](#4-phase-2--cover-the-gaps-week-2)
5. [Phase 3 — Multi-Runtime Harness (Week 3-4)](#5-phase-3--multi-runtime-harness-week-3-4)
6. [Phase 4 — CI/CD Integration (Week 5)](#6-phase-4--cicd-integration-week-5)
7. [Phase 5 — Runtime Certification (Week 6-8)](#7-phase-5--runtime-certification-week-6-8)
8. [Phase 6 — Performance Benchmarking (Week 8+)](#8-phase-6--performance-benchmarking-week-8)
9. [Phase 7 — ISA v3 Full Coverage (Month 3+)](#9-phase-7--isa-v3-full-coverage-month-3)
10. [Integration with datum-runtime](#10-integration-with-datum-runtime)
11. [Dependencies and Fleet Coordination](#11-dependencies-and-fleet-coordination)
12. [Risk Register](#12-risk-register)
13. [Success Metrics](#13-success-metrics)

---

## 1. Vision

flux-conformance exists to answer one question with absolute authority:

> **"Is this runtime FLUX-compatible?"**

The answer must be binary, reproducible, and trustworthy. Every FLUX runtime
in the fleet — Python, TypeScript/WASM, Rust, C, Go, CUDA, and any future
implementation — should be able to run a single command and receive a
definitive PASS or FAIL against the full ISA specification.

### Principles

```
  ┌──────────────────────────────────────────────────────────────┐
  │                    DESIGN PHILOSOPHY                         │
  │                                                              │
  │  1. SINGLE SOURCE OF TRUTH    One runner, one vector set     │
  │  2. RUNTIME AGNOSTIC          No assumptions about impl       │
  │  3. SPECIFICATION-DRIVEN      Every vector traces to ISA.md   │
  │  4. REPRODUCIBLE              Deterministic, no timestamps   │
  │  5. GRADUAL COMPLIANCE        P0 → P1 → P2 → P3 levels       │
  │  6. AUTOMATED GATES           CI blocks non-conformant pushes │
  └──────────────────────────────────────────────────────────────┘
```

### The Certification Promise

```
  A runtime earns "FLUX Certified v2" by passing ALL v2 vectors.
  A runtime earns "FLUX Certified v3" by passing ALL v3 vectors.
  A runtime earns "FLUX Certified Gold" by passing both + benchmarks.
```

This is the single command that every runtime developer should be able
to run:

```bash
pip install flux-conformance
flux-conformance run --runtime ./my-vm --certify
```

---

## 2. Current State Assessment

### 2.1 What Exists — File Inventory

```
flux-conformance/                          (~4,000 LOC total)
├── conformance_core.py                    1,249 LOC  — Reference VM + 113 vectors
├── canonical_opcode_shim.py                 383 LOC  — Cross-runtime translation
├── flux_universal_validator.py              553 LOC  — Bytecode validator
├── run_conformance.py                       519 LOC  — V2 cross-runtime runner
├── run_v3_conformance.py                    276 LOC  — V3-specific runner
├── benchmark_flux.py                        499 LOC  — Performance benchmarks
├── test_conformance.py                      ~200 LOC  — Pytest v2 tests
├── test_conformance_v3.py                   ~200 LOC  — Pytest v3 tests
├── conformance-vectors.json                  ~N/A    — 113 v2 vectors (JSON)
├── conformance-vectors-v3.json               ~N/A    — 68 v3 vectors (JSON)
├── pyproject.toml                              —    — v0.1.0 pip-installable
├── tests/
│   ├── test_conformance.py
│   ├── test_opcode_shim.py
│   └── test_validator.py
└── Documentation (7 files, ~2,800 LOC)
    ├── README.md
    ├── ARCHITECTURE.md
    ├── CHANGELOG.md
    ├── CONTRIBUTING.md
    ├── CROSS-RUNTIME-RESULTS.md
    ├── CONFORMANCE-CAPABILITY-MATRIX.md
    └── CROSS-RUNTIME-CONFORMANCE-AUDIT-REPORT.md
```

### 2.2 What Works

| Component | Status | Quality |
|-----------|--------|---------|
| Python reference VM (FluxVM) | WORKING | 113/113 vectors pass (96.9% after CONF fix) |
| FluxVMv3 extension VM | WORKING | 62/62 v3 vectors expected pass |
| FluxFlags register | WORKING | Full Z/S/C/O implementation |
| Bytecode helpers | WORKING | push_imm32, jmp, jz, jnz, call, store, load |
| ConformanceTestSuite runner | WORKING | run_single, run_all, summary |
| Pytest integration | WORKING | Parametrized tests + manual categories |
| Benchmark harness (PERF-001) | WORKING | 12 categories, JSON/Markdown output |
| SubprocessRuntime adapter | WORKING | JSON-over-stdin protocol |
| Canonical opcode shim | WORKING | Python↔Canonical↔Rust↔C↔Go mapping |
| Universal bytecode validator | WORKING | Coverage, control flow, register analysis |

### 2.3 What Doesn't Work

| Gap | Severity | Root Cause |
|-----|----------|------------|
| Three separate runners | HIGH | Organic growth; run_conformance.py, run_v3_conformance.py, oracle1/unified_runner.py |
| Vector format incompatibility | HIGH | Stack-based vs register-based vector schemas |
| No actual cross-runtime testing | HIGH | SubprocessRuntime exists but no runtimes implement the protocol |
| CONF subsystem broken (5/113) | MEDIUM | Spec ambiguity: float vs int-scaled confidence |
| Only 161 vectors (v2.1) | MEDIUM | 247 defined opcodes, many untested |
| No CI/CD | MEDIUM | No GitHub Actions workflow |
| No certification system | LOW | No badge, no automated pass/fail gate |
| No datum-runtime integration | LOW | `datum-rt conformance run` not wired up |

### 2.4 The Fragmentation Problem

There are currently THREE test runner implementations in the fleet,
each with incompatible vector formats and VM models:

```
  ┌─────────────────────────────────────────────────────────────────────┐
  │                    CURRENT RUNNER FRAGMENTATION                      │
  │                                                                      │
  │  flux-conformance/                                                   │
  │  ├── run_conformance.py          → Stack VM, 113 v2 vectors         │
  │  │   Vector format: bytecode_hex + initial_stack + expected_stack    │
  │  │   VM: FluxVM (stack-based, 41 opcodes)                            │
  │  │                                                                    │
  │  ├── run_v3_conformance.py        → Stack VM, 68 v3 vectors          │
  │  │   Vector format: bytecode_hex + initial_stack + expected_stack    │
  │  │   VM: FluxVMv3 (stack-based, 41 + escape opcodes)                 │
  │  │                                                                    │
  │  oracle1/for-jetsonclaw1/conformance/                                │
  │  ├── runners/unified_runner.py    → Register VM, 88 vectors          │
  │  │   Vector format: bytecode + initial_registers + expected_registers│
  │  │   VM: FluxMiniVM (register-based, 34 opcodes)                      │
  │  │                                                                    │
  │  └── runners/cross_runtime_runner.py → Register VM, 88 vectors       │
  │      Vector format: bytecode + preconditions + expected.gp/.fp       │
  │      VM: flux-runtime Interpreter (register-based, 122 opcodes)       │
  │                                                                      │
  │  PROBLEM: Same "conformance" word, 3 different meanings.             │
  └─────────────────────────────────────────────────────────────────────┘
```

### 2.5 The Portability Crisis

```
  ┌──────────────────────────────────────────────────┐
  │         CROSS-RUNTIME OPCODE COVERAGE            │
  │                                                   │
  │  Runtime   Opcodes  Vectors  Pass Rate             │
  │  ──────────────────────────────────────           │
  │  Python       41/41   161/161   96.9%             │
  │  WASM         27/41    ~95/161  59.0%             │
  │  Rust         18/41    ~65/161  40.4%             │
  │  C            13/41    ~45/161  28.0%             │
  │  Go            8/41    ~30/161  18.6%             │
  │  ──────────────────────────────────────           │
  │  Universal      7/41    ~18/161  100%              │
  │                                                   │
  │  Only 7 opcodes work on ALL runtimes:             │
  │  { HALT, NOP, ADD, SUB, EQ, JMP, PUSH, POP }     │
  │                                                   │
  │  93% of the ISA is inaccessible for portable      │
  │  cross-runtime programming.                       │
  └──────────────────────────────────────────────────┘
```

### 2.6 ISA Specification Scope

| Metric | ISA v2 | ISA v3 |
|--------|--------|--------|
| Defined opcodes | 247 | ~275 primary + 32 escape |
| Encoding formats | 7 (A-G) | 7 + compressed shorts |
| Extension spaces | 0 | 4 (temporal, security, async, negotiation) |
| Test vectors (current) | 113 | 68 |
| Test vectors (target) | 300+ | 500+ |
| Escape sub-opcodes | N/A | 256 (0x00-0xFF) |

---

## 3. Phase 1 — Consolidate (Week 1)

**Goal:** Merge three separate runners into one unified runner with a single
vector format. Resolve the stack-based vs register-based incompatibility.

**Dependencies:** None (self-contained within flux-conformance)
**Estimated LOC:** ~600 new/modified

### 3.1 Unified Vector Schema

Define a single vector format that can express both stack-based and
register-based expectations:

```json
{
  "schema": "flux-conformance-v3",
  "version": "3.0",
  "name": "arith_add_3_4",
  "category": "arithmetic",
  "tier": "P0",
  "bytecode": "55030000005504000000100000",
  "expectations": {
    "stack": {
      "post": [7],
      "allow_float_epsilon": false
    },
    "registers": {
      "post": {"R0": 7},
      "mode": "any_match"
    },
    "flags": {
      "expected": "0x02",
      "mask": "Z"
    },
    "halt_state": "halted",
    "error": null
  },
  "isa_version": "v2",
  "description": "ADD: push 3, push 4, ADD → 7"
}
```

The key insight: **a vector can specify expectations for BOTH stack
and registers**. The runner checks whichever fields are present. This
allows the same vector to test both stack-based and register-based VMs.

**Files:**
- `src/vector_schema.py` — Schema definition and validation (~150 LOC)
- `src/vector_loader.py` — Load from JSON files + built-in Python (~200 LOC)
- `vectors/unified/` — Directory for all vectors in unified format

### 3.2 Merge Runners

Create a single `flux_conformance` package with one entry point:

```
  BEFORE (3 runners):                          AFTER (1 runner):
  ───────────────────                          ──────────────────
  run_conformance.py           ──┐             flux_conformance/
  run_v3_conformance.py         ├──────────→   ├── cli.py
  oracle1/unified_runner.py     ──┘             ├── runner.py
                                                      ├── engines/
                                                      │   ├── stack_engine.py
                                                      │   ├── register_engine.py
                                                      │   └── subprocess_engine.py
                                                      ├── schema/
                                                      │   ├── vector.py
                                                      │   └── loader.py
                                                      └── reporters/
                                                          ├── terminal.py
                                                          ├── json_reporter.py
                                                          └── junit_reporter.py
```

**Files:**
- `src/cli.py` — Click-based CLI with subcommands (~250 LOC)
- `src/runner.py` — Core test orchestration (~300 LOC)
- `src/engines/stack_engine.py` — Wraps existing FluxVM (~100 LOC)
- `src/engines/register_engine.py` — Port from unified_runner.py (~200 LOC)
- `src/engines/subprocess_engine.py` — Wraps existing SubprocessRuntime (~150 LOC)

### 3.3 Vector Migration

Migrate all existing vectors to the unified schema:

| Source | Vectors | Action |
|--------|---------|--------|
| `conformance-vectors.json` (v2) | 113 | Reformat to unified schema |
| `conformance-vectors-v3.json` (v3) | 68 | Reformat to unified schema |
| `oracle1/.../vectors/vectors/` | 88 | Reformat + deduplicate |
| `oracle1/.../vectors/unified/` | 29 | Merge into unified set |
| **Total unique** | **~250** | **~50 duplicates removed** |

**Files:**
- `scripts/migrate_vectors.py` — Automated migration script (~150 LOC)
- `vectors/unified/*.json` — Individual vector files
- `vectors/manifest.json` — Vector index with categories and tiers

### 3.4 Package Restructure

Move from flat files to a proper Python package:

```
flux-conformance/
├── pyproject.toml              ← UPDATE: v0.2.0, add click, rich deps
├── src/
│   └── flux_conformance/
│       ├── __init__.py
│       ├── core.py             ← FROM: conformance_core.py (FluxVM, FluxFlags)
│       ├── shim.py             ← FROM: canonical_opcode_shim.py
│       ├── validator.py        ← FROM: flux_universal_validator.py
│       ├── cli.py              ← NEW: unified CLI
│       ├── runner.py           ← NEW: test orchestration
│       ├── schema/
│       │   ├── __init__.py
│       │   ├── vector.py       ← NEW: ConformanceVector dataclass
│       │   └── loader.py       ← NEW: vector loading
│       ├── engines/
│       │   ├── __init__.py
│       │   ├── base.py         ← NEW: FluxEngine ABC
│       │   ├── stack.py        ← NEW: FluxVM wrapper
│       │   ├── register.py     ← NEW: FluxMiniVM port
│       │   └── subprocess.py   ← NEW: external runtime adapter
│       └── reporters/
│           ├── __init__.py
│           ├── terminal.py
│           ├── json_reporter.py
│           └── junit_reporter.py
├── vectors/
│   ├── v2/                     ← 113+ vectors (stack format)
│   ├── v3/                     ← 68+ vectors (escape prefix)
│   ├── unified/                ← 250+ vectors (unified format)
│   └── manifest.json
├── tests/
│   ├── test_core.py
│   ├── test_shim.py
│   ├── test_validator.py
│   ├── test_runner.py
│   ├── test_schema.py
│   └── test_cli.py
├── benchmark_flux.py           ← KEEP: standalone benchmark
└── ROADMAP.md                  ← THIS FILE
```

### 3.5 Deliverables

| Deliverable | File | LOC |
|-------------|------|-----|
| Unified vector schema | `src/flux_conformance/schema/vector.py` | ~150 |
| Vector loader | `src/flux_conformance/schema/loader.py` | ~200 |
| CLI entry point | `src/flux_conformance/cli.py` | ~250 |
| Core runner | `src/flux_conformance/runner.py` | ~300 |
| Stack engine | `src/flux_conformance/engines/stack.py` | ~100 |
| Register engine | `src/flux_conformance/engines/register.py` | ~200 |
| Subprocess engine | `src/flux_conformance/engines/subprocess.py` | ~150 |
| Migration script | `scripts/migrate_vectors.py` | ~150 |
| Updated pyproject.toml | `pyproject.toml` | ~30 |
| **Phase 1 Total** | | **~1,530** |

### 3.6 CLI Design

```bash
# Run all vectors against Python reference
flux-conformance run

# Run against a specific runtime
flux-conformance run --runtime ./my-vm --engine subprocess

# Run only v3 vectors
flux-conformance run --isa v3

# Run only P0 (universally portable) vectors
flux-conformance run --tier P0

# Run a specific category
flux-conformance run --category arithmetic

# Output as JUnit XML for CI
flux-conformance run --junit results.xml

# List all vectors
flux-conformance list --format table

# Export vectors for other runtimes
flux-conformance export --format json --output vectors.json

# Validate a runtime's conformance level
flux-conformance certify --runtime ./my-vm
```

---

## 4. Phase 2 — Cover the Gaps (Week 2)

**Goal:** Expand from ~250 vectors to 300+. Cover all 247 ISA v2 opcodes
and add the 42 edge-case vectors recommended by CONF-002.

**Dependencies:** Phase 1 (unified runner and schema)
**Estimated LOC:** ~800 new

### 4.1 Opcode Coverage Gap Analysis

Current coverage by ISA v2 opcode category:

```
  ┌──────────────────────────────────────────────────────────────┐
  │              OPCODE COVERAGE GAP MAP                          │
  │                                                               │
  │  Category         Defined   Tested   Gap    Priority         │
  │  ──────────────────────────────────────────────────          │
  │  System (HALT,NOP)     3       3      0       DONE           │
  │  Arithmetic          12      12      0       DONE           │
  │  Comparison           8       6      2       HIGH           │
  │  Logic/Bitwise       10       6      4       HIGH           │
  │  Memory              10       4      6       HIGH           │
  │  Control Flow        12       7      5       HIGH           │
  │  Stack                8       4      4       MEDIUM         │
  │  Float                8       4      4       MEDIUM         │
  │  Confidence           5       3      2       HIGH*          │
  │  A2A                  8       3      5       MEDIUM         │
  │  ──────────────────────────────────────────────────          │
  │  TOTAL               84      52     32                       │
  │                                                               │
  │  * CONF subsystem has spec ambiguity — needs ISA clarification│
  │  Note: 247 total ISA opcodes includes many NOT in conformance │
  │  core (FIR-only, meta-instructions, debug ops, etc.)          │
  └──────────────────────────────────────────────────────────────┘
```

### 4.2 New Vector Categories

**CONF-002 Edge Cases (42 vectors — already specified):**

```
  Control Flow (8):
    - jz_flag_set, jz_flag_clear, jnz_flag_set, jnz_flag_clear
    - call_ret_nested_3, ret_empty_stack, jmp_backward, jz_after_arith

  Arithmetic (10):
    - add_overflow, sub_underflow, mul_overflow, mul_zero, mul_negative
    - div_truncate, mod_negative, neg_int32_min, inc_overflow, dec_underflow

  Float (8):
    - fadd_nan, fsub_inf_inf, fmul_zero_inf, fdiv_by_zero
    - fadd_large_inf, fdiv_denorm, fmul_neg_pos, mixed_int_float

  Stack (6):
    - dup_empty, swap_single, over_single, rot_two, pop_empty, push_zero

  Memory (6):
    - load_uninit, store_load_verify, store_max_addr, load_addr_zero
    - peek_unaligned, poke_peek_verify

  Flags (4):
    - add_sets_zero, sub_sets_sign, and_clears_overflow, xor_sets_zero

  Integration (5):
    - factorial_5, fibonacci_10, bubble_sort_3, nested_subroutine, signal_roundtrip
```

**Additional Gap Coverage (estimated ~50 vectors):**

```
  Comparison (2): ge_equal_values, ge_mixed_signs
  Logic (4): shift_left_max, shift_right_max, rotate_full_circle, not_all_bits
  Memory (6): store8_load8_boundary, store16_load16, memset_pattern,
              memory_wrap_64k, peek_poke_multi, region_overlap
  Control (5): call_self_recursion, ret_mid_loop, jmp_into_call,
               nested_loop_break, switch_emulation
  Stack (4): over_deep_5deep, rot4_cycle, swap_parity, pushpop_large
  Float (4): fabs_neg, fmin_max_same, fadd_sub_zero, fmul_identity
  A2A (5): signal_capacity, listen_order_multi, broadcast_self,
            delegate_chain, channel_isolation_stress
  Confidence (3): conf_get_set_roundtrip, conf_mul_identity,
                  conf_clamp_boundary (after spec fix)
```

### 4.3 Vector Authoring Workflow

Create a semi-automated workflow for vector authoring:

```
  ┌────────────────────────────────────────────────────────────────┐
  │                 VECTOR AUTHORING PIPELINE                       │
  │                                                                 │
  │  1. SPEC REFERENCE                                              │
  │     └─→ isa-v3-draft.md §opcode-table                          │
  │                                                                 │
  │  2. AUTHOR (Python helper)                                      │
  │     python -m flux_conformance.tools.author \                   │
  │         --opcode DIV --category arithmetic \                    │
  │         --cases "basic,truncate,neg,zero,max"                   │
  │                                                                 │
  │  3. GENERATE (automatic)                                        │
  │     └─→ vectors/unified/arith-div-*.json                       │
  │                                                                 │
  │  4. VALIDATE (automatic)                                        │
  │     python -m flux_conformance.tools.validate \                 │
  │         vectors/unified/arith-div-*.json                        │
  │                                                                 │
  │  5. RUN (reference VM)                                          │
  │     flux-conformance run --category arith-div                  │
  │                                                                 │
  │  6. REVIEW (human)                                              │
  │     Check for: wrong expectations, missing edge cases,          │
  │     insufficient description                                   │
  │                                                                 │
  │  7. COMMIT                                                       │
  │     git commit -m "add arith-div-* vectors (4 new)"             │
  └────────────────────────────────────────────────────────────────┘
```

**Files:**
- `src/flux_conformance/tools/author.py` — Vector authoring helper (~200 LOC)
- `src/flux_conformance/tools/validate.py` — Vector schema validator (~100 LOC)
- `vectors/unified/arith-*.json` — ~20 new arithmetic vectors
- `vectors/unified/cmp-*.json` — ~8 new comparison vectors
- `vectors/unified/logic-*.json` — ~10 new logic vectors
- `vectors/unified/mem-*.json` — ~12 new memory vectors
- `vectors/unified/ctrl-*.json` — ~13 new control vectors
- `vectors/unified/stack-*.json` — ~10 new stack vectors
- `vectors/unified/float-*.json` — ~12 new float vectors
- `vectors/unified/conf-*.json` — ~3 new confidence vectors
- `vectors/unified/a2a-*.json` — ~10 new A2A vectors
- `vectors/unified/integration-*.json` — ~5 integration vectors

### 4.4 ISA v3 Extension Vectors (Phase 2 subset)

Begin adding ISA v3 extension vectors in areas where the spec is clear:

```
  Escape Prefix (5 vectors):  ✅ Already exist in v3 JSON
  Temporal (8 vectors):       ✅ Already exist in v3 JSON
  Security (7 vectors):       ✅ Already exist in v3 JSON
  Async (7 vectors):          ✅ Already exist in v3 JSON
  Compressed Shorts (8):      ✅ Already exist in v3 JSON
  Backward Compat (15):       ✅ Already exist in v3 JSON
  ─────────────────────────────────────────────
  NEW in Phase 2:
  Negotiation (0xFF 0x04):    ~10 vectors (spec-dependent)
  Capability System:          ~8 vectors (after spec clarification)
  Sandbox Profiles:           ~6 vectors (after spec clarification)
```

### 4.5 Deliverables

| Deliverable | LOC |
|-------------|-----|
| 42 CONF-002 edge-case vectors (JSON) | ~500 |
| ~50 gap coverage vectors (JSON) | ~600 |
| Vector authoring tool | ~200 |
| Vector validation tool | ~100 |
| Updated manifest.json | ~100 |
| **Phase 2 Total** | **~1,500** |

### 4.6 Target: 300+ Vectors

After Phase 2, the vector count should be:

| Source | Count |
|--------|-------|
| Existing v2 (migrated) | 113 |
| Existing v3 (migrated) | 68 |
| Oracle1 unified (migrated) | 88 |
| CONF-002 edge cases (new) | 42 |
| Gap coverage (new) | ~50 |
| Deduplication | (~61) |
| **Net total** | **~300** |

---

## 5. Phase 3 — Multi-Runtime Harness (Week 3-4)

**Goal:** Build and test subprocess adapters for non-Python runtimes.
Make `flux-conformance run --runtime <path>` work for TypeScript/WASM,
Rust, C, and Go.

**Dependencies:** Phase 1 (unified runner), Phase 2 (sufficient vectors)
**Estimated LOC:** ~500 new in flux-conformance + ~200-400 per external runtime

### 5.1 Architecture: The Conformance Protocol

Every runtime must implement the FLUX Conformance Protocol — a simple
JSON-over-stdin/stdout contract:

```
  ┌────────────────────────────────────────────────────────────────────┐
  │                 FLUX CONFORMANCE PROTOCOL v1                      │
  │                                                                     │
  │  flux-conformance (runner)          External Runtime (SUT)          │
  │  ──────────────────────             ──────────────────────          │
  │                                                                     │
  │  stdin  ──── JSON request  ────→  stdin                             │
  │                {                                                      │
  │                  "version": "1.0",                                   │
  │                  "bytecode": "5503000000550400000010",               │
  │                  "initial_state": {                                  │
  │                    "stack": [],                                      │
  │                    "registers": {}                                   │
  │                  },                                                   │
  │                  "expectations": { ... }                             │
  │                }                                                      │
  │                                                                     │
  │  stdout ←── JSON response  ←───  stdout                            │
  │                {                                                      │
  │                  "passed": true,                                     │
  │                  "actual": {                                         │
  │                    "stack": [7],                                     │
  │                    "registers": {"R0": 7},                          │
  │                    "flags": "0x02",                                  │
  │                    "halt_state": "halted"                            │
  │                  },                                                   │
  │                  "error": "",                                        │
  │                  "duration_ns": 12345                                │
  │                }                                                      │
  │                                                                     │
  │  EXIT CODES:                                                         │
  │    0 = test passed (response.passed == true)                        │
  │    1 = test failed (response.passed == false)                        │
  │    2 = protocol error (bad JSON, timeout, crash)                     │
  └────────────────────────────────────────────────────────────────────┘
```

### 5.2 Runtime Adapter Implementations

**TypeScript/WASM (Priority 1 — highest impact):**

```
  Source: download/flux-wasm/
  Files:  src/vm.ts (2,209 LOC), src/opcode.ts (251 opcodes)

  New file needed:
    download/flux-wasm/src/run-conformance.ts (~150 LOC)

  Adapter reads JSON from stdin, executes bytecode on existing VM,
  returns JSON result to stdout.

  Build:
    npx tsc src/run-conformance.ts --out dist/
    node dist/run-conformance.js  <── flux-conformance calls this
```

**Rust (Priority 2):**

```
  Source: flux/crates/ (103 opcodes defined, 54 dispatched)

  New file needed:
    flux/crates/flux-conformance/src/main.rs (~200 LOC)

  Adapter: reads JSON from stdin, executes on flux-core VM,
  returns JSON result.

  Build:
    cargo build --release --package flux-conformance
    ./target/release/flux-conformance  <── flux-conformance calls this
```

**C (Priority 3):**

```
  Source: flux-os/ (184 opcodes defined, 58 dispatched)

  New file needed:
    flux-os/conformance-runner.c (~250 LOC)

  Adapter: minimal JSON parser (or use cJSON), execute bytecode,
  return JSON result.

  Build:
    gcc -O2 conformance-runner.c -o flux-c-conformance -lm
    ./flux-c-conformance  <── flux-conformance calls this
```

**Go (Priority 4):**

```
  Source: flux-swarm/ (14 opcodes — most limited runtime)

  New file needed:
    flux-swarm/cmd/conformance/main.go (~200 LOC)

  Adapter: read JSON from stdin, execute bytecode, return JSON.

  Build:
    go build ./cmd/conformance/
    ./conformance  <── flux-conformance calls this
```

### 5.3 Opcode Translation Layer

Before sending bytecode to an external runtime, the conformance
harness must translate from canonical opcode encoding to the
runtime's native encoding. This uses the existing
`canonical_opcode_shim.py`:

```
  ┌──────────────────────────────────────────────────────────────┐
  │               OPCODE TRANSLATION PIPELINE                    │
  │                                                               │
  │  Test Vector                                                  │
  │  bytecode: "5503..." (canonical encoding)                     │
  │       │                                                       │
  │       ▼                                                       │
  │  canonical_opcode_shim.translate(                             │
  │      bytecode, from="canonical", to="wasm")                   │
  │       │                                                       │
  │       ▼                                                       │
  │  Translated bytecode: "8003..." (WASM encoding)              │
  │       │                                                       │
  │       ▼                                                       │
  │  SubprocessRuntime.send(translated_bytecode)                  │
  │       │                                                       │
  │       ▼                                                       │
  │  External VM executes and returns result                     │
  └──────────────────────────────────────────────────────────────┘
```

### 5.4 Cross-Runtime Compatibility Shims

The translation layer needs per-runtime shim configuration:

```python
# src/flux_conformance/engines/translation.py

RUNTIME_SHIMS = {
    "python-reference": {
        "encoding": "canonical_stack",
        "translate": False,  # Reference uses canonical directly
    },
    "typescript-wasm": {
        "encoding": "wasm_register",
        "translate": True,
        "shim_module": "canonical_opcode_shim",
        "from": "canonical",
        "to": "wasm",
    },
    "rust-flux": {
        "encoding": "rust_register",
        "translate": True,
        "shim_module": "canonical_opcode_shim",
        "from": "canonical",
        "to": "rust",
    },
    # ... C, Go
}
```

### 5.5 Expected Cross-Runtime Results After Phase 3

Based on CONF-003 capability matrix predictions:

```
  ┌──────────────────────────────────────────────────────┐
  │        PREDICTED PASS RATES (Phase 3 Target)          │
  │                                                       │
  │  Runtime       Before P3    After P3    Delta         │
  │  ──────────────────────────────────────────          │
  │  Python         96.9%       98.0%      +1.1%         │
  │  WASM           59.0%       65.0%      +6.0%         │
  │  Rust           40.4%       45.0%      +4.6%         │
  │  C              28.0%       32.0%      +4.0%         │
  │  Go             18.6%       22.0%      +3.4%         │
  │                                                       │
  │  Note: Pass rates limited by opcode implementation   │
  │  in each runtime. Phase 3 adds the harness; actual    │
  │  rates depend on runtime teams implementing opcodes.  │
  └──────────────────────────────────────────────────────┘
```

### 5.6 Deliverables

| Deliverable | File | LOC |
|-------------|------|-----|
| Conformance protocol spec | `docs/PROTOCOL.md` | ~100 |
| Translation layer | `src/engines/translation.py` | ~150 |
| Runtime registry | `src/engines/registry.py` | ~100 |
| WASM adapter spec | `docs/adapters/wasm.md` | ~80 |
| Rust adapter spec | `docs/adapters/rust.md` | ~80 |
| C adapter spec | `docs/adapters/c.md` | ~80 |
| Go adapter spec | `docs/adapters/go.md` | ~80 |
| External adapter code (4 runtimes) | Other repos | ~800 |
| **Phase 3 Total (this repo)** | | **~670** |

---

## 6. Phase 4 — CI/CD Integration (Week 5)

**Goal:** GitHub Actions workflow that automatically tests all runtimes
on every push. Matrix build across Python versions and runtimes.

**Dependencies:** Phase 3 (at least WASM adapter working)
**Estimated LOC:** ~200 (YAML + scripts)

### 6.1 CI Pipeline Architecture

```
  ┌──────────────────────────────────────────────────────────────────┐
  │                    CI/CD PIPELINE                                 │
  │                                                                    │
  │  push / PR                                                        │
  │      │                                                             │
  │      ▼                                                             │
  │  ┌─────────────┐                                                  │
  │  │  LINT +     │  ruff check, mypy, black                         │
  │  │  TYPE CHECK │  ~2 min                                          │
  │  └──────┬──────┘                                                  │
  │         │                                                         │
  │         ▼                                                         │
  │  ┌─────────────────────────────────────────────┐                  │
  │  │          TEST MATRIX                         │                  │
  │  │                                               │                  │
  │  │  Python 3.10 │ pytest        │ ~3 min       │                  │
  │  │  Python 3.11 │ pytest        │ ~3 min       │                  │
  │  │  Python 3.12 │ pytest        │ ~3 min       │                  │
  │  │  Node.js 18  │ WASM adapter  │ ~5 min       │                  │
  │  │  Node.js 20  │ WASM adapter  │ ~5 min       │                  │
  │  │  Rust stable │ Rust adapter  │ ~10 min      │                  │
  │  │  C (gcc 13)  │ C adapter     │ ~5 min       │                  │
  │  └─────────────────────────────────────────────┘                  │
  │         │                                                         │
  │         ▼                                                         │
  │  ┌──────────────────┐                                            │
  │  │  CROSS-RUNTIME   │  Run full suite on all available runtimes  │
  │  │  CONFORMANCE     │  Generate pass/fail matrix                  │
  │  │  GATE            │  FAIL if any P0 vector fails               │
  │  └──────┬───────────┘                                            │
  │         │                                                         │
  │         ▼                                                         │
  │  ┌──────────────────┐                                            │
  │  │  CERTIFICATION   │  Update conformance badge                  │
  │  │  REPORT          │  Post results to PR comment                 │
  │  │                  │  Update CONFORMANCE-RESULTS.json           │
  │  └──────────────────┘                                            │
  └──────────────────────────────────────────────────────────────────┘
```

### 6.2 GitHub Actions Workflow

**File:** `.github/workflows/conformance.yml`

```yaml
name: FLUX Conformance

on:
  push:
    branches: [main, develop]
  pull_request:
    branches: [main]

jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - run: pip install ruff mypy
      - run: ruff check src/ tests/
      - run: mypy src/

  test-python:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ["3.10", "3.11", "3.12"]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with: { python-version: "${{ matrix.python-version }}" }
      - run: pip install -e ".[dev]"
      - run: pytest tests/ -v --tb=short --junitxml=results.xml
      - run: flux-conformance run --junit results-full.xml

  test-wasm:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        node-version: [18, 20]
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: "${{ matrix.node-version }}" }
      - run: npm ci --prefix test-runtimes/flux-wasm
      - run: pip install -e .
      - run: flux-conformance run --runtime node --engine subprocess \
            --junit results-wasm.xml

  test-rust:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: dtolnay/rust-toolchain@stable
      - run: cargo build --release -p flux-conformance
      - run: pip install -e .
      - run: flux-conformance run --runtime ./target/release/flux-conformance

  conformance-gate:
    needs: [test-python, test-wasm, test-rust]
    if: always()
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - run: pip install -e .
      - run: flux-conformance certify --runtime python --output badge.svg
      - name: Check P0 gate
        run: |
          flux-conformance run --tier P0 --json results.json
          # Fail if any P0 vector fails
          python -c "
          import json
          with open('results.json') as f:
              data = json.load(f)
          fails = [r for r in data['results'] if not r['passed']]
          if fails:
              print(f'P0 FAILURE: {len(fails)} vectors failed')
              exit(1)
          "
```

### 6.3 Branch Protection Rules

```
  main branch:
    ✓ Require status checks: lint, test-python (3.12), conformance-gate
    ✓ Require up-to-date branch
    ✓ Require 1 review (for non-Datum agents)

  develop branch:
    ✓ Require status checks: lint, test-python (3.10)
    ✓ No review required (agent commits)
```

### 6.4 Automated Reporting

After every CI run, generate and post a conformance report:

```markdown
## Conformance Report — Commit abc1234

| Runtime | Vectors | Passed | Failed | Rate |
|---------|---------|--------|--------|------|
| Python 3.12 | 300 | 295 | 5 | 98.3% |
| WASM (Node 20) | 300 | 195 | 105 | 65.0% |
| Rust (stable) | 300 | 135 | 165 | 45.0% |

### P0 (Universal) — All Runtimes: 18/18 PASS ✓
### P1 (Canonical) — Python: 100%, WASM: 80%, Rust: 55%
### P2 (Extended) — Python: 98%, WASM: 60%, Rust: 30%
### P3 (Runtime-specific) — Python: 95%, WASM: 40%, Rust: 10%
```

### 6.5 Deliverables

| Deliverable | File | LOC |
|-------------|------|-----|
| CI workflow | `.github/workflows/conformance.yml` | ~120 |
| CI scripts | `.github/scripts/certify.sh` | ~30 |
| Branch protection config | `.github/branch-protection.json` | ~20 |
| PR comment template | `.github/templates/conformance-report.md` | ~30 |
| **Phase 4 Total** | | **~200** |

---

## 7. Phase 5 — Runtime Certification (Week 6-8)

**Goal:** Automated certification badge system. A runtime that passes
100% of its tier gets a "FLUX Certified" badge. Integration with
fleet-contributing.

**Dependencies:** Phase 4 (CI pipeline), Phase 2 (sufficient vectors)
**Estimated LOC:** ~400 new

### 7.1 Certification Tiers

```
  ┌──────────────────────────────────────────────────────────────┐
  │                 CERTIFICATION TIERS                           │
  │                                                               │
  │  ┌─────────────────────────────────────────────────┐        │
  │  │  FLUX CERTIFIED v2                              │        │
  │  │  Pass ALL 113 v2 conformance vectors             │        │
  │  │  100% pass rate required                          │        │
  │  │  Badge: [![FLUX v2](badge.svg)]                  │        │
  │  └─────────────────────────────────────────────────┘        │
  │                                                               │
  │  ┌─────────────────────────────────────────────────┐        │
  │  │  FLUX CERTIFIED v3                              │        │
  │  │  Pass ALL v2 + ALL v3 vectors                    │        │
  │  │  100% pass rate required                          │        │
  │  │  Badge: [![FLUX v3](badge.svg)]                  │        │
  │  └─────────────────────────────────────────────────┘        │
  │                                                               │
  │  ┌─────────────────────────────────────────────────┐        │
  │  │  FLUX CERTIFIED GOLD                             │        │
  │  │  Pass ALL vectors + ALL benchmarks               │        │
  │  │  Performance within 2x of reference VM            │        │
  │  │  Badge: [![FLUX Gold](badge.svg)]                │        │
  │  └─────────────────────────────────────────────────┘        │
  │                                                               │
  │  ┌─────────────────────────────────────────────────┐        │
  │  │  FLUX COMPLIANT (Tiered)                         │        │
  │  │  P0: 100% required (universal opcodes)           │        │
  │  │  P1: 80% required (canonical opcodes)            │        │
  │  │  P2: 50% required (extended opcodes)             │        │
  │  │  P3: Optional (runtime-specific)                 │        │
  │  │  Badge: [![FLUX P1](badge.svg)]                  │        │
  │  └─────────────────────────────────────────────────┘        │
  └──────────────────────────────────────────────────────────────┘
```

### 7.2 Badge Generation

```python
# src/flux_conformance/certification/badge.py

CERTIFICATION_CONFIGS = {
    "v2": {
        "label": "FLUX v2",
        "required_vectors": "v2",
        "pass_rate_required": 1.0,  # 100%
        "color_pass": "#00cc00",
        "color_fail": "#cc0000",
    },
    "v3": {
        "label": "FLUX v3",
        "required_vectors": "all",
        "pass_rate_required": 1.0,
        "color_pass": "#0066ff",
        "color_fail": "#cc0000",
    },
    "gold": {
        "label": "FLUX Gold",
        "required_vectors": "all",
        "pass_rate_required": 1.0,
        "benchmark_factor": 2.0,  # Within 2x of reference
        "color_pass": "#ffaa00",
        "color_fail": "#cc0000",
    },
}
```

Badge format: SVG with shields.io-compatible layout.

### 7.3 Certification Protocol

```
  flux-conformance certify --runtime ./my-vm --tier v2

  Step 1: Discover runtime capabilities (opcode inventory)
  Step 2: Run ALL v2 vectors against runtime
  Step 3: Check pass rate (must be 100%)
  Step 4: Run performance benchmarks (for Gold tier)
  Step 5: Generate badge + certificate
  Step 6: Write results to conformance-report.json

  Output:
    ✓ FLUX CERTIFIED v2 — 113/113 vectors passed
    ✓ Badge saved to: ./flask-v2-certified.svg
    ✓ Report saved to: ./conformance-report.json
```

### 7.4 Integration with fleet-contributing

```markdown
# In download/fleet-contributing/CONTRIBUTING.md

## Runtime Certification Checklist

Before submitting a new FLUX runtime:

- [ ] Implement the FLUX Conformance Protocol (JSON stdin/stdout)
- [ ] Run `flux-conformance run --runtime ./your-vm --junit results.xml`
- [ ] Achieve at least P0 compliance (7 universal opcodes)
- [ ] Document your opcode coverage in README.md
- [ ] Include conformance results in PR description
- [ ] Target P1 compliance for merge (80%+ canonical opcodes)
```

### 7.5 Certification Database

Maintain a registry of certified runtimes:

```json
{
  "version": "1.0",
  "last_updated": "2026-04-14T00:00:00Z",
  "certifications": [
    {
      "runtime": "python-reference",
      "version": "0.2.0",
      "certification": "v3",
      "pass_rate": 0.969,
      "total_vectors": 181,
      "passed_vectors": 175,
      "failed_vectors": ["conf_get_initial", "conf_set_clamp_low",
                          "conf_set_clamp_high", "conf_mul_chain",
                          "conf_mul_clamp"],
      "benchmarked": false,
      "certified_at": "2026-04-14T00:00:00Z"
    }
  ]
}
```

### 7.6 Deliverables

| Deliverable | File | LOC |
|-------------|------|-----|
| Certification engine | `src/certification/engine.py` | ~200 |
| Badge generator | `src/certification/badge.py` | ~100 |
| Certificate generator | `src/certification/certificate.py` | ~50 |
| Certification DB | `data/certifications.json` | ~50 |
| Fleet-contributing checklist | External repo | ~30 |
| **Phase 5 Total** | | **~430** |

---

## 8. Phase 6 — Performance Benchmarking (Week 8+)

**Goal:** Standard benchmark suite across all runtimes. Generate a
league table of performance metrics. Integrate with fleet index.

**Dependencies:** Phase 3 (multi-runtime harness), Phase 5 (certification)
**Estimated LOC:** ~300 new

### 8.1 Benchmark Categories

```
  ┌──────────────────────────────────────────────────────────────┐
  │              BENCHMARK SUITE (12 categories)                  │
  │                                                               │
  │  Category           Metric              Current (Python)      │
  │  ──────────────────────────────────────────────────          │
  │  NOP loop           ops/sec             ~500K                 │
  │  PUSH+HALT          ops/sec             ~250K                 │
  │  ADD loop           ops/sec             ~200K                 │
  │  MUL loop           ops/sec             ~180K                 │
  │  DIV+MOD loop       ops/sec             ~120K                 │
  │  FADD+FMUL loop     ops/sec             ~100K                 │
  │  AND/OR/XOR/SHL     ops/sec             ~150K                 │
  │  EQ/LT/GT           ops/sec             ~130K                 │
  │  STORE/LOAD loop    ops/sec             ~150K                 │
  │  DUP/SWAP/OVER/ROT  ops/sec             ~250K                 │
  │  CALL/RET loop      ops/sec             ~180K                 │
  │  Startup (1000x)     programs/sec        ~50K                  │
  │                                                               │
  │  Additional (Phase 6):                                        │
  │  Memory throughput  bytes/sec           ~10MB/s               │
  │  Branch prediction  correct%            ~95%                  │
  │  Stack depth        max before error    ~unlimited            │
  │  Code size          bytes per program   ~20 avg               │
  └──────────────────────────────────────────────────────────────┘
```

### 8.2 Cross-Runtime League Table

```bash
flux-conformance benchmark --all --markdown

# Output:
| Runtime | NOP (ops/s) | ADD (ops/s) | MEM (ops/s) | Startup (prog/s) | Total Score |
|---------|-------------|-------------|-------------|-------------------|-------------|
| Rust    | 50,000,000  | 25,000,000  | 20,000,000  | 500,000           | 95,400      |
| C       | 40,000,000  | 20,000,000  | 18,000,000  | 400,000           | 78,400      |
| WASM    | 10,000,000  | 5,000,000   | 4,000,000   | 100,000           | 19,100      |
| Python  | 500,000     | 200,000     | 150,000     | 50,000            | 900         |
| Go      | 8,000,000   | 4,000,000   | 3,000,000   | 80,000            | 15,080      |
```

### 8.3 Benchmark Protocol Extension

Extend the Conformance Protocol to support benchmarks:

```json
// Request
{
  "type": "benchmark",
  "benchmark": "nop_loop",
  "iterations": 100000,
  "warmup": 3
}

// Response
{
  "type": "benchmark_result",
  "benchmark": "nop_loop",
  "total_ops": 100000,
  "total_time_ns": 200000000,
  "ops_per_second": 500000,
  "ns_per_op": 2000
}
```

### 8.4 Fleet Index Integration

Push benchmark results to the fleet index for discovery:

```json
// fleet-work/flux-conformance-benchmarks.json
{
  "timestamp": "2026-04-14T00:00:00Z",
  "benchmarks": {
    "python-reference": {
      "nop_ops_per_sec": 500000,
      "add_ops_per_sec": 200000,
      "startup_prog_per_sec": 50000
    },
    "typescript-wasm": {
      "nop_ops_per_sec": 10000000,
      "add_ops_per_sec": 5000000,
      "startup_prog_per_sec": 100000
    }
  }
}
```

### 8.5 Deliverables

| Deliverable | File | LOC |
|-------------|------|-----|
| Benchmark protocol | `docs/PROTOCOL.md` (extension) | ~50 |
| Cross-runtime benchmark runner | `src/benchmark/runner.py` | ~150 |
| League table generator | `src/benchmark/league.py` | ~100 |
| Fleet index integration | `scripts/push_benchmarks.py` | ~50 |
| **Phase 6 Total** | | **~350** |

---

## 9. Phase 7 — ISA v3 Full Coverage (Month 3+)

**Goal:** Full ISA v3 extension testing. All 256 escape sub-opcodes.
Capability system. Sandbox profiles. Temporal primitives.
Async continuations.

**Dependencies:** ISA v3 spec finalization (ability-transfer repo),
Phases 1-4 (infrastructure), Phase 5 (certification framework)
**Estimated LOC:** ~1,200 new

### 9.1 ISA v3 Extension Spaces

```
  ┌──────────────────────────────────────────────────────────────┐
  │               ISA v3 EXTENSION SPACES                         │
  │                                                               │
  │  0xFF 0x00  Escape Control    10 sub-opcodes                 │
  │  0xFF 0x01  Temporal          16 sub-opcodes                 │
  │  0xFF 0x02  Security          16 sub-opcodes                 │
  │  0xFF 0x03  Async             16 sub-opcodes                 │
  │  0xFF 0x04  Negotiation       16 sub-opcodes                 │
  │  0xFF 0x05  Epistemic         16 sub-opcodes (proposed)      │
  │  0xFF 0x06  Causal            16 sub-opcodes (proposed)      │
  │  0xFF 0x07-0xFE  Reserved     240 sub-opcodes                │
  │  0xFF 0xFF  Meta             16 sub-opcodes                  │
  │  ──────────────────────────────────────────────────          │
  │  TOTAL:  368 potential sub-opcodes                           │
  │  Current coverage: ~28/368 (7.6%)                            │
  └──────────────────────────────────────────────────────────────┘
```

### 9.2 Temporal Primitives — Full Coverage

Current: 8 vectors. Target: 32+ vectors.

```
  Existing (8):
    - fuel_check_default, fuel_set_then_check, fuel_exhausted_halt
    - fuel_decrement_per_check, time_now_monotonic, yield_no_contention
    - yield_with_contention, persist_state

  New (24):
    - fuel_set_zero, fuel_set_max, fuel_check_after_op
    - fuel_check_multiple_vm, deadline_cancel, deadline_nested
    - time_now_resolution, time_now_overflow, sleep_duration
    - sleep_cancel, yield_starvation, yield_priority
    - persist_overwrite, persist_protected_region, persist_restore
    - persist_concurrent_access, persist_size_limit
    - temporal_composition_fuel_deadline, temporal_cancel_propagation
    - fuel_decrement_by_operation, fuel_granularity
    - time_virtual_vs_real, yield_backoff_increasing
```

### 9.3 Security Primitives — Full Coverage

Current: 7 vectors. Target: 40+ vectors.

```
  Existing (7):
    - cap_invoke_denied, cap_invoke_granted, identity_get_consistent
    - sandbox_enter_exit, sandbox_readonly_write_blocked
    - mem_tag_set, fuel_denies_execution

  New (33):
    - cap_invoke_revoked, cap_delegate, cap_revoke_self
    - cap_hierarchy, cap_inherit, cap_exclusive
    - sandbox_stack_overflow, sandbox_memory_boundary
    - sandbox_code_boundary, sandbox_io_restriction
    - sandbox_network_isolation, sandbox_timer_restriction
    - mem_tag_read_check, mem_tag_write_check, mem_tag_clear
    - mem_tag_range, mem_tag_inherit, mem_tag_conflict
    - identity_clone, identity_compare, identity_destroy
    - fuel_global_limit, fuel_per_opcode_limit
    - fuel_replenish, fuel_transfer, fuel_borrow
    - security_composition_sandbox_cap, security_composition_tag_sandbox
    - security_composition_fuel_sandbox, security_edge_cases
```

### 9.4 Async Primitives — Full Coverage

Current: 7 vectors. Target: 32+ vectors.

```
  Existing (7):
    - suspend_saves_state, resume_restores_state, fork_returns_id
    - cancel_valid, cancel_invalid, await_nonblocking, join_nonexistent

  New (25):
    - fork_stack_isolation, fork_memory_isolation, fork_register_isolation
    - resume_after_timeout, resume_multiple_times
    - cancel_running, cancel_self, cancel_cascade
    - await_with_message, await_timeout_expired, await_ordering
    - join_success, join_timeout, join_result
    - context_limit_reached, context_gc
    - async_fork_join_tree, async_pipeline, async_select
    - async_race, async_all, async_timeout_wrapper
    - continuation_serialization, continuation_size_limit
```

### 9.5 Capability System — Full Coverage

```
  New extension space (0xFF 0x05 — proposed in OPCODE-PRIMITIVE-THEORY):
    - believe_set, believe_get, believe_query, believe_contradict
    - doubt_raise, doubt_resolve, doubt_chain, doubt_threshold
    - reconcile_merge, reconcile_conflict, reconcile_prune
    - trust_compute, trust_degrade, trust_restore

  Estimated: ~30 vectors covering epistemic reasoning opcodes
```

### 9.6 Compressed Shorts — Full Coverage

```
  Existing: 8 vectors (basic operations)
  New: ~20 vectors covering:
    - All 16 compressed opcode formats
    - Boundary conditions (imm4 = 0, imm4 = 15)
    - Mixed compressed + standard instructions
    - Compressed instruction alignment
    - Compressed instruction disassembly
```

### 9.7 Deliverables

| Deliverable | LOC |
|-------------|-----|
| Temporal vectors (24 new) | ~300 |
| Security vectors (33 new) | ~400 |
| Async vectors (25 new) | ~300 |
| Compressed shorts vectors (20 new) | ~250 |
| Capability system vectors (30 new) | ~350 |
| Negotiation extension vectors (10 new) | ~100 |
| FluxVMv3 updates for new opcodes | ~400 |
| **Phase 7 Total** | **~2,100** |

---

## 10. Integration with datum-runtime

**Goal:** Make flux-conformance a callable library that datum-runtime
invokes via `datum-rt conformance run`.

### 10.1 Integration Architecture

```
  ┌──────────────────────────────────────────────────────────────────┐
  │                datum-runtime ↔ flux-conformance                   │
  │                                                                    │
  │  datum-rt conformance run --runtime ./my-vm                       │
  │       │                                                            │
  │       ▼                                                            │
  │  datum_runtime/superagent/datum.py                                │
  │  └─→ datum.conformance.run(runtime_path)                          │
  │       │                                                            │
  │       ▼                                                            │
  │  flux_conformance (pip-installed library)                         │
  │  └─→ ConformanceRunner.run_all()                                  │
  │       │                                                            │
  │       ▼                                                            │
  │  Results → datum journal entry + MiB to oracle1                   │
  │                                                                    │
  │  datum-rt conformance certify --runtime ./my-vm --tier v2         │
  │       │                                                            │
  │       ▼                                                            │
  │  CertificationEngine.certify()                                     │
  │       │                                                            │
  │       ▼                                                            │
  │  Badge + Report → fleet-contributing PR                            │
  └──────────────────────────────────────────────────────────────────┘
```

### 10.2 datum-runtime CLI Extension

Add a `conformance` command group to datum-runtime:

```python
# In datum_runtime/cli.py

@main.group()
def conformance():
    """FLUX conformance testing and certification."""
    pass

@conformance.command()
@click.option("--runtime", "-r", required=True, help="Path to runtime binary")
@click.option("--tier", "-t", default="P0", help="Certification tier")
@click.option("--output", "-o", default=None, help="Output file")
def run(runtime: str, tier: str, output: Optional[str]):
    """Run conformance tests against a FLUX runtime."""
    from flux_conformance import ConformanceRunner, SubprocessEngine
    runner = ConformanceRunner()
    runner.add_engine(SubprocessEngine(cmd=[runtime]))
    results = runner.run_all(tier_filter=tier)
    # Format and display...

@conformance.command()
@click.option("--runtime", "-r", required=True, help="Path to runtime binary")
@click.option("--tier", "-t", default="v2", help="Certification level")
def certify(runtime: str, tier: str):
    """Certify a FLUX runtime."""
    from flux_conformance.certification import CertificationEngine
    engine = CertificationEngine()
    result = engine.certify(runtime_path=runtime, tier=tier)
    if result.passed:
        console.print(f"[bold green]FLUX CERTIFIED {tier.upper()}[/]")
    else:
        console.print(f"[bold red]NOT CERTIFIED[/]")
        console.print(f"  Passed: {result.passed_vectors}/{result.total_vectors}")
```

### 10.3 pyproject.toml Dependency

```toml
# In datum/pyproject.toml
[project]
dependencies = [
    # ... existing deps ...
    "flux-conformance>=0.2.0",
]

[project.optional-dependencies]
conformance = [
    "flux-conformance>=0.2.0",
]
```

### 10.4 Integration Points

| datum-runtime command | flux-conformance call |
|---------------------|----------------------|
| `datum-rt conformance run` | `ConformanceRunner.run_all()` |
| `datum-rt conformance certify` | `CertificationEngine.certify()` |
| `datum-rt conformance list` | `VectorLoader.list_all()` |
| `datum-rt conformance export` | `VectorLoader.export_json()` |
| `datum-rt audit --type conformance` | `FluxUniversalValidator.validate()` |
| `datum-rt benchmark` | `FluxBenchmark.run_all()` |

### 10.5 Deliverables

| Deliverable | File | LOC |
|-------------|------|-----|
| CLI conformance group | `datum_runtime/cli.py` (extension) | ~80 |
| Conformance integration module | `datum_runtime/conformance.py` | ~100 |
| pyproject.toml update | `datum/pyproject.toml` | ~5 |
| **Integration Total** | | **~185** |

---

## 11. Dependencies and Fleet Coordination

### 11.1 Repo Dependency Map

```
  ┌──────────────────────────────────────────────────────────────┐
  │                 REPO DEPENDENCY MAP                          │
  │                                                               │
  │  flux-conformance (THIS REPO)                                │
  │  │                                                            │
  │  ├── depends on ──→ flux-spec (ISA v2/v3 specification)      │
  │  │                 └── isa-v3-draft.md (829 LOC)              │
  │  │                                                            │
  │  ├── tested against ──→ flux-wasm (TypeScript VM)            │
  │  │                     └── src/vm.ts (2,209 LOC)             │
  │  │                                                            │
  │  ├── tested against ──→ flux/crates (Rust VM)               │
  │  │                     └── 103 opcodes, 54 dispatched        │
  │  │                                                            │
  │  ├── tested against ──→ flux-os (C VM)                       │
  │  │                     └── 184 opcodes, 58 dispatched        │
  │  │                                                            │
  │  ├── tested against ──→ flux-swarm (Go VM)                  │
  │  │                     └── 14 opcodes                        │
  │  │                                                            │
  │  ├── integrated into ──→ datum-runtime (Datum's CLI)        │
  │  │                     └── datum_runtime/cli.py              │
  │  │                                                            │
  │  ├── coordinated with ──→ ability-transfer (ISA v3 spec)     │
  │  │                        └── rounds/03-isa-v3-draft/        │
  │  │                                                            │
  │  └── coordinated with ──→ fleet-contributing (checklists)    │
  │                         └── CONTRIBUTING.md                  │
  │                                                               │
  │  External:                                                    │
  │  ├── oracle1-vessel-session3/ (cross-runtime vectors)         │
  │  └── fleet-work/ (benchmark data, fleet index)               │
  └──────────────────────────────────────────────────────────────┘
```

### 11.2 Fleet Agent Coordination

| Agent | Role | Phase |
|-------|------|-------|
| **Datum** (us) | Build and maintain flux-conformance | All phases |
| **Oracle1** | ISA specification decisions, fleet coordination | Phase 2, 7 |
| **JetsonClaw1** | Cross-runtime runner development, vector authoring | Phase 1, 3 |
| **Any runtime dev** | Implement conformance protocol adapter | Phase 3+ |
| **Navigator** | Fleet index integration, discovery | Phase 4, 6 |

### 11.3 External Dependencies

```
  Phase 1: None (self-contained)
  Phase 2: ISA v3 spec clarification (CONF subsystem)
           → Coordinate with Oracle1 via MiB
  Phase 3: flux-wasm adapter (JetsonClaw1 or community)
           Rust/C/Go adapters (respective runtime maintainers)
  Phase 4: GitHub Actions (infrastructure)
  Phase 5: fleet-contributing update (Navigator or Oracle1)
  Phase 6: All runtime adapters
  Phase 7: ISA v3 spec finalization (ability-transfer, Oracle1)
```

### 11.4 Blocking Issues

| Issue | Blocks | Resolution |
|-------|--------|------------|
| CONF subsystem spec ambiguity | Phase 2 confidence vectors | Define in ISA v3 spec |
| No canonical opcode encoding agreed | Phase 3 cross-runtime tests | Define in flux-spec |
| flux-wasm has no conformance adapter | Phase 3 WASM testing | JetsonClaw1 to build |
| Rust VM only 54/103 opcodes | Phase 3 Rust testing | Rust runtime team |
| Go VM only 14 opcodes | Phase 3 Go testing | Go runtime team |

---

## 12. Risk Register

| Risk | Probability | Impact | Mitigation |
|------|-------------|--------|------------|
| ISA v3 spec keeps changing | HIGH | HIGH | Version-lock vectors to spec commits |
| Runtime teams don't build adapters | MEDIUM | HIGH | Provide adapter templates, make it trivial |
| CONF ambiguity never resolved | MEDIUM | LOW | Mark confidence vectors as "optional" tier |
| Vector explosion (>1000 unmanageable) | LOW | MEDIUM | Strict authoring guidelines, automated dedup |
| Performance benchmarks non-reproducible | MEDIUM | MEDIUM | Fixed iteration counts, median-of-5, pinned hardware |
| GitHub Actions rate limits | LOW | LOW | Cache dependencies, limit matrix size |
| datum-runtime integration breaks | LOW | MEDIUM | Version pin flux-conformance dependency |

---

## 13. Success Metrics

### 13.1 Quantitative Targets

| Metric | Current | Phase 1 | Phase 3 | Phase 5 | Phase 7 |
|--------|---------|---------|---------|---------|---------|
| Total vectors | 181 | 250 | 300 | 350 | 500+ |
| Unique opcodes tested | 41 | 50 | 55 | 60 | 80+ |
| Runtimes with adapters | 1 (Python) | 1 | 3-5 | 3-5 | 5+ |
| P0 pass rate (all runtimes) | 100% | 100% | 100% | 100% | 100% |
| P1 pass rate (Python) | ~95% | 97% | 98% | 99% | 99%+ |
| P1 pass rate (WASM) | ~60% | 65% | 65% | 70% | 80%+ |
| CI pipeline | None | None | Manual | Automated | Automated |
| Certified runtimes | 0 | 0 | 0 | 1+ | 3+ |
| Benchmark league table | None | None | None | None | 3+ runtimes |

### 13.2 Qualitative Targets

- **One command to test any runtime:** `flux-conformance run --runtime <path>`
- **One command to certify:** `flux-conformance certify --runtime <path>`
- **Spec-traceable:** Every vector links to an ISA specification section
- **Community-contributed:** Runtime maintainers can add their own vectors via PR
- **Self-documenting:** `flux-conformance list` shows all vectors with descriptions

### 13.3 Fleet Impact

```
  BEFORE flux-conformance roadmap:
    "Does my runtime implement FLUX correctly?"
    → Nobody knows. Each runtime has its own tests.
    → Bytecode is not portable between runtimes.
    → 93% of the ISA is untested across runtimes.

  AFTER Phase 5:
    "Does my runtime implement FLUX correctly?"
    → flux-conformance certify --runtime ./my-vm
    → ✓ FLUX CERTIFIED v2 — 113/113 vectors passed
    → Binary answer. Reproducible. Trustworthy.
```

---

## Appendix A: Phase Timeline Summary

```
  Week 1        Phase 1: Consolidate
                 ├── Merge 3 runners into 1
                 ├── Unified vector schema
                 ├── Package restructure
                 └── 250 unique vectors

  Week 2        Phase 2: Cover the Gaps
                 ├── 42 CONF-002 edge cases
                 ├── ~50 gap coverage vectors
                 ├── Vector authoring tools
                 └── 300+ total vectors

  Week 3-4      Phase 3: Multi-Runtime Harness
                 ├── Conformance protocol spec
                 ├── WASM adapter (Priority 1)
                 ├── Rust adapter (Priority 2)
                 ├── C/Go adapters (Priority 3-4)
                 └── Opcode translation layer

  Week 5        Phase 4: CI/CD Integration
                 ├── GitHub Actions workflow
                 ├── Test matrix (Python, Node, Rust)
                 ├── P0 conformance gate
                 └── Automated reporting

  Week 6-8      Phase 5: Runtime Certification
                 ├── Certification tiers (P0-P3)
                 ├── Badge generation
                 ├── Certificate system
                 └── fleet-contributing integration

  Week 8+       Phase 6: Performance Benchmarking
                 ├── Cross-runtime benchmarks
                 ├── League table
                 └── Fleet index integration

  Month 3+      Phase 7: ISA v3 Full Coverage
                 ├── 256 escape sub-opcodes
                 ├── Temporal, Security, Async full coverage
                 ├── Capability system vectors
                 └── 500+ total vectors
```

## Appendix B: LOC Budget Summary

| Phase | New LOC | Modified LOC | Dependencies |
|-------|---------|--------------|--------------|
| Phase 1 | ~1,530 | ~500 (restructure) | None |
| Phase 2 | ~1,500 | ~200 | Phase 1 |
| Phase 3 | ~670 | ~100 | Phase 1, 2 |
| Phase 4 | ~200 | ~50 | Phase 3 |
| Phase 5 | ~430 | ~50 | Phase 4 |
| Phase 6 | ~350 | ~100 | Phase 3, 5 |
| Phase 7 | ~2,100 | ~400 | Phase 1-5, ISA v3 spec |
| datum-runtime integration | ~185 | ~80 | Phase 1, 5 |
| **TOTAL** | **~6,965** | **~1,480** | |

## Appendix C: Key File Reference

```
  # Core (existing)
  flux-conformance/conformance_core.py         1,249 LOC  — FluxVM, FluxFlags, 113 vectors
  flux-conformance/canonical_opcode_shim.py      383 LOC  — Cross-runtime opcode mapping
  flux-conformance/flux_universal_validator.py    553 LOC  — Bytecode validation
  flux-conformance/benchmark_flux.py              499 LOC  — Performance benchmarks

  # Runners (existing, to be merged)
  flux-conformance/run_conformance.py             519 LOC  — V2 runner
  flux-conformance/run_v3_conformance.py          276 LOC  — V3 runner
  oracle1/.../unified_runner.py                   758 LOC  — Register VM runner

  # External runtimes
  download/flux-wasm/src/vm.ts                 2,209 LOC  — TypeScript VM
  oracle1/.../cross_runtime_runner.py            369 LOC  — Cross-runtime runner

  # Specs
  ability-transfer/rounds/03-isa-v3-draft/isa-v3-draft.md  829 LOC

  # Vectors
  flux-conformance/conformance-vectors.json              113 v2 vectors
  flux-conformance/conformance-vectors-v3.json             68 v3 vectors
  oracle1/.../vectors/vectors/*.json                       88 register vectors
  oracle1/.../vectors/unified/*.json                       29 unified vectors
```

---

*Datum — Fleet Quartermaster — flux-conformance roadmap v1.0*
*This roadmap is a living document. Update as phases complete and
fleet priorities evolve. Coordinate with Oracle1 for ISA decisions
and JetsonClaw1 for cross-runtime implementation.*
