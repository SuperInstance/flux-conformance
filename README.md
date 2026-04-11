# flux-conformance

**Cross-runtime conformance test suite for FLUX.** Ensures all FLUX implementations produce identical results for the same inputs.

## Purpose

The FLUX ecosystem has three implementations (C, Rust, Python) with divergent ISAs. This repo provides the authoritative test vectors that all implementations must pass to be considered FLUX-conformant.

## Test Vector Format

```json
{
  "name": "arithmetic-add",
  "description": "Test integer addition: R0 = 3 + 4",
  "bytecode": "10002003100104002100080000",
  "expected": {
    "final_state": "HALTED",
    "R0": 7,
    "R1": 4,
    "cycle_count": 3,
    "flags": 0
  }
}
```

## Test Categories

1. **Arithmetic** — IADD, ISUB, IMUL, IDIV, IMOD, INEG, IABS, INC, DEC
2. **Float** — FADD, FSUB, FMUL, FDIV, FNEG, F2I, I2F
3. **Logic** — IAND, IOR, IXOR, INOT, ISHL, ISHR
4. **Comparison** — CMP, CMPI, FCMP, TEST
5. **Branch** — JMP, JZ, JNZ, JE, JNE, JG, JL, JGE, JLE, LOOP
6. **Stack** — PUSH, POP, DUP, SWAP, ENTER, LEAVE, PUSHA, POPA
7. **Memory** — LOAD, STORE, LEA, LOAD8/16/32, STORE8/16/32
8. **Call** — CALL, RET, CALLI, TAILCALL
9. **A2A** — TELL, ASK, DELEGATE, REPLY, BROADCAST, SPAWN
10. **Regions** — REGION_CREATE, REGION_DESTROY, LOAD_RM, STORE_RM
11. **FLUX** — TILE_LOAD, TILE_COMPOSE, TILE_EXEC, ADAPT, EVOLVE
12. **Edge cases** — division by zero, stack overflow, invalid opcode, PC out of bounds

## Runners

- `runners/python/` — Test runner for flux-runtime
- `runners/rust/` — Test runner for flux (Rust)
- `runners/c/` — Test runner for flux-os

## Status

- [ ] Test vector format specification
- [ ] Arithmetic test vectors (30+)
- [ ] Control flow test vectors (20+)
- [ ] Memory test vectors (15+)
- [ ] A2A protocol test vectors (10+)
- [ ] Python runner
- [ ] Rust runner
- [ ] C runner

## Related

- [flux-spec](https://github.com/SuperInstance/flux-spec) — canonical ISA (defines what tests must verify)
- [flux-os](https://github.com/SuperInstance/flux-os) — C implementation
- [flux](https://github.com/SuperInstance/flux) — Rust implementation
- [flux-runtime](https://github.com/SuperInstance/flux-runtime) — Python implementation

## License

MIT
