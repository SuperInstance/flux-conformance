#!/usr/bin/env python3
"""
FLUX Conformance Test Runner — Python Runtime

Loads test vectors from vectors/*.json and validates them against the
flux-runtime Python VM (flux.vm.interpreter.Interpreter).

Usage:
    python run_conformance.py                    # Run all tests
    python run_conformance.py --category branch  # Run specific category
    python run_conformance.py --tag smoke        # Run tagged tests
    python run_conformance.py --vector arith-iadd-basic  # Run specific vector
    python run_conformance.py --list             # List all test vectors
    python run_conformance.py --json             # Output results as JSON
"""

import argparse
import json
import os
import struct
import sys
import time
from dataclasses import dataclass, field
from typing import Dict, List, Optional

# Try to import flux-runtime
try:
    from flux.vm.interpreter import Interpreter
    HAS_FLUX_RUNTIME = True
except ImportError:
    HAS_FLUX_RUNTIME = False

try:
    from flux.bytecode.opcodes import Op
    HAS_OPCODES = True
except ImportError:
    HAS_OPCODES = False


@dataclass
class TestResult:
    """Result of running a single test vector."""
    vector_id: str
    category: str
    passed: bool
    actual_state: str = ""
    expected_state: str = ""
    details: str = ""
    duration_ms: float = 0.0
    error: Optional[str] = None
    register_mismatches: Dict = field(default_factory=dict)
    flag_mismatches: Dict = field(default_factory=dict)


