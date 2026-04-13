#!/usr/bin/env python3
"""
FLUX Cross-Runtime Conformance Runner (CONF-001)

Executes all conformance test vectors against multiple FLUX runtimes
and reports a pass/fail matrix per runtime.

Usage:
    python run_conformance.py              # Run against Python reference VM
    python run_conformance.py --all        # Run against all available runtimes
    python run_conformance.py --json       # Output results as JSON
    python run_conformance.py --markdown   # Output results as Markdown table

Runtimes supported:
    - Python (reference VM, always available)
    - TypeScript/WASM (via subprocess if npm available)
    - C (via subprocess if compiled)
    - Rust (via subprocess if compiled)
    - Go (via subprocess if compiled)
"""

import argparse
import json
import os
import struct
import subprocess
import sys
import time
from dataclasses import dataclass, field, asdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# ─── Import the conformance core ──────────────────────────────────────────────

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from conformance_core import (
    ConformanceTestSuite, ConformanceTestCase, FluxVM,
    FLAG_Z, FLAG_S, FLAG_C, FLAG_O, FLAGS_ANY,
)


# ─── Runtime Interface ───────────────────────────────────────────────────────

@dataclass
class RuntimeResult:
    """Result of running a single test against a single runtime."""
    runtime_name: str
    test_name: str
    passed: bool
    error: str = ""
    actual_stack: List = field(default_factory=list)
    actual_flags: int = 0
    duration_ms: float = 0.0

    def to_dict(self):
        return asdict(self)


@dataclass
class RuntimeSummary:
    """Summary for a single runtime across all tests."""
    runtime_name: str
    total: int = 0
    passed: int = 0
    failed: int = 0
    errors: int = 0
    total_duration_ms: float = 0.0
    failed_tests: List[str] = field(default_factory=list)

    @property
    def pass_rate_pct(self) -> str:
        return f"{self.passed / max(self.total, 1):.1%}"

    def to_dict(self):
        d = asdict(self)
        d["pass_rate"] = self.pass_rate_pct
        return d


class FluxRuntime:
    """Base class for FLUX runtime adapters."""

    name: str = "unknown"
    description: str = ""

    def is_available(self) -> bool:
        """Check if this runtime is available to run."""
        raise NotImplementedError

    def run_test(self, case: ConformanceTestCase) -> RuntimeResult:
        """Run a single conformance test case."""
        raise NotImplementedError


class PythonReferenceRuntime(FluxRuntime):
    """Python reference VM — always available."""

    name = "python-reference"
    description = "Python reference VM (conformance_core.py)"

    def is_available(self) -> bool:
        return True

    def run_test(self, case: ConformanceTestCase) -> RuntimeResult:
        start = time.monotonic()
        vm = FluxVM()
        try:
            code = bytes.fromhex(case.bytecode_hex)
            stack, flags = vm.run(code, case.initial_stack or None)
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            return RuntimeResult(
                runtime_name=self.name, test_name=case.name,
                passed=False, error=str(e), duration_ms=elapsed)

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

        # Check flags
        if case.expected_flags != FLAGS_ANY and flags != case.expected_flags:
            passed = False
            reasons.append(f"Flags: expected 0x{case.expected_flags:02x}, got 0x{flags:02x}")

        return RuntimeResult(
            runtime_name=self.name, test_name=case.name,
            passed=passed, error="; ".join(reasons) if not passed else "",
            actual_stack=stack, actual_flags=flags, duration_ms=elapsed)


