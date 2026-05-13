"""FLUX Cross-Runtime Conformance Test Suite — Main Runner.

Runs all bytecode fixtures against every available FLUX runtime
and reports conformance results.

Usage:
    pytest conformance_suite.py -v
    pytest conformance_suite.py --runtimes python,c -v
    pytest conformance_suite.py --report conformance_report.md
"""

import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional

import pytest

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent))

from runtime_adapters.abstract_adapter import (
    AbstractRuntimeAdapter,
    BytecodeProgram,
    ExecutionResult,
    ExecutionStatus,
    RegisterState,
)
from runtime_adapters.python_adapter import PythonRuntimeAdapter
from runtime_adapters.c_adapter import CRuntimeAdapter
from bytecode_fixtures import ALL_FIXTURES


def discover_runtimes() -> List[AbstractRuntimeAdapter]:
    """Discover all available FLUX runtime implementations."""
    adapters: List[AbstractRuntimeAdapter] = []

    # Try Python runtime
    python_adapter = PythonRuntimeAdapter()
    if python_adapter.health_check():
        adapters.append(python_adapter)

    # Try C runtime
    c_adapter = CRuntimeAdapter()
    if c_adapter.health_check():
        adapters.append(c_adapter)

    return adapters


def run_fixture_against_runtime(
    fixture: BytecodeProgram,
    adapter: AbstractRuntimeAdapter,
) -> Dict:
    """Run a single fixture against a single runtime and return results."""
    result = adapter.execute(fixture)

    # Check if the opcodes used are supported
    unsupported = set(fixture.opcodes_used) - adapter.supported_opcodes
    if unsupported:
        return {
            "fixture": fixture.name,
            "runtime": adapter.runtime_name,
            "status": "skipped",
            "reason": f"Unsupported opcodes: {[f'0x{o:02x}' for o in sorted(unsupported)]}",
        }

    # Verify expected results
    passed = True
    failures = []

    if result.status != fixture.expected_status:
        # Allow UNSUPPORTED as a pass if the expected was ERROR
        if not (result.status == ExecutionStatus.UNSUPPORTED and
                fixture.expected_status == ExecutionStatus.ERROR):
            passed = False
            failures.append(
                f"Status: expected {fixture.expected_status.value}, "
                f"got {result.status.value}"
            )

    if fixture.expected_registers and result.status == ExecutionStatus.HALT:
        for reg, expected_val in fixture.expected_registers.int_regs.items():
            actual_val = result.registers.int_regs.get(reg)
            if actual_val != expected_val:
                passed = False
                failures.append(
                    f"R{reg}: expected {expected_val}, got {actual_val}"
                )

    return {
        "fixture": fixture.name,
        "runtime": adapter.runtime_name,
        "status": "passed" if passed else "failed",
        "failures": failures,
        "execution_status": result.status.value,
        "cycles": result.cycles,
    }


def generate_conformance_report(results: List[Dict], output_path: str) -> None:
    """Generate a markdown conformance report."""
    runtimes = sorted(set(r["runtime"] for r in results))
    fixtures = sorted(set(r["fixture"] for r in results))

    # Group results by fixture
    by_fixture: Dict[str, Dict[str, Dict]] = {}
    for r in results:
        by_fixture.setdefault(r["fixture"], {})[r["runtime"]] = r

    lines = [
        "# FLUX Cross-Runtime Conformance Report",
        "",
        f"Generated: {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}",
        "",
        f"**Runtimes tested:** {len(runtimes)}",
        f"**Fixtures tested:** {len(fixtures)}",
        "",
    ]

    # Summary table
    lines.append("## Summary")
    lines.append("")
    lines.append("| Runtime | Passed | Failed | Skipped | Coverage |")
    lines.append("|---------|--------|--------|---------|----------|")

    for rt in runtimes:
        rt_results = [r for r in results if r["runtime"] == rt]
        passed = sum(1 for r in rt_results if r["status"] == "passed")
        failed = sum(1 for r in rt_results if r["status"] == "failed")
        skipped = sum(1 for r in rt_results if r["status"] == "skipped")
        total = len(rt_results)
        coverage = f"{passed/max(total,1)*100:.0f}%"
        lines.append(f"| {rt} | {passed} | {failed} | {skipped} | {coverage} |")

    lines.append("")

    # Detailed results per fixture
    lines.append("## Detailed Results")
    lines.append("")

    for fixture_name in fixtures:
        lines.append(f"### {fixture_name}")
        lines.append("")
        fixture_results = by_fixture.get(fixture_name, {})
        for rt_name, r in fixture_results.items():
            status_emoji = {
                "passed": "✅",
                "failed": "❌",
                "skipped": "⏭️",
            }.get(r["status"], "❓")
            lines.append(f"- {status_emoji} **{rt_name}**: {r['status']}")
            if r.get("failures"):
                for f in r["failures"]:
                    lines.append(f"  - {f}")
            if r.get("reason"):
                lines.append(f"  - Reason: {r['reason']}")
        lines.append("")

    # Opcode coverage
    lines.append("## Opcode Coverage")
    lines.append("")
    all_opcodes = set()
    for fixture in ALL_FIXTURES:
        all_opcodes.update(fixture.opcodes_used)
    lines.append(f"Opcodes exercised by test suite: {len(all_opcodes)}")
    lines.append(f"Opcodes: {', '.join(f'0x{o:02x}' for o in sorted(all_opcodes))}")
    lines.append("")

    with open(output_path, "w") as f:
        f.write("\n".join(lines))