class ConformanceRunner:
    """Run conformance test vectors against a FLUX VM implementation."""

    def __init__(self, vectors_dir: str):
        self.vectors_dir = vectors_dir
        self.vectors: List[dict] = []
        self.results: List[TestResult] = []
        self._load_vectors()

    def _load_vectors(self):
        """Load all test vectors from the vectors directory."""
        manifest_path = os.path.join(self.vectors_dir, "manifest.json")
        if os.path.exists(manifest_path):
            with open(manifest_path) as f:
                manifest = json.load(f)
            for category, vector_ids in manifest.get("categories", {}).items():
                for vid in vector_ids:
                    vpath = os.path.join(self.vectors_dir, f"{vid}.json")
                    if os.path.exists(vpath):
                        with open(vpath) as f:
                            self.vectors.append(json.load(f))
        else:
            # Load all JSON files directly
            for fname in sorted(os.listdir(self.vectors_dir)):
                if fname.endswith(".json") and fname != "manifest.json":
                    with open(os.path.join(self.vectors_dir, fname)) as f:
                        self.vectors.append(json.load(f))

    def list_vectors(self):
        """Print all loaded test vectors."""
        print(f"Loaded {len(self.vectors)} test vectors:\n")
        by_cat = {}
        for v in self.vectors:
            cat = v["category"]
            if cat not in by_cat:
                by_cat[cat] = []
            by_cat[cat].append(v)

        for cat in sorted(by_cat.keys()):
            print(f"  [{cat}] ({len(by_cat[cat])})")
            for v in by_cat[cat]:
                tags = " ".join(f"#{t}" for t in v.get("tags", []))
                print(f"    {v['id']:40s} {v['name'][:50]:50s} {tags}")
        print()

    def run_vector(self, vector: dict) -> TestResult:
        """Run a single test vector against the VM."""
        start = time.time()
        result = TestResult(
            vector_id=vector["id"],
            category=vector["category"],
            passed=False,
            expected_state=vector["expected"].get("final_state", "HALTED"),
        )

        if not HAS_FLUX_RUNTIME:
            result.error = "flux-runtime not installed"
            result.details = "Cannot run tests without flux.runtime Python package"
            result.duration_ms = (time.time() - start) * 1000
            return result

        try:
            # Parse bytecode
            bytecode_hex = vector["bytecode_hex"]
            bytecode = bytes.fromhex(bytecode_hex)

            # Create VM
            max_cycles = vector["expected"].get("max_cycles", 10000)
            vm = Interpreter(bytecode, memory_size=65536, max_cycles=max_cycles)

            # Apply preconditions
            preconditions = vector.get("preconditions", {})
            if preconditions:
                if "gp" in preconditions:
                    for reg_str, val in preconditions["gp"].items():
                        reg_idx = int(reg_str)
                        vm.regs.write_gp(reg_idx, val)
                if "fp" in preconditions:
                    for reg_str, val in preconditions["fp"].items():
                        reg_idx = int(reg_str)
                        vm.regs.write_fp(reg_idx, val)
                if "memory" in preconditions:
                    for region_name, offsets in preconditions["memory"].items():
                        region = vm.memory.get_region(region_name)
                        for offset_str, hex_val in offsets.items():
                            offset = int(offset_str)
                            data = bytes.fromhex(hex_val)
                            region.write(offset, data)

            # Set up A2A handler if needed
            if vector["category"] == "a2a":
                def a2a_handler(name, data):
                    return 0  # Return int (VM expects int result)
                vm.on_a2a(a2a_handler)

            # Execute
            vm.execute()

            # Determine actual state
            if vm.halted:
                result.actual_state = "HALTED"
            elif hasattr(vm, 'yielded') and vm.yielded:
                result.actual_state = "YIELDED"
            else:
                result.actual_state = "CYCLE_LIMIT"

            # Check final state
            expected_state = vector["expected"].get("final_state", "HALTED")
            if result.actual_state != expected_state:
                result.details = f"State mismatch: expected {expected_state}, got {result.actual_state}"
                if expected_state == "ERRORED":
                    # VM didn't error when it should have
                    pass
                elif result.actual_state != "HALTED":
                    pass
                else:
                    pass
                result.duration_ms = (time.time() - start) * 1000
                return result

            # If we expected ERRORED and got it, test passes
            if expected_state == "ERRORED":
                result.passed = True
                result.details = "Correctly entered error state"
                result.duration_ms = (time.time() - start) * 1000
                return result

            # Check GP registers
            expected_gp = vector["expected"].get("gp", {})
            for reg_str, expected_val in expected_gp.items():
                reg_idx = int(reg_str)
                actual_val = vm.regs.read_gp(reg_idx)
                if actual_val != expected_val:
                    result.register_mismatches[f"R{reg_idx}"] = {
                        "expected": expected_val,
                        "actual": actual_val,
                    }

            # Check FP registers
            expected_fp = vector["expected"].get("fp", {})
            for reg_str, expected_val in expected_fp.items():
                reg_idx = int(reg_str)
                actual_val = vm.regs.read_fp(reg_idx)
                if isinstance(expected_val, float):
                    # Float comparison with tolerance
                    if abs(actual_val - expected_val) > 1e-6:
                        result.register_mismatches[f"F{reg_idx}"] = {
                            "expected": expected_val,
                            "actual": actual_val,
                        }
                elif actual_val != expected_val:
                    result.register_mismatches[f"F{reg_idx}"] = {
                        "expected": expected_val,
                        "actual": actual_val,
                    }

            # Determine pass/fail
            if not result.register_mismatches and not result.flag_mismatches:
                result.passed = True
                result.details = "All checks passed"
            else:
                mismatches = []
                for reg, vals in result.register_mismatches.items():
                    mismatches.append(f"{reg}: expected {vals['expected']}, got {vals['actual']}")
                result.details = f"Register mismatches: {'; '.join(mismatches)}"

        except Exception as e:
            expected_state = vector["expected"].get("final_state", "HALTED")
            if expected_state == "ERRORED":
                result.passed = True
                result.actual_state = "ERRORED"
                error_type = vector["expected"].get("error_type", "")
                result.details = f"Correctly raised error: {type(e).__name__}"
            else:
                result.error = str(e)
                result.details = f"Unexpected error: {type(e).__name__}: {e}"

        result.duration_ms = (time.time() - start) * 1000
        return result

    def run_all(
        self,
        category: Optional[str] = None,
        tag: Optional[str] = None,
        vector_id: Optional[str] = None,
    ) -> List[TestResult]:
        """Run tests matching filters."""
        for v in self.vectors:
            if category and v["category"] != category:
                continue
            if tag and tag not in v.get("tags", []):
                continue
            if vector_id and v["id"] != vector_id:
                continue

            result = self.run_vector(v)
            self.results.append(result)

        return self.results

    def print_summary(self):
        """Print test results summary."""
        total = len(self.results)
        passed = sum(1 for r in self.results if r.passed)
        failed = total - passed
        total_time = sum(r.duration_ms for r in self.results)

        print(f"\n{'='*70}")
        print(f"FLUX Conformance Test Results")
        print(f"{'='*70}")
        print(f"Total:  {total}")
        print(f"Passed: {passed} ({100*passed//max(total,1)}%)")
        print(f"Failed: {failed} ({100*failed//max(total,1)}%)")
        print(f"Time:   {total_time:.1f}ms")
        print(f"{'='*70}")

        if failed > 0:
            print(f"\nFailed tests:")
            for r in self.results:
                if not r.passed:
                    status = "FAIL"
                    print(f"  [{status}] {r.vector_id}: {r.details}")
                    if r.error:
                        print(f"        Error: {r.error}")
                    if r.register_mismatches:
                        for reg, vals in r.register_mismatches.items():
                            print(f"        {reg}: expected={vals['expected']}, actual={vals['actual']}")
            print()

        return failed == 0

    def to_json(self) -> dict:
        """Serialize results as JSON."""
        return {
            "total": len(self.results),
            "passed": sum(1 for r in self.results if r.passed),
            "failed": sum(1 for r in self.results if not r.passed),
            "results": [
                {
                    "id": r.vector_id,
                    "category": r.category,
                    "passed": r.passed,
                    "expected_state": r.expected_state,
                    "actual_state": r.actual_state,
                    "details": r.details,
                    "duration_ms": round(r.duration_ms, 2),
                    "error": r.error,
                    "register_mismatches": r.register_mismatches,
                }
                for r in self.results
            ],
        }


