# Changelog

All notable changes to the FLUX Conformance Test Suite are documented in this file. The format follows [Keep a Changelog](https://keepachangelog.com/) and this project adheres to [Semantic Versioning](https://semver.org/).

## [2.0.0] - 2026-04-13

### Added
- **Benchmark framework** (`benchmark_flux.py`): Comprehensive performance benchmarking harness (PERF-001) with 12 benchmark categories covering decode, arithmetic, float, logic, comparison, memory, stack, control flow, confidence, agent-to-agent, complex programs, and startup cost.
- **Unified runner** (`run_conformance.py`): Cross-runtime conformance runner (CONF-001) with auto-discovery of installed runtimes, category filtering, and JSON/Markdown/terminal output formats.
- **Test vector JSON export**: `conformance-vectors.json` with all 113 v2 test vectors in portable JSON format for cross-language consumption.
- **SubprocessRuntime adapter**: Generic adapter pattern for testing non-Python runtimes via JSON-over-stdin/stdout protocol.
- **RuntimeResult and RuntimeSummary** data classes for structured cross-runtime comparison.
- **v3 backward compatibility tests**: 5 tests verifying all v2 programs produce identical results on the v3 VM.
- **Expanded documentation**: README.md, ARCHITECTURE.md, CONTRIBUTING.md, CROSS-RUNTIME-RESULTS.md.

### Changed
- Expanded Quick Start with detailed installation and usage instructions.
- Added badge section to README with tests, coverage, version, and ISA v3 status indicators.
- Modularized test file structure with dedicated v2 and v3 test files.

## [1.3.0] - 2026-04-10

### Added
- **Universal bytecode validator**: Validation logic for checking bytecode structural integrity before execution (correct operand sizes, valid opcode ranges).
- **Expanded edge-case vectors**: 15 new edge-case test vectors covering boundary conditions:
  - `arith_add_large` — million-scale addition
  - `arith_mul_large` — thousand-scale multiplication
  - `complex_range_check` — compound comparison
  - `complex_gt_check` — comparison with flag verification
  - `complex_bitmask` — 16-bit masking
  - `complex_power_of_2` — shift-based exponentiation
  - `complex_div_mod` — combined division and modulo
  - `complex_rotate_left` — bit rotation emulation
  - `complex_abs_pos` — absolute value of positive number
- **Stack-preserving HALT test** (`sys_halt_preserves_stack`): Verifies that HALT does not modify a pre-loaded stack.
- **Multiple confidence chain tests**: `conf_mul_chain` testing sequential multiplication with clamping.
- **A2A channel isolation tests**: `a2a_separate_channels` and `a2a_empty_after_listen` testing independent channel behavior.

### Changed
- Increased total v2 test vector count from 100 to 113.
- Updated `conformance-vectors.json` export with new vectors.

## [1.2.0] - 2026-04-07

### Added
- **Cross-runtime audit results** (CONF-002): Comprehensive analysis of opcode portability across 8 target runtimes (Python, Rust, C, Go, TypeScript/WASM, Zig, Java, CUDA).
- **Canonical opcode translation shim** (`canonical_opcode_shim.py`): Compatibility layer mapping between runtime-specific opcode encodings and the canonical FLUX ISA encoding.
- **Portability classification system**: Four-tier system (P0–P3) categorizing opcodes by cross-runtime implementation difficulty.
- **7 universally portable opcodes identified**: HALT, NOP, PUSH, POP, ADD, SUB, MUL.
- **42 recommended new edge-case vectors**: Specific suggestions for improving test coverage based on cross-runtime failure analysis.

### Changed
- Updated `ConformanceTestSuite` with improved comparison logic for float epsilon tolerance.
- Added `allow_float_epsilon` field to `ConformanceTestCase` dataclass.

## [1.1.0] - 2026-04-04

### Added
- **ISA v3 extension conformance vectors**: 62 new test vectors covering three extension primitive classes:
  - **Temporal primitives** (EXT 0x01): 8 tests for `FUEL_CHECK`, `DEADLINE_BEFORE`, `YIELD_IF_CONTENTION`, `PERSIST_CRITICAL_STATE`, `TIME_NOW`, `SLEEP_UNTIL`.
  - **Security primitives** (EXT 0x02): 7 tests for `CAP_INVOKE`, `MEM_TAG`, `SANDBOX_ENTER`/`SANDBOX_EXIT`, `FUEL_SET`, `IDENTITY_GET`.
  - **Async primitives** (EXT 0x03): 6 tests for `SUSPEND`, `RESUME`, `FORK`, `JOIN`, `CANCEL`, `AWAIT_CHANNEL`.
  - **Extension discovery** (EXT 0x00): 2 tests for `PROBE` and unsupported extension error handling.
- **FluxVMv3 reference implementation**: Extended VM with temporal state (simulated clock, fuel budget), security state (capability sets, sandbox stack, memory tags), and async state (continuations, context map).
- **Escape prefix encoding**: `0xFF` + extension_id + sub_opcode + payload format.
- **Security error codes**: `CAPABILITY_DENIED` (0xE0), `SANDBOX_VIOLATION` (0xE1), `FUEL_EXHAUSTED` (0xE2), `TAG_MISMATCH` (0xE3), `EXTENSION_NOT_SUPPORTED` (0xE4), `INVALID_CAPABILITY` (0xE5).
- **v3 test file**: `test_conformance_v3.py` with dedicated pytest test classes.

### Changed
- Base `FluxVM._step()` is now overridable in `FluxVMv3` with pre-dispatch sandbox checking.

## [1.0.0] - 2026-04-01

### Added
- **Initial conformance test suite** with 116 test vectors (subsequently refined to 113 after removing 3 duplicates).
- **Reference VM** (`FluxVM`): Complete implementation of the FLUX ISA v2 specification with 37 opcodes across 7 encoding formats (A–G).
- **Flags register** (`FluxFlags`): 4-bit condition code register (Z, S, C, O) with arithmetic and logic update rules.
- **Test case data structure** (`ConformanceTestCase`): Dataclass with bytecode hex, initial/expected stack, expected flags, float epsilon tolerance, and description.
- **Test runner** (`ConformanceTestSuite`): Suite manager with `run_single()`, `run_all()`, and `summary()` methods.
- **11 test categories**: System Control, Integer Arithmetic, Comparison, Logic/Bitwise, Memory, Control Flow, Stack Manipulation, Float Operations, Confidence, Agent-to-Agent, Complex/Mixed.
- **Pytest integration** (`test_conformance.py`): Parametrized tests for all vectors plus manual category-level test classes.
- **Bytecode helper functions**: `push_imm32`, `jmp_addr`, `jz_addr`, `jnz_addr`, `call_addr`, `store_addr`, `load_addr`, `signal_ch`, `broadcast_ch`, `listen_ch`.
- **Project configuration** (`pyproject.toml`): setuptools build system, pytest configuration, dev dependencies.
- **Encoding format documentation**: Tables for all 7 instruction encoding formats.

---

## Version Summary

| Version | Date | Vectors | Key Milestone |
|---------|------|---------|---------------|
| 2.0.0 | 2026-04-13 | 113 v2 + 62 v3 | Benchmark framework, unified runner |
| 1.3.0 | 2026-04-10 | 113 v2 | Universal bytecode validator, edge cases |
| 1.2.0 | 2026-04-07 | 113 v2 | Cross-runtime audit, canonical shims |
| 1.1.0 | 2026-04-04 | 113 v2 + 62 v3 | ISA v3 extension vectors |
| 1.0.0 | 2026-04-01 | 113 v2 | Initial conformance suite |
