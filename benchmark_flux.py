#!/usr/bin/env python3
"""
FLUX Runtime Performance Benchmark Harness (PERF-001)

Benchmarks FLUX VM implementations across multiple dimensions:
- Instruction decode speed (ops/second)
- Execution throughput per opcode category
- Memory operation latency
- Control flow overhead
- Stack manipulation throughput
- Program startup cost

Outputs results as JSON and/or Markdown tables suitable for
cross-runtime comparison.

Usage:
    python benchmark_flux.py              # Run all benchmarks, terminal output
    python benchmark_flux.py --json       # Output as JSON
    python benchmark_flux.py --markdown   # Output as Markdown table
    python benchmark_flux.py --category arith  # Benchmark specific category
    python benchmark_flux.py --iterations 10000  # Control iteration count

Designed for integration with flux-conformance cross-runtime runner.
"""

import argparse
import json
import os
import struct
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from typing import Dict, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conformance_core import (
    FluxVM, HALT, NOP, ADD, SUB, MUL, DIV, MOD, NEG, INC, DEC,
    EQ, NE, LT, LE, GT, GE, AND, OR, XOR, NOT, SHL, SHR,
    LOAD, STORE, PEEK, POKE, JMP, JZ, JNZ, CALL, RET, PUSH, POP,
    DUP, SWAP, OVER, ROT, FADD, FSUB, FMUL, FDIV,
    CONF_GET, CONF_SET, CONF_MUL, SIGNAL, BROADCAST, LISTEN,
    FLAG_Z,
)

# ─── Bytecode helpers ────────────────────────────────────────────────────────

def push_imm32(value: int) -> bytes:
    return bytes([PUSH]) + struct.pack("<i", value)

def jmp_addr(addr: int) -> bytes:
    return bytes([JMP]) + struct.pack("<H", addr)

def jnz_addr(addr: int) -> bytes:
    return bytes([JNZ]) + struct.pack("<H", addr)

def jz_addr(addr: int) -> bytes:
    return bytes([JZ]) + struct.pack("<H", addr)

def call_addr(addr: int) -> bytes:
    return bytes([CALL]) + struct.pack("<H", addr)

def store_addr(addr: int) -> bytes:
    return bytes([STORE]) + struct.pack("<H", addr)

def load_addr(addr: int) -> bytes:
    return bytes([LOAD]) + struct.pack("<H", addr)


# ─── Benchmark Programs ─────────────────────────────────────────────────────

def bench_nop_loop(n: int) -> bytes:
    """NOP loop: measures raw instruction decode speed."""
    # PUSH n, loop: DEC, JNZ to DEC
    # Layout: PUSH_n(0-4), DEC(5), JNZ(6-8)->5, HALT(9)
    return push_imm32(n) + bytes([DEC]) + jnz_addr(5) + bytes([HALT])

def bench_add_loop(n: int) -> bytes:
    """ADD loop: PUSH 0, PUSH 1, ADD (n times), HALT."""
    # PUSH 0, PUSH 1, loop: ADD, PUSH 1, ADD, DEC counter, JNZ
    # Simpler: accumulate 1 n times starting from 0
    # PUSH 0, PUSH n, DEC, DUP, JZ done, POP, PUSH 1, ADD, JMP loop
    # Layout:
    #   0-4:   PUSH 0      (accumulator)
    #   5-9:   PUSH n      (counter)
    #   10:    DUP
    #   11-13: JZ 17       (if counter == 0, jump to HALT)
    #   14:    POP         (remove counter copy)
    #   15-19: PUSH 1
    #   20:    ADD         (accumulator += 1)
    #   21:    DEC         (counter--)
    #   22-24: JNZ 10      (back to DUP)
    #   25:    HALT
    return push_imm32(0) + push_imm32(n) + bytes([DUP]) + jz_addr(25) + bytes([POP]) + push_imm32(1) + bytes([ADD, DEC]) + jnz_addr(10) + bytes([HALT])

def bench_mul_loop(n: int) -> bytes:
    """MUL loop: multiply by 2, n times."""
    # PUSH 1, PUSH n, DUP, JZ done, POP, PUSH 2, MUL, DEC, JNZ loop
    return push_imm32(1) + push_imm32(n) + bytes([DUP]) + jz_addr(25) + bytes([POP]) + push_imm32(2) + bytes([MUL, DEC]) + jnz_addr(10) + bytes([HALT])