class SubprocessRuntime(FluxRuntime):
    """Generic adapter for runtimes accessed via subprocess."""

    def __init__(self, name: str, description: str, cmd: List[str], test_format: str = "json"):
        self.name = name
        self.description = description
        self.cmd = cmd
        self.test_format = test_format

    def is_available(self) -> bool:
        try:
            result = subprocess.run(
                self.cmd + ["--version"],
                capture_output=True, text=True, timeout=10)
            return result.returncode == 0 or len(result.stdout) > 0
        except (FileNotFoundError, subprocess.TimeoutExpired):
            return False

    def run_test(self, case: ConformanceTestCase) -> RuntimeResult:
        start = time.monotonic()

        # Build test input as JSON
        test_input = {
            "bytecode_hex": case.bytecode_hex,
            "initial_stack": case.initial_stack or [],
            "expected_stack": case.expected_stack,
            "expected_flags": case.expected_flags,
            "allow_float_epsilon": case.allow_float_epsilon,
        }

        try:
            result = subprocess.run(
                self.cmd,
                input=json.dumps(test_input),
                capture_output=True, text=True, timeout=30)

            if result.returncode != 0:
                elapsed = (time.monotonic() - start) * 1000
                return RuntimeResult(
                    runtime_name=self.name, test_name=case.name,
                    passed=False, error=result.stderr[:200], duration_ms=elapsed)

            output = json.loads(result.stdout)
            elapsed = (time.monotonic() - start) * 1000

            return RuntimeResult(
                runtime_name=self.name, test_name=case.name,
                passed=output.get("passed", False),
                error=output.get("error", ""),
                actual_stack=output.get("actual_stack", []),
                actual_flags=output.get("actual_flags", 0),
                duration_ms=elapsed)

        except subprocess.TimeoutExpired:
            elapsed = (time.monotonic() - start) * 1000
            return RuntimeResult(
                runtime_name=self.name, test_name=case.name,
                passed=False, error="Timeout (30s)", duration_ms=elapsed)
        except Exception as e:
            elapsed = (time.monotonic() - start) * 1000
            return RuntimeResult(
                runtime_name=self.name, test_name=case.name,
                passed=False, error=str(e), duration_ms=elapsed)


# ─── Conformance Runner ──────────────────────────────────────────────────────

