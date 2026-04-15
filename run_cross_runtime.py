#!/usr/bin/env python3
"""
FLUX Cross-Runtime Conformance Runner with Shim Support (SHIM-001)

Extends run_conformance.py with bytecode translation via canonical_opcode_shim.
This enables running the same test vectors against runtimes that use different
opcode numberings by translating bytecode through the canonical ISA.

Usage:
    python run_cross_runtime.py                    # Python reference (no shim needed)
    python run_cross_runtime.py --shim-go          # Translate vectors for Go runtime
    python run_cross_runtime.py --shim-coverage    # Show opcode translation coverage
    python run_cross_runtime.py --translate-only   # Show translated bytecode for each vector

This addresses TASK SHIM-001 from oracle1-index/TASKS.md.
"""

import argparse
import json
import os
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

# ─── Import the conformance core ──────────────────────────────────────────────

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conformance_core import (
    ConformanceTestSuite, ConformanceTestCase, FluxVM,
    FLAG_Z, FLAG_S, FLAG_C, FLAG_O, FLAGS_ANY,
)


# ─── Shim Translation ───────────────────────────────────────────────────────

def get_shim():
    """Lazy-load the canonical opcode shim."""
    try:
        import canonical_opcode_shim as shim
        return shim
    except ImportError:
        print("ERROR: canonical_opcode_shim.py not found", file=sys.stderr)
        sys.exit(1)


def translate_bytecode(bytecode_hex: str, target_runtime: str) -> tuple[str, int, int]:
    """Translate bytecode from Python runtime to target runtime via canonical ISA.

    Returns (translated_hex, opcodes_translated, opcodes_unmapped).
    """
    shim = get_shim()
    bytecode = bytes.fromhex(bytecode_hex)

    # Translate: Python -> Canonical -> Target
    translators = {
        "rust": shim.canonical_to_rust,
        "c": shim.canonical_to_cos,
        "go": shim.canonical_to_go,
        "canonical": shim.python_to_canonical,
    }

    translator = translators.get(target_runtime)
    if translator is None:
        raise ValueError(f"Unknown target runtime: {target_runtime}")

    canonical = shim.python_to_canonical(bytecode)
    translated = translator(canonical)

    # Count translation success
    unmapped_count = sum(1 for b in translated if b == 0xFE)

    return translated.hex(), len(bytecode), unmapped_count


# ─── Shimmed Runtime ─────────────────────────────────────────────────────────

class ShimmedPythonRuntime:
    """Runs test vectors after translating them from Python to canonical ISA
    and back. This validates that the shim round-trips correctly."""

    name = "shimmed-python"
    description = "Python VM with round-trip shim translation (tests shim correctness)"

    def run_test(self, case: ConformanceTestCase) -> dict:
        shim = get_shim()
        start = time.monotonic()

        try:
            # Round-trip: Python -> Canonical -> Python
            original = bytes.fromhex(case.bytecode_hex)
            canonical = shim.python_to_canonical(original)
            round_tripped = shim.canonical_to_python(canonical)

            # Run the round-tripped bytecode
            vm = FluxVM()
            stack, flags = vm.run(round_tripped, case.initial_stack or None)
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            return {
                "name": f"shim:{case.name}",
                "passed": False,
                "error": f"Round-trip error: {e}",
                "duration_ms": elapsed,
            }

        elapsed = (time.monotonic() - start) * 1000

        # Check stack
        passed = True
        reasons = []
        if len(stack) != len(case.expected_stack):
            passed = False
            reasons.append(f"Stack length: expected {len(case.expected_stack)}, got {len(stack)}")
        else:
            for i, (actual, expected) in enumerate(zip(stack, case.expected_stack)):
                if case.allow_float_epsilon and (isinstance(actual, float) or isinstance(expected, float)):
                    if abs(float(actual) - float(expected)) > 1e-5:
                        passed = False
                        reasons.append(f"Stack[{i}]: expected ~{expected}, got {actual}")
                elif actual != expected:
                    passed = False
                    reasons.append(f"Stack[{i}]: expected {expected}, got {actual}")

        if case.expected_flags != FLAGS_ANY and flags != case.expected_flags:
            passed = False
            reasons.append(f"Flags: expected 0x{case.expected_flags:02x}, got 0x{flags:02x}")

        return {
            "name": f"shim:{case.name}",
            "passed": passed,
            "error": "; ".join(reasons) if not passed else "",
            "actual_stack": stack,
            "actual_flags": flags,
            "duration_ms": elapsed,
        }


# ─── Cross-Runtime Translation Report ───────────────────────────────────────