def bench_div_mod_loop(n: int) -> bytes:
    """DIV+MOD loop: divide by 2 and add remainder."""
    # PUSH 1000000, PUSH n, DUP, JZ done, POP, DUP, PUSH 2, DIV, PUSH 2, MOD, ADD, SWAP, DEC, JNZ loop
    # Layout:
    #   0-4:   PUSH 1000000
    #   5-9:   PUSH n
    #   10:    DUP
    #   11-13: JZ 30       (done)
    #   14:    POP
    #   15:    DUP         (copy accumulator for div)
    #   16-20: PUSH 2
    #   21:    DIV
    #   22-26: PUSH 2      (reload 2 for mod)
    #   27:    MOD         (get remainder)
    #   28:    ADD         (add remainder)
    #   29:    DEC         (counter--)
    #   30-32: JNZ 10
    #   33:    HALT
    # Wait this is wrong - I need to swap properly. Let me simplify.
    # Simpler: PUSH n, loop: PUSH 100, PUSH 7, DIV, PUSH 100, PUSH 7, MOD, DEC, JNZ
    return push_imm32(n) + bytes([DUP]) + jz_addr(20) + bytes([POP]) + push_imm32(100) + push_imm32(7) + bytes([DIV]) + push_imm32(100) + push_imm32(7) + bytes([MOD]) + bytes([DEC]) + jnz_addr(10) + bytes([HALT])

def bench_float_loop(n: int) -> bytes:
    """Float arithmetic loop: FADD + FMUL."""
    # PUSH 1.0 (as int, will be cast), PUSH n, DUP, JZ done, POP, PUSH 1, FADD, PUSH 2, FMUL, DEC, JNZ
    return push_imm32(1) + push_imm32(n) + bytes([DUP]) + jz_addr(28) + bytes([POP]) + push_imm32(1) + bytes([FADD]) + push_imm32(2) + bytes([FMUL]) + bytes([DEC]) + jnz_addr(10) + bytes([HALT])

def bench_logic_loop(n: int) -> bytes:
    """Bitwise operations loop: AND, OR, XOR, SHL."""
    return push_imm32(0xFF) + push_imm32(n) + bytes([DUP]) + jz_addr(34) + bytes([POP]) + push_imm32(0x0F) + bytes([AND]) + push_imm32(0xF0) + bytes([OR]) + push_imm32(0xFF) + bytes([XOR]) + push_imm32(1) + bytes([SHL]) + bytes([DEC]) + jnz_addr(10) + bytes([HALT])

def bench_comparison_loop(n: int) -> bytes:
    """Comparison operations loop."""
    return push_imm32(0) + push_imm32(n) + bytes([DUP]) + jz_addr(30) + bytes([POP]) + push_imm32(42) + push_imm32(7) + bytes([EQ]) + push_imm32(3) + push_imm32(5) + bytes([LT]) + push_imm32(10) + push_imm32(20) + bytes([GT]) + bytes([DEC]) + jnz_addr(10) + bytes([HALT])

def bench_mem_store_load_loop(n: int) -> bytes:
    """Memory store/load roundtrip loop."""
    # PUSH 0, PUSH n, DUP, JZ done, POP, PUSH counter, STORE 100, LOAD 100, DEC, JNZ
    return push_imm32(0) + push_imm32(n) + bytes([DUP]) + jz_addr(20) + bytes([POP]) + store_addr(100) + load_addr(100) + bytes([DEC]) + jnz_addr(10) + bytes([HALT])

def bench_mem_peek_poke_loop(n: int) -> bytes:
    """Memory POKE/PEEK roundtrip loop."""
    return push_imm32(0) + push_imm32(n) + bytes([DUP]) + jz_addr(25) + bytes([POP]) + push_imm32(200) + push_imm32(42) + bytes([POKE]) + push_imm32(200) + bytes([PEEK]) + bytes([DEC]) + jnz_addr(10) + bytes([HALT])

def bench_stack_manip_loop(n: int) -> bytes:
    """Stack manipulation loop: DUP, SWAP, OVER, ROT."""
    # Keep 3 items on stack, do DUP/SWAP/OVER/ROT then clean up
    return push_imm32(1) + push_imm32(2) + push_imm32(3) + push_imm32(n) + bytes([DUP]) + jz_addr(28) + bytes([POP]) + bytes([DUP, SWAP, OVER, ROT]) + bytes([POP]) + bytes([DEC]) + jnz_addr(14) + bytes([HALT])