class ConformanceRunner:
    """
    Runs conformance test vectors against one or more FLUX runtimes
    and produces a results matrix.
    """

    def __init__(self):
        self.runtimes: List[FluxRuntime] = []
        self.suite = ConformanceTestSuite()
        self.suite.load_builtin_cases()

    def add_runtime(self, runtime: FluxRuntime):
        self.runtimes.append(runtime)

    def discover_runtimes(self):
        """Auto-discover available runtimes."""
        # Python reference is always available
        self.add_runtime(PythonReferenceRuntime())

        # Check for TypeScript/WASM runner
        ts_runner = SubprocessRuntime(
            name="typescript-wasm",
            description="TypeScript/WASM FLUX VM (flux-runtime-wasm)",
            cmd=["node", "src/run-conformance.js"],
        )
        if ts_runner.is_available():
            self.add_runtime(ts_runner)

        # Check for Go runner
        go_runner = SubprocessRuntime(
            name="go-flux",
            description="Go FLUX VM (flux-swarm)",
            cmd=["go", "run", "./cmd/conformance-runner/"],
        )
        if go_runner.is_available():
            self.add_runtime(go_runner)

        # Check for Rust runner
        rust_runner = SubprocessRuntime(
            name="rust-flux",
            description="Rust FLUX VM (flux-core)",
            cmd=["cargo", "run", "--", "--conformance"],
        )
        if rust_runner.is_available():
            self.add_runtime(rust_runner)

        # Check for C runner
        c_runner = SubprocessRuntime(
            name="c-flux",
            description="C FLUX VM (flux-c)",
            cmd=["./flux-c-conformance"],
        )
        if c_runner.is_available():
            self.add_runtime(c_runner)

    def run_all(self, filter_category: str = None) -> Dict[str, List[RuntimeResult]]:
        """Run all test vectors against all runtimes."""
        results = {}
        for runtime in self.runtimes:
            runtime_results = []
            for case in self.suite.cases:
                if filter_category and not case.name.startswith(filter_category):
                    continue
                result = runtime.run_test(case)
                runtime_results.append(result)
            results[runtime.name] = runtime_results
        return results

    def build_summaries(self, results: Dict[str, List[RuntimeResult]]) -> List[RuntimeSummary]:
        """Build per-runtime summaries."""
        summaries = []
        for runtime_name, runtime_results in results.items():
            summary = RuntimeSummary(runtime_name=runtime_name)
            for r in runtime_results:
                summary.total += 1
                summary.total_duration_ms += r.duration_ms
                if r.error and not r.passed:
                    # Distinguish between test failure and runtime error
                    summary.failed += 1
                    summary.failed_tests.append(r.test_name)
                elif r.passed:
                    summary.passed += 1
                else:
                    summary.failed += 1
                    summary.failed_tests.append(r.test_name)
            summaries.append(summary)
        return summaries

    def print_terminal(self, results: Dict[str, List[RuntimeResult]]):
        """Print results to terminal."""
        summaries = self.build_summaries(results)

        print("\n" + "=" * 70)
        print("FLUX CROSS-RUNTIME CONFORMANCE RESULTS")
        print(f"Date: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC")
        print(f"Test vectors: {len(self.suite.cases)}")
        print(f"Runtimes tested: {len(self.runtimes)}")
        print("=" * 70)

        # Summary matrix
        header = f"{'Runtime':30s} {'Passed':>8s} {'Failed':>8s} {'Rate':>8s} {'Time':>8s}"
        print(f"\n{header}")
        print("-" * 70)
        for s in summaries:
            line = f"{s.runtime_name:30s} {s.passed:8d} {s.failed:8d} {s.pass_rate_pct:>8s} {s.total_duration_ms:7.0f}ms"
            print(line)

        # Per-runtime details for failures
        for s in summaries:
            if s.failed_tests:
                print(f"\n--- {s.runtime_name} FAILURES ---")
                runtime_results = results[s.runtime_name]
                for r in runtime_results:
                    if not r.passed:
                        print(f"  FAIL: {r.test_name}")
                        if r.error:
                            print(f"        {r.error}")

        # Cross-runtime comparison
        print("\n--- CROSS-RUNTIME COMPARISON ---")
        all_names = [s.runtime_name for s in summaries]
        if len(all_names) > 1:
            # Find tests that pass on some runtimes but fail on others
            for case in self.suite.cases:
                case_results = {}
                for rn, rr in results.items():
                    for r in rr:
                        if r.test_name == case.name:
                            case_results[rn] = r.passed

                if len(set(case_results.values())) > 1:
                    status_str = " | ".join(
                        f"{'PASS' if case_results.get(rn, False) else 'FAIL':4s}" for rn in all_names)
                    print(f"  DIVERGE: {case.name:40s} {status_str}")

        print("\n" + "=" * 70)

    def output_json(self, results: Dict[str, List[RuntimeResult]], filepath: str = None):
        """Output results as JSON."""
        summaries = self.build_summaries(results)
        output = {
            "timestamp": datetime.utcnow().isoformat(),
            "test_vector_count": len(self.suite.cases),
            "runtimes": [s.to_dict() for s in summaries],
            "results": {},
        }
        for runtime_name, runtime_results in results.items():
            output["results"][runtime_name] = [r.to_dict() for r in runtime_results]

        json_str = json.dumps(output, indent=2)
        if filepath:
            with open(filepath, "w") as f:
                f.write(json_str)
            print(f"Results written to {filepath}")
        else:
            print(json_str)

    def output_markdown(self, results: Dict[str, List[RuntimeResult]], filepath: str = None):
        """Output results as Markdown table."""
        summaries = self.build_summaries(results)

        lines = [
            "# FLUX Conformance Test Results",
            f"",
            f"**Date:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M')} UTC  ",
            f"**Test Vectors:** {len(self.suite.cases)}  ",
            f"**Runtimes:** {len(self.runtimes)}  ",
            f"",
            "## Summary",
            "",
            "| Runtime | Passed | Failed | Rate | Time |",
            "|---------|--------|--------|------|------|",
        ]

        for s in summaries:
            lines.append(f"| {s.runtime_name} | {s.passed} | {s.failed} | {s.pass_rate_pct} | {s.total_duration_ms:.0f}ms |")

        # Category breakdown
        lines.extend(["", "## Category Breakdown", ""])

        categories = {}
        for case in self.suite.cases:
            cat = case.name.split("_")[0]
            categories.setdefault(cat, []).append(case)

        for cat, cat_cases in sorted(categories.items()):
            cat_lines = [f"### {cat.upper()} ({len(cat_cases)} tests)", ""]
            for rn, rr in results.items():
                cat_results = [r for r in rr if r.test_name in [c.name for c in cat_cases]]
                cat_passed = sum(1 for r in cat_results if r.passed)
                cat_total = len(cat_results)
                cat_lines.append(f"- **{rn}:** {cat_passed}/{cat_total}")
            lines.extend(cat_lines)

        output = "\n".join(lines)

        if filepath:
            with open(filepath, "w") as f:
                f.write(output)
            print(f"Markdown report written to {filepath}")
        else:
            print(output)

    def export_test_vectors_json(self, filepath: str):
        """Export all test vectors as a JSON file for other runtimes to consume."""
        vectors = []
        for case in self.suite.cases:
            vectors.append({
                "name": case.name,
                "bytecode_hex": case.bytecode_hex,
                "initial_stack": case.initial_stack,
                "expected_stack": case.expected_stack,
                "expected_flags": case.expected_flags,
                "allow_float_epsilon": case.allow_float_epsilon,
                "description": case.description,
            })

        with open(filepath, "w") as f:
            json.dump({
                "version": "2.0",
                "generated": datetime.now(timezone.utc).isoformat(),
                "total_vectors": len(vectors),
                "vectors": vectors,
            }, f, indent=2)

        print(f"Exported {len(vectors)} test vectors to {filepath}")


