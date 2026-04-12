# Cross-Runtime Conformance Report

**Generated:** 2026-04-12 02:07:09 UTC
**Python runtime:** CPython (FluxMiniVM)
**Go test file:** `/home/z/my-project/repos/flux-conformance/cross_runtime/flux_vm_test.go`

## Summary

| Metric | Value |
|--------|-------|
| Total vectors | 33 |
| Executed | 32 |
| Skipped | 1 |
| **Passed** | **32** |
| **Failed** | **0** |
| Pass rate | 100% |

## Results by Category

| Category | Total | Passed | Failed | Skipped |
|----------|-------|--------|--------|---------|
| arithmetic | 8 | 8 | 0 | 0 |
| branch | 6 | 6 | 0 | 0 |
| comparison | 4 | 4 | 0 | 0 |
| composite | 3 | 3 | 0 | 0 |
| edge | 4 | 3 | 0 | 1 |
| logic | 4 | 4 | 0 | 0 |
| stack | 1 | 1 | 0 | 0 |
| system | 3 | 3 | 0 | 0 |

## Detailed Results

| # | Name | Category | Python | Details |
|---|------|----------|--------|---------|
| 1 | `system-halt` | system | PASS | 3 us, 1 insns |
| 2 | `system-nop` | system | PASS | 5 us, 4 insns |
| 3 | `system-ret-empty` | system | PASS | 1 us, 1 insns |
| 4 | `arith-add-10-plus-20` | arithmetic | PASS | 8 us, 4 insns |
| 5 | `arith-sub-50-minus-17` | arithmetic | PASS | 17 us, 4 insns |
| 6 | `arith-mul-6-times-7` | arithmetic | PASS | 3 us, 4 insns |
| 7 | `arith-div-100-by-4` | arithmetic | PASS | 4 us, 4 insns |
| 8 | `arith-mod-17-by-5` | arithmetic | PASS | 3 us, 4 insns |
| 9 | `arith-inc` | arithmetic | PASS | 2 us, 3 insns |
| 10 | `arith-dec` | arithmetic | PASS | 2 us, 3 insns |
| 11 | `arith-neg` | arithmetic | PASS | 3 us, 3 insns |
| 12 | `logic-and-15-and-3` | logic | PASS | 3 us, 4 insns |
| 13 | `logic-or-15-or-3` | logic | PASS | 2 us, 4 insns |
| 14 | `logic-xor-15-xor-3` | logic | PASS | 2 us, 4 insns |
| 15 | `logic-not-0` | logic | PASS | 2 us, 3 insns |
| 16 | `cmp-eq-equal` | comparison | PASS | 3 us, 4 insns |
| 17 | `cmp-lt-3-less-than-5` | comparison | PASS | 3 us, 4 insns |
| 18 | `cmp-gt-3-not-greater-5` | comparison | PASS | 3 us, 4 insns |
| 19 | `cmp-ne-3-not-equal-5` | comparison | PASS | 2 us, 4 insns |
| 20 | `branch-jmp-skip-dec` | branch | PASS | 2 us, 3 insns |
| 21 | `branch-jz-taken` | branch | PASS | 2 us, 3 insns |
| 22 | `branch-jz-not-taken` | branch | PASS | 2 us, 4 insns |
| 23 | `branch-jnz-taken` | branch | PASS | 2 us, 3 insns |
| 24 | `branch-jnz-not-taken` | branch | PASS | 2 us, 4 insns |
| 25 | `branch-call-ret` | branch | PASS | 4 us, 5 insns |
| 26 | `stack-push-pop-roundtrip` | stack | PASS | 3 us, 5 insns |
| 27 | `edge-div-zero` | edge | PASS | 2 us, 3 insns |
| 28 | `edge-r0-immutable` | edge | PASS | 2 us, 4 insns |
| 29 | `edge-end-of-bytecode` | edge | PASS | 1 us, 1 insns |
| 30 | `edge-cycle-limit` | edge | SKIP | slow test |
| 31 | `composite-countdown-5-to-0` | composite | PASS | 11 us, 18 insns |
| 32 | `composite-sum-1-to-5` | composite | PASS | 18 us, 28 insns |
| 33 | `composite-nested-add` | composite | PASS | 5 us, 9 insns |

## Go Runtime Testing

To run the cross-runtime tests on the Go VM:

```bash
# Copy the generated test file to your Go module
cp /home/z/my-project/repos/flux-conformance/cross_runtime/flux_vm_test.go <go-module-root>/pkg/vm/flux_vm_test.go

# Run the tests
cd <go-module-root> && go test -v -run TestCrossRuntime ./pkg/vm/
```

The Go VM must implement the following interface:

```go
type VM interface {
    New() VM
    Load(code []byte)
    Run()
    Halted() bool
    Error() bool
    GetReg(idx int) int32
    SetReg(idx int, val int)
}
```