def bench_call_ret_loop(n: int) -> bytes:
    """CALL/RET loop: call subroutine n times."""
    # PUSH n, loop: CALL subroutine, DEC, JNZ loop, HALT
    # Subroutine: PUSH 1, POP, RET (noop)
    # Layout:
    #   0-4:   PUSH n
    #   5-7:   CALL 12     (call subroutine)
    #   8:     DEC
    #   9-11:  JNZ 5
    #   12:    HALT
    # Wait, this doesn't work because HALT ends execution.
    # Better: subroutine PUSH 1 POP RET, then after loop HALT
    #   0-4:   PUSH n
    #   5-7:   CALL 13     (call subroutine at 13)
    #   8:     DEC
    #   9-11:  JNZ 5
    #   12:    HALT
    #   13-17: PUSH 1
    #   18:    POP
    #   19:    RET
    return push_imm32(n) + call_addr(13) + bytes([DEC]) + jnz_addr(5) + bytes([HALT]) + push_imm32(1) + bytes([POP, RET])

def bench_nested_call(n: int) -> bytes:
    """Nested CALL: outer calls inner which does work."""
    # PUSH n, loop: CALL outer, DEC, JNZ
    # outer: CALL inner, RET
    # inner: PUSH 1, POP, RET
    return push_imm32(n) + call_addr(15) + bytes([DEC]) + jnz_addr(5) + bytes([HALT]) + call_addr(20) + bytes([RET]) + push_imm32(1) + bytes([POP, RET])

def bench_confidence_loop(n: int) -> bytes:
    """Confidence operations loop."""
    return push_imm32(n) + bytes([DUP]) + jz_addr(25) + bytes([POP]) + push_imm32(1) + bytes([CONF_SET]) + bytes([CONF_GET]) + push_imm32(2) + bytes([CONF_MUL]) + bytes([DEC]) + jnz_addr(10) + bytes([HALT])

def bench_a2a_loop(n: int) -> bytes:
    """Agent-to-agent signal/listen loop."""
    return push_imm32(n) + bytes([DUP]) + jz_addr(25) + bytes([POP]) + push_imm32(42) + bytes([SIGNAL, 1]) + bytes([LISTEN, 1]) + bytes([DEC]) + jnz_addr(10) + bytes([HALT])

def bench_factorial(n: int) -> bytes:
    """Factorial computation: measures mixed arithmetic + control flow."""
    # Standard factorial loop from conformance tests
    # PUSH 1, PUSH n, loop: LOAD acc, LOAD n, MUL, STORE acc, LOAD n, DEC, STORE n, JNZ
    return push_imm32(1) + store_addr(0) + push_imm32(n) + store_addr(4) + load_addr(0) + load_addr(4) + bytes([MUL]) + store_addr(0) + load_addr(4) + bytes([DEC]) + store_addr(4) + jnz_addr(16) + load_addr(0) + bytes([HALT])

def bench_fibonacci(n: int) -> bytes:
    """Fibonacci: measures stack manipulation + arithmetic."""
    # PUSH 0, PUSH 1, n times: OVER, ADD, SWAP
    return push_imm32(0) + push_imm32(1) + (bytes([OVER, ADD, SWAP]) * n) + bytes([HALT])

def bench_startup(num_programs: int) -> List[bytes]:
    """VM startup cost: many tiny programs."""
    programs = []
    for i in range(num_programs):
        programs.append(push_imm32(i) + bytes([HALT]))
    return programs


# ─── Benchmark Runner ────────────────────────────────────────────────────────

@dataclass
class BenchmarkResult:
    name: str
    category: str
    iterations: int
    total_ops: int
    total_time_ms: float
    ops_per_second: float
    avg_op_time_ns: float = 0.0
    note: str = ""

    def to_dict(self):
        return asdict(self)