# ─── Main ────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="FLUX Cross-Runtime Conformance Runner",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python run_conformance.py                    # Python reference only
  python run_conformance.py --all              # All available runtimes
  python run_conformance.py --json             # JSON output
  python run_conformance.py --markdown         # Markdown report
  python run_conformance.py --export           # Export test vectors as JSON
  python run_conformance.py --category arith   # Run arithmetic tests only
        """)

    parser.add_argument("--all", action="store_true",
                        help="Run against all available runtimes")
    parser.add_argument("--json", action="store_true",
                        help="Output results as JSON")
    parser.add_argument("--markdown", action="store_true",
                        help="Output results as Markdown table")
    parser.add_argument("--export", type=str, metavar="FILE",
                        help="Export test vectors as JSON for other runtimes")
    parser.add_argument("--category", type=str,
                        help="Run only tests matching category prefix (e.g. 'arith', 'ctrl')")
    parser.add_argument("--output", type=str, metavar="FILE",
                        help="Write output to file instead of stdout")
    parser.add_argument("--list", action="store_true",
                        help="List all test vector names and exit")

    args = parser.parse_args()

    runner = ConformanceRunner()

    # Always add Python reference
    runner.add_runtime(PythonReferenceRuntime())

    if args.all:
        runner.discover_runtimes()
        # Remove duplicates (Python is already added)
        seen = {"python-reference"}
        unique = []
        for rt in runner.runtimes:
            if rt.name not in seen:
                seen.add(rt.name)
                unique.append(rt)
        runner.runtimes = unique

    if args.list:
        print(f"Total test vectors: {len(runner.suite.cases)}")
        for case in runner.suite.cases:
            cat = case.name.split("_")[0]
            print(f"  [{cat:8s}] {case.name:40s} {case.description}")
        return 0

    if args.export:
        runner.export_test_vectors_json(args.export)
        return 0

    print(f"Running {len(runner.suite.cases)} test vectors against {len(runner.runtimes)} runtime(s)...")
    print(f"Runtimes: {', '.join(r.name for r in runner.runtimes)}")
    results = runner.run_all(filter_category=args.category)

    if args.json:
        runner.output_json(results, args.output)
    elif args.markdown:
        runner.output_markdown(results, args.output)
    else:
        runner.print_terminal(results)

    # Exit code
    summaries = runner.build_summaries(results)
    all_passed = all(s.failed == 0 for s in summaries)
    return 0 if all_passed else 1


if __name__ == "__main__":
    sys.exit(main())