# Pytest fixtures
@pytest.fixture(params=discover_runtimes(), ids=lambda a: a.runtime_name)
def adapter(request):
    """Parametrized fixture providing each available runtime adapter."""
    return request.param


class TestConformanceSuite:
    """Main conformance test class — runs all fixtures against all runtimes."""

    @pytest.mark.parametrize("fixture", ALL_FIXTURES, ids=lambda f: f.name)
    def test_fixture_against_runtime(self, adapter, fixture):
        """Run each fixture against each available runtime."""
        result = run_fixture_against_runtime(fixture, adapter)

        if result["status"] == "skipped":
            pytest.skip(result.get("reason", "Unsupported opcodes"))

        if result["status"] == "failed":
            failures = result.get("failures", [])
            pytest.fail(f"Conformance failure: {'; '.join(failures)}")

        assert result["status"] == "passed"


class TestOpcodeCoverage:
    """Verify that the test suite covers key opcode categories."""

    def test_control_flow_opcodes_covered(self):
        """JMP, JZ, JNZ, CALL, RET must be in at least one fixture."""
        all_opcodes = set()
        for f in ALL_FIXTURES:
            all_opcodes.update(f.opcodes_used)

        required = {0x04, 0x05, 0x06, 0x07, 0x28}  # JMP, JZ, JNZ, CALL, RET
        missing = required - all_opcodes
        assert not missing, f"Missing required control flow opcodes: {missing}"

    def test_arithmetic_opcodes_covered(self):
        """IADD, ISUB, IMUL, IDIV must be in at least one fixture."""
        all_opcodes = set()
        for f in ALL_FIXTURES:
            all_opcodes.update(f.opcodes_used)

        required = {0x08, 0x09, 0x0A, 0x0B}  # IADD, ISUB, IMUL, IDIV
        missing = required - all_opcodes
        assert not missing, f"Missing required arithmetic opcodes: {missing}"

    def test_stack_opcodes_covered(self):
        """PUSH, POP must be in at least one fixture."""
        all_opcodes = set()
        for f in ALL_FIXTURES:
            all_opcodes.update(f.opcodes_used)

        required = {0x20, 0x21}  # PUSH, POP
        missing = required - all_opcodes
        assert not missing, f"Missing required stack opcodes: {missing}"

    def test_halt_is_always_used(self):
        """Every fixture must end with HALT (0x80)."""
        for fixture in ALL_FIXTURES:
            assert 0x80 in fixture.opcodes_used, f"Fixture {fixture.name} missing HALT"


if __name__ == "__main__":
    # Run as script for quick conformance check
    adapters = discover_runtimes()
    if not adapters:
        print("No FLUX runtimes available. Install flux-runtime or flux-runtime-c.")
        sys.exit(1)

    print(f"Discovered {len(adapters)} runtime(s):")
    for a in adapters:
        print(f"  - {a.runtime_name} v{a.runtime_version}")

    print(f"\nRunning {len(ALL_FIXTURES)} fixtures...")
    all_results = []

    for adapter in adapters:
        for fixture in ALL_FIXTURES:
            result = run_fixture_against_runtime(fixture, adapter)
            all_results.append(result)
            status = result["status"]
            emoji = {"passed": "✅", "failed": "❌", "skipped": "⏭️"}.get(status, "❓")
            print(f"  {emoji} {fixture.name} @ {adapter.runtime_name}: {status}")
            if result.get("failures"):
                for f in result["failures"]:
                    print(f"     {f}")

    # Generate report
    report_path = os.path.join(os.path.dirname(__file__), "conformance_report.md")
    generate_conformance_report(all_results, report_path)
    print(f"\nReport saved to: {report_path}")