class FluxBenchmark:
    """Benchmarks the FLUX reference VM."""

    def __init__(self, default_iterations: int = 10000):
        self.default_iterations = default_iterations
        self.results: List[BenchmarkResult] = []

    def run_benchmark(self, name: str, category: str, program_builder, n: int,
                      ops_per_iteration: int = 1, warmup: int = 3) -> BenchmarkResult:
        """Run a single benchmark with warmup and multiple iterations."""
        code = program_builder(n)

        # Warmup runs
        for _ in range(warmup):
            vm = FluxVM()
            vm.max_steps = n * 20  # Safety limit
            vm.run(code)

        # Timed runs
        total_ops = 0
        total_time = 0.0
        runs = 5

        for _ in range(runs):
            vm = FluxVM()
            vm.max_steps = n * 20
            start = time.perf_counter_ns()
            vm.run(code)
            elapsed = time.perf_counter_ns() - start
            total_time += elapsed
            total_ops += vm.steps

        avg_time_ms = total_time / runs / 1_000_000.0
        avg_time_sec = total_time / runs / 1_000_000_000.0
        ops_per_sec = total_ops / avg_time_sec if avg_time_sec > 0 else 0
        avg_op_ns = (total_time / runs / total_ops) if total_ops > 0 else 0

        result = BenchmarkResult(
            name=name, category=category, iterations=n,
            total_ops=total_ops, total_time_ms=avg_time_ms,
            ops_per_second=ops_per_sec, avg_op_time_ns=avg_op_ns,
        )
        self.results.append(result)
        return result

    def run_all(self, n: int = None):
        """Run all benchmarks."""
        if n is None:
            n = self.default_iterations

        # Instruction decode
        self.run_benchmark("NOP loop", "decode", bench_nop_loop, n, ops_per_iteration=1)
        self.run_benchmark("PUSH+HALT", "decode", lambda x: push_imm32(x) + bytes([HALT]), n, ops_per_iteration=2)

        # Integer arithmetic
        self.run_benchmark("ADD loop", "arith", bench_add_loop, n)
        self.run_benchmark("MUL loop", "arith", bench_mul_loop, n)
        self.run_benchmark("DIV+MOD loop", "arith", bench_div_mod_loop, n)

        # Float arithmetic
        self.run_benchmark("FADD+FMUL loop", "float", bench_float_loop, n)

        # Logic/bitwise
        self.run_benchmark("AND/OR/XOR/SHL loop", "logic", bench_logic_loop, n)

        # Comparison
        self.run_benchmark("EQ/LT/GT loop", "comparison", bench_comparison_loop, n)

        # Memory
        self.run_benchmark("STORE/LOAD loop", "memory", bench_mem_store_load_loop, n)
        self.run_benchmark("POKE/PEEK loop", "memory", bench_mem_peek_poke_loop, n)

        # Stack manipulation
        self.run_benchmark("DUP/SWAP/OVER/ROT loop", "stack", bench_stack_manip_loop, n)

        # Control flow
        self.run_benchmark("CALL/RET loop", "control", bench_call_ret_loop, n)
        self.run_benchmark("Nested CALL", "control", bench_nested_call, n)
        self.run_benchmark("Factorial", "control", bench_factorial, min(n, 12))

        # Confidence
        self.run_benchmark("CONF_SET/GET/MUL loop", "confidence", bench_confidence_loop, n)

        # A2A
        self.run_benchmark("SIGNAL/LISTEN loop", "a2a", bench_a2a_loop, n)

        # Complex programs
        self.run_benchmark("Fibonacci", "complex", bench_fibonacci, min(n, 50))

        # Startup cost
        programs = bench_startup(1000)
        start = time.perf_counter_ns()
        for code in programs:
            vm = FluxVM()
            vm.run(code)
        elapsed = (time.perf_counter_ns() - start) / 1_000_000
        self.results.append(BenchmarkResult(
            name="1000x startup", category="startup",
            iterations=1000, total_ops=2000, total_time_ms=elapsed,
            ops_per_second=2000 / (elapsed / 1000) if elapsed > 0 else 0,
            avg_op_time_ns=elapsed * 1000 / 2000 if elapsed > 0 else 0,
            note="1000 separate PUSH+HALT programs"
        ))

        return self.results

    def run_category(self, category: str, n: int = None):
        """Run benchmarks for a specific category."""
        if n is None:
            n = self.default_iterations

        category_benchmarks = {
            "decode": [
                ("NOP loop", bench_nop_loop),
                ("PUSH+HALT", lambda x: push_imm32(x) + bytes([HALT])),
            ],
            "arith": [
                ("ADD loop", bench_add_loop),
                ("MUL loop", bench_mul_loop),
                ("DIV+MOD loop", bench_div_mod_loop),
            ],
            "float": [
                ("FADD+FMUL loop", bench_float_loop),
            ],
            "logic": [
                ("AND/OR/XOR/SHL loop", bench_logic_loop),
            ],
            "comparison": [
                ("EQ/LT/GT loop", bench_comparison_loop),
            ],
            "memory": [
                ("STORE/LOAD loop", bench_mem_store_load_loop),
                ("POKE/PEEK loop", bench_mem_peek_poke_loop),
            ],
            "stack": [
                ("DUP/SWAP/OVER/ROT loop", bench_stack_manip_loop),
            ],
            "control": [
                ("CALL/RET loop", bench_call_ret_loop),
                ("Nested CALL", bench_nested_call),
                ("Factorial", lambda x: bench_factorial(min(x, 12))),
            ],
            "confidence": [
                ("CONF_SET/GET/MUL loop", bench_confidence_loop),
            ],
            "a2a": [
                ("SIGNAL/LISTEN loop", bench_a2a_loop),
            ],
            "complex": [
                ("Fibonacci", bench_fibonacci),
            ],
        }

        if category not in category_benchmarks:
            print(f"Unknown category: {category}")
            print(f"Available: {', '.join(category_benchmarks.keys())}")
            return

        for name, builder in category_benchmarks[category]:
            self.run_benchmark(name, category, builder, n)

        return self.results

    def print_terminal(self):
        """Print results to terminal."""
        print("\n" + "=" * 80)
        print("FLUX PERFORMANCE BENCHMARK RESULTS")
        print(f"Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC")
        print(f"Runtime: Python reference VM (conformance_core.py)")
        print(f"Python: {sys.version.split()[0]}")
        print("=" * 80)

        # Summary table
        header = f"{'Benchmark':35s} {'Category':12s} {'Ops':>10s} {'Time(ms)':>10s} {'Ops/sec':>12s} {'ns/op':>10s}"
        print(f"\n{header}")
        print("-" * 80)
        for r in self.results:
            line = f"{r.name:35s} {r.category:12s} {r.total_ops:10d} {r.total_time_ms:10.2f} {r.ops_per_second:12.0f} {r.avg_op_time_ns:10.1f}"
            print(line)

        # Category averages
        print("\n--- CATEGORY AVERAGES ---")
        categories = {}
        for r in self.results:
            categories.setdefault(r.category, []).append(r)
        for cat, cat_results in sorted(categories.items()):
            avg_ops = sum(r.ops_per_second for r in cat_results) / len(cat_results)
            avg_ns = sum(r.avg_op_time_ns for r in cat_results) / len(cat_results)
            print(f"  {cat:15s}  {avg_ops:>10.0f} ops/sec  {avg_ns:>8.1f} ns/op  ({len(cat_results)} benchmarks)")

        print("\n" + "=" * 80)

    def output_json(self, filepath: str = None):
        """Output results as JSON."""
        output = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "runtime": "python-reference",
            "python_version": sys.version.split()[0],
            "benchmarks": [r.to_dict() for r in self.results],
        }
        json_str = json.dumps(output, indent=2)
        if filepath:
            with open(filepath, "w") as f:
                f.write(json_str)
            print(f"Results written to {filepath}")
        else:
            print(json_str)

    def output_markdown(self, filepath: str = None):
        """Output results as Markdown."""
        lines = [
            "# FLUX Performance Benchmark Results",
            "",
            f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC  ",
            f"**Runtime:** Python reference VM  ",
            f"**Python:** {sys.version.split()[0]}  ",
            f"**Benchmarks:** {len(self.results)}  ",
            "",
            "## Summary",
            "",
            "| Benchmark | Category | Total Ops | Time (ms) | Ops/sec | ns/op |",
            "|-----------|----------|-----------|-----------|---------|-------|",
        ]
        for r in self.results:
            lines.append(f"| {r.name} | {r.category} | {r.total_ops} | {r.total_time_ms:.2f} | {r.ops_per_second:.0f} | {r.avg_op_time_ns:.1f} |")

        # Category breakdown
        lines.extend(["", "## Category Averages", ""])
        categories = {}
        for r in self.results:
            categories.setdefault(r.category, []).append(r)
        lines.append("| Category | Avg Ops/sec | Avg ns/op | Benchmarks |")
        lines.append("|----------|-------------|-----------|------------|")
        for cat, cat_results in sorted(categories.items()):
            avg_ops = sum(r.ops_per_second for r in cat_results) / len(cat_results)
            avg_ns = sum(r.avg_op_time_ns for r in cat_results) / len(cat_results)
            lines.append(f"| {cat} | {avg_ops:.0f} | {avg_ns:.1f} | {len(cat_results)} |")

        output = "\n".join(lines)
        if filepath:
            with open(filepath, "w") as f:
                f.write(output)
            print(f"Markdown report written to {filepath}")
        else:
            print(output)


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="FLUX Performance Benchmark Harness")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    parser.add_argument("--markdown", action="store_true", help="Output as Markdown table")
    parser.add_argument("--category", type=str, help="Run only benchmarks for a category")
    parser.add_argument("--iterations", type=int, default=10000, help="Loop iterations (default: 10000)")
    parser.add_argument("--output", type=str, help="Write output to file")
    args = parser.parse_args()

    bench = FluxBenchmark(default_iterations=args.iterations)

    if args.category:
        bench.run_category(args.category, args.iterations)
    else:
        bench.run_all(args.iterations)

    if args.json:
        bench.output_json(args.output)
    elif args.markdown:
        bench.output_markdown(args.output)
    else:
        bench.print_terminal()

    return 0


if __name__ == "__main__":
    sys.exit(main())