def generate_translation_report(target_runtime: str = "go") -> str:
    """Generate a report showing how each test vector translates to a target runtime."""
    shim = get_shim()
    suite = ConformanceTestSuite()
    suite.load_builtin_cases()

    lines = [
        f"# FLUX Bytecode Translation Report: Python -> {target_runtime.upper()}",
        f"",
        f"**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC",
        f"**Test Vectors:** {len(suite.cases)}",
        f"**Target Runtime:** {target_runtime}",
        f"",
        "| Vector | Category | Bytes | Translated | Unmapped | Status |",
        "|--------|----------|-------|------------|----------|--------|",
    ]

    total_translated = 0
    total_unmapped = 0
    total_passed = 0

    for case in suite.cases:
        try:
            translated_hex, opcodes_translated, unmapped = translate_bytecode(
                case.bytecode_hex, target_runtime)
            status = "OK" if unmapped == 0 else f"WARN({unmapped} unmapped)"
            if unmapped == 0:
                total_passed += 1
            total_translated += opcodes_translated
            total_unmapped += unmapped

            # Truncate long hex for readability
            hex_display = translated_hex[:20] + "..." if len(translated_hex) > 20 else translated_hex
            lines.append(
                f"| {case.name:40s} | {case.name.split('_')[0]:8s} "
                f"| {opcodes_translated:5d} | {len(translated_hex)//2:10d} "
                f"| {unmapped:8d} | {status:20s} |"
            )
        except Exception as e:
            lines.append(
                f"| {case.name:40s} | {case.name.split('_')[0]:8s} "
                f"| ERROR: {str(e)[:50]:50s} |"
            )

    lines.extend([
        f"",
        f"## Summary",
        f"",
        f"- **Fully translatable:** {total_passed}/{len(suite.cases)} vectors ({100*total_passed/max(len(suite.cases),1):.1f}%)",
        f"- **Total opcodes processed:** {total_translated}",
        f"- **Total unmapped opcodes:** {total_unmapped}",
        f"",
        f"## Coverage",
        f"",
    ])

    # Include shim coverage report
    coverage = shim.coverage_report()
    lines.extend(coverage.split("\n"))

    return "\n".join(lines)


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="FLUX Cross-Runtime Conformance with Shim Support (SHIM-001)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_cross_runtime.py                      # Round-trip shim test
  python run_cross_runtime.py --shim-go            # Translate for Go, show report
  python run_cross_runtime.py --shim-rust          # Translate for Rust, show report
  python run_cross_runtime.py --shim-coverage      # Show translation coverage
  python run_cross_runtime.py --translate-only     # Show translated bytecode per vector
        """)

    parser.add_argument("--shim-go", action="store_true",
                        help="Translate test vectors for Go runtime and report")
    parser.add_argument("--shim-rust", action="store_true",
                        help="Translate test vectors for Rust runtime and report")
    parser.add_argument("--shim-c", action="store_true",
                        help="Translate test vectors for C runtime and report")
    parser.add_argument("--shim-coverage", action="store_true",
                        help="Show canonical opcode shim coverage report")
    parser.add_argument("--translate-only", action="store_true",
                        help="Show translated bytecode for each vector (Python->Canonical)")
    parser.add_argument("--json", action="store_true",
                        help="Output results as JSON")
    parser.add_argument("--output", type=str, metavar="FILE",
                        help="Write output to file")

    args = parser.parse_args()

    shim = get_shim()

    # Coverage report
    if args.shim_coverage:
        report = shim.coverage_report()
        print(report)
        if args.output:
            with open(args.output, "w") as f:
                f.write(report)
            print(f"\nWritten to {args.output}")
        return 0

    # Translation report for specific runtime
    if args.shim_go or args.shim_rust or args.shim_c:
        target = "go" if args.shim_go else ("rust" if args.shim_rust else "c")
        report = generate_translation_report(target)

        if args.output:
            with open(args.output, "w") as f:
                f.write(report)
            print(f"Report written to {args.output}")
        else:
            print(report)
        return 0

    # Translate-only mode
    if args.translate_only:
        suite = ConformanceTestSuite()
        suite.load_builtin_cases()

        for case in suite.cases:
            try:
                canonical_hex, _, unmapped = translate_bytecode(case.bytecode_hex, "canonical")
                status = "OK" if unmapped == 0 else f"WARN({unmapped})"
                print(f"  {case.name:40s} -> {canonical_hex:40s} [{status}]")
            except Exception as e:
                print(f"  {case.name:40s} -> ERROR: {e}")
        return 0

    # Default: Run round-trip shim validation
    print("=" * 60)
    print("FLUX Shim Round-Trip Validation")
    print(f"Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC")
    print("=" * 60)

    runtime = ShimmedPythonRuntime()
    suite = ConformanceTestSuite()
    suite.load_builtin_cases()

    passed = 0
    failed = 0
    failed_tests = []

    for case in suite.cases:
        result = runtime.run_test(case)
        if result["passed"]:
            passed += 1
        else:
            failed += 1
            failed_tests.append((case.name, result["error"]))

    total = passed + failed
    print(f"\nResults: {passed}/{total} passed ({100*passed/max(total,1):.1f}%)")
    print(f"Total vectors: {total}")

    if failed_tests:
        print(f"\n--- {len(failed_tests)} FAILURES ---")
        for name, error in failed_tests:
            print(f"  FAIL: {name}")
            print(f"        {error}")
    else:
        print("\nAll vectors passed shim round-trip validation!")

    if args.json:
        output = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "shim_round_trip_validation",
            "total": total,
            "passed": passed,
            "failed": failed,
            "pass_rate": f"{100*passed/max(total,1):.1f}%",
            "failures": [{"name": n, "error": e} for n, e in failed_tests],
        }
        json_str = json.dumps(output, indent=2)
        if args.output:
            with open(args.output, "w") as f:
                f.write(json_str)
            print(f"\nJSON results written to {args.output}")
        else:
            print(json_str)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