def main():
    parser = argparse.ArgumentParser(description="FLUX Conformance Test Runner")
    parser.add_argument("--vectors-dir", default=None,
                        help="Directory containing test vectors (default: ../vectors)")
    parser.add_argument("--category", "-c", default=None,
                        help="Run only tests in this category")
    parser.add_argument("--tag", "-t", default=None,
                        help="Run only tests with this tag")
    parser.add_argument("--vector", "-v", default=None,
                        help="Run a specific test vector by ID")
    parser.add_argument("--list", "-l", action="store_true",
                        help="List all test vectors without running")
    parser.add_argument("--json", action="store_true",
                        help="Output results as JSON")
    parser.add_argument("--quiet", "-q", action="store_true",
                        help="Only show failures")
    args = parser.parse_args()

    # Determine vectors directory
    if args.vectors_dir:
        vectors_dir = args.vectors_dir
    else:
        # Default: ../vectors relative to this script
        script_dir = os.path.dirname(os.path.abspath(__file__))
        vectors_dir = os.path.join(script_dir, "..", "vectors")

    if not os.path.exists(vectors_dir):
        # Try alternate path
        vectors_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "vectors")

    if not os.path.exists(vectors_dir):
        print(f"Error: Vectors directory not found: {vectors_dir}", file=sys.stderr)
        sys.exit(1)

    runner = ConformanceRunner(vectors_dir)

    if args.list:
        runner.list_vectors()
        sys.exit(0)

    if not HAS_FLUX_RUNTIME:
        print("WARNING: flux-runtime not installed. Running in validation-only mode.")
        print("Install with: pip install -e /path/to/flux-runtime")
        print()

    # Run tests
    results = runner.run_all(
        category=args.category,
        tag=args.tag,
        vector_id=args.vector,
    )

    if not args.quiet:
        for r in results:
            status = "PASS" if r.passed else "FAIL"
            print(f"  [{status}] {r.vector_id:40s} {r.details[:60]}")

    if args.json:
        print(json.dumps(runner.to_json(), indent=2))
        sys.exit(0 if all(r.passed for r in results) else 1)

    success = runner.print_summary()
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
