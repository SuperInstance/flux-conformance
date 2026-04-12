#!/usr/bin/env python3
"""Cross-runtime conformance test runner.

Loads unified test vectors, runs them on the Python VM adapter,
optionally generates a Go test file, and produces a comparison
report in Markdown format.

Usage
-----
    python run_cross_conformance.py                        # full run + report
    python run_cross_conformance.py --python-only           # skip Go generation
    python run_cross_conformance.py --go-only               # only generate Go test
    python run_cross_conformance.py --report=cross_report.md
    python run_cross_conformance.py --filter arith --verbose
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure sibling modules are importable
_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from python_adapter import CrossRuntimeResult, PythonAdapter  # noqa: E402


# ===================================================================
#  Report generation
# ===================================================================

def _colored_status(passed: bool, skipped: bool = False) -> str:
    if skipped:
        return "\033[33mSKIP\033[0m"
    if passed:
        return "\033[32mPASS\033[0m"
    return "\033[31mFAIL\033[0m"


def _plain_status(passed: bool, skipped: bool = False) -> str:
    if skipped:
        return "SKIP"
    if passed:
        return "PASS"
    return "FAIL"


def generate_report(
    results: List[CrossRuntimeResult],
    vectors: List[dict],
    go_generated: bool = False,
    go_path: str = "",
) -> str:
    """Generate a Markdown conformance report.

    Parameters
    ----------
    results : list[CrossRuntimeResult]
        Results from the Python VM adapter.
    vectors : list[dict]
        Original test vectors.
    go_generated : bool
        Whether a Go test file was also generated.
    go_path : str
        Path to the generated Go test file.

    Returns
    -------
    str
        Complete Markdown report.
    """
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    lines: List[str] = []

    # -- Header --------------------------------------------------------
    lines.append("# Cross-Runtime Conformance Report")
    lines.append("")
    lines.append(f"**Generated:** {now}")
    lines.append(f"**Python runtime:** CPython (FluxMiniVM)")
    if go_generated:
        lines.append(f"**Go test file:** `{go_path}`")
    else:
        lines.append("**Go test file:** not generated (use `--go-only` or omit `--python-only`)")
    lines.append("")

    # -- Summary -------------------------------------------------------
    total = len(results)
    ran = [r for r in results if not r.skipped]
    skipped = [r for r in results if r.skipped]
    passed = sum(1 for r in ran if r.passed)
    failed = sum(1 for r in ran if not r.passed)

    lines.append("## Summary")
    lines.append("")
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Total vectors | {total} |")
    lines.append(f"| Executed | {len(ran)} |")
    lines.append(f"| Skipped | {len(skipped)} |")
    lines.append(f"| **Passed** | **{passed}** |")
    lines.append(f"| **Failed** | **{failed}** |")
    lines.append(f"| Pass rate | {passed * 100 // max(len(ran), 1)}% |")
    lines.append("")

    # -- Category breakdown --------------------------------------------
    categories: Dict[str, List[CrossRuntimeResult]] = {}
    for r in results:
        # Find the vector to get its category
        cat = "unknown"
        for v in vectors:
            if v.get("name") == r.name:
                cat = v.get("category", "unknown")
                break
        categories.setdefault(cat, []).append(r)

    lines.append("## Results by Category")
    lines.append("")
    lines.append("| Category | Total | Passed | Failed | Skipped |")
    lines.append("|----------|-------|--------|--------|---------|")
    for cat in sorted(categories):
        items = categories[cat]
        c_ran = [x for x in items if not x.skipped]
        c_skip = [x for x in items if x.skipped]
        c_pass = sum(1 for x in c_ran if x.passed)
        c_fail = sum(1 for x in c_ran if not x.passed)
        lines.append(
            f"| {cat} | {len(items)} | {c_pass} | {c_fail} | {len(c_skip)} |"
        )
    lines.append("")

    # -- Detailed results table ----------------------------------------
    lines.append("## Detailed Results")
    lines.append("")
    lines.append("| # | Name | Category | Python | Details |")
    lines.append("|---|------|----------|--------|---------|")

    for i, r in enumerate(results, 1):
        status = _plain_status(r.passed, r.skipped)
        detail = ""
        if r.skipped:
            detail = r.skip_reason
        elif not r.passed:
            detail = r.details if r.details else "see above"
        elif r.elapsed_us > 1000:
            detail = f"{r.elapsed_us/1000:.1f} ms, {r.insn_count} insns"
        else:
            detail = f"{r.elapsed_us:.0f} us, {r.insn_count} insns"

        # Find category
        cat = ""
        for v in vectors:
            if v.get("name") == r.name:
                cat = v.get("category", "")
                break

        lines.append(f"| {i} | `{r.name}` | {cat} | {status} | {detail} |")
    lines.append("")

    # -- Failure details (if any) --------------------------------------
    failures = [r for r in results if not r.passed and not r.skipped]
    if failures:
        lines.append("## Failures")
        lines.append("")
        for r in failures:
            lines.append(f"### `{r.name}`")
            lines.append("")
            lines.append(f"- **Halted:** expected={r.expected_halted}, actual={r.halted}")
            lines.append(f"- **Error:** expected={r.expected_error}, actual={r.error}")
            if r.register_mismatches:
                lines.append("- **Register mismatches:**")
                for key, exp, act in r.register_mismatches:
                    lines.append(f"  - `{key}`: expected `{exp}`, got `{act}`")
            lines.append("")

    # -- Go test instructions ------------------------------------------
    if go_generated and go_path:
        lines.append("## Go Runtime Testing")
        lines.append("")
        lines.append("To run the cross-runtime tests on the Go VM:")
        lines.append("")
        lines.append("```bash")
        lines.append(f"# Copy the generated test file to your Go module")
        lines.append(f"cp {go_path} <go-module-root>/pkg/vm/flux_vm_test.go")
        lines.append("")
        lines.append("# Run the tests")
        lines.append("cd <go-module-root> && go test -v -run TestCrossRuntime ./pkg/vm/")
        lines.append("```")
        lines.append("")
        lines.append("The Go VM must implement the following interface:")
        lines.append("")
        lines.append("```go")
        lines.append("type VM interface {")
        lines.append("    New() VM")
        lines.append("    Load(code []byte)")
        lines.append("    Run()")
        lines.append("    Halted() bool")
        lines.append("    Error() bool")
        lines.append("    GetReg(idx int) int32")
        lines.append("    SetReg(idx int, val int)")
        lines.append("}")
        lines.append("```")
        lines.append("")

    return "\n".join(lines)


# ===================================================================
#  Comparison table (terminal)
# ===================================================================

def print_comparison_table(results: List[CrossRuntimeResult]) -> None:
    """Print a terminal-friendly comparison table."""
    print()
    print(f"  {'#':>3}  {'Name':<40}  {'Cat':<12}  {'Status':<6}  {'Detail'}")
    print(f"  {'---':>3}  {'----':<40}  {'---':<12}  {'------':<6}  {'------'}")

    for i, r in enumerate(results, 1):
        status = _colored_status(r.passed, r.skipped)
        detail = ""
        if r.skipped:
            detail = r.skip_reason
        elif not r.passed:
            detail = r.details[:50] if r.details else ""
        else:
            detail = f"{r.elapsed_us:.0f}us {r.insn_count}insns"

        # Truncate name for display
        name = r.name[:40]
        cat = getattr(r, 'category', '')[:12]

        print(f"  {i:>3}  {name:<40}  {cat:<12}  {status:<17}  {detail}")

    print()


# ===================================================================
#  Vector loading
# ===================================================================

def _load_vectors(path: str) -> Tuple[List[dict], str]:
    """Load vectors from JSON, returning (vectors_list, resolved_path)."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    vectors = data.get("vectors", data) if isinstance(data, dict) else data
    return vectors, str(Path(path).resolve())


def _find_vectors() -> str:
    """Auto-detect the vectors JSON file."""
    candidates = [
        Path(__file__).parent / "unified_test_vectors.json",
        Path.cwd() / "unified_test_vectors.json",
        Path.cwd() / "cross_runtime" / "unified_test_vectors.json",
    ]
    for c in candidates:
        if c.is_file():
            return str(c)
    return ""


# ===================================================================
#  CLI
# ===================================================================

def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(
        prog="run_cross_conformance.py",
        description="Cross-runtime conformance test runner for FLUX Unified ISA",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""\
examples:
  %(prog)s                                 # full run (Python + Go gen + report)
  %(prog)s --python-only                   # Python only, skip Go generation
  %(prog)s --go-only                       # only generate Go test file
  %(prog)s --report=cross_report.md        # custom report path
  %(prog)s --filter arith --verbose        # filter + verbose
""",
    )
    parser.add_argument(
        "--vectors", default=None,
        help="Path to unified_test_vectors.json (default: auto-detect)",
    )
    parser.add_argument(
        "--python-only", action="store_true",
        help="Run only the Python adapter, skip Go test generation",
    )
    parser.add_argument(
        "--go-only", action="store_true",
        help="Only generate the Go test file, skip Python execution",
    )
    parser.add_argument(
        "--report", "-r", default=None,
        help="Output path for the Markdown report (default: stdout only)",
    )
    parser.add_argument(
        "--go-output", default=None,
        help="Output path for the generated Go test file",
    )
    parser.add_argument(
        "--filter", default=None,
        help="Only run tests whose name contains this substring",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true",
        help="Show disassembly and register dumps",
    )
    parser.add_argument(
        "--include-slow", action="store_true",
        help="Run slow-tagged tests (e.g. cycle-limit)",
    )
    parser.add_argument(
        "--pkg-path", default="github.com/flux-labs/flux/pkg/vm",
        help="Go import path for the VM package (for Go test generation)",
    )
    args = parser.parse_args(argv)

    # Locate vectors
    vectors_path = args.vectors or _find_vectors()
    if not vectors_path:
        print("ERROR: cannot find unified_test_vectors.json", file=sys.stderr)
        print("  Set --vectors <path> or run from the cross_runtime/ directory.",
              file=sys.stderr)
        return 1

    vectors, resolved_path = _load_vectors(vectors_path)

    # Apply filter
    if args.filter:
        fl = args.filter.lower()
        vectors = [v for v in vectors if fl in v.get("name", "").lower()]

    # -- Banner --------------------------------------------------------
    print("=" * 64)
    print("  FLUX Cross-Runtime Conformance Test Runner")
    print("=" * 64)
    print(f"  vectors     : {resolved_path}")
    print(f"  count       : {len(vectors)}")
    print(f"  python-only : {args.python_only}")
    print(f"  go-only     : {args.go_only}")
    print(f"  verbose     : {args.verbose}")
    print(f"  include-slow: {args.include_slow}")
    print()

    # -- Go-only mode --------------------------------------------------
    if args.go_only:
        from go_adapter import GoAdapter
        go_output = args.go_output or str(
            _SCRIPT_DIR / "flux_vm_test.go"
        )
        adapter = GoAdapter(pkg_import=args.pkg_path)
        written = adapter.generate_and_write(vectors, go_output)
        print(f"  Generated Go test: {written}")
        print(f"  Vectors: {len(vectors)}")
        return 0

    # -- Python execution ----------------------------------------------
    print("  --- Python VM Adapter ---")
    print()

    py_adapter = PythonAdapter(
        verbose=args.verbose,
        skip_slow=not args.include_slow,
    )
    py_results = py_adapter.run_all(vectors)

    # -- Summary -------------------------------------------------------
    ran = [r for r in py_results if not r.skipped]
    skipped = [r for r in py_results if r.skipped]
    passed = sum(1 for r in ran if r.passed)
    failed = sum(1 for r in ran if not r.passed)

    print_comparison_table(py_results)

    print(f"  Python results: {passed} passed, {failed} failed, "
          f"{len(skipped)} skipped (of {len(py_results)} total)")
    print()

    # -- Go generation -------------------------------------------------
    go_generated = False
    go_path = ""
    if not args.python_only:
        print("  --- Go Test Generation ---")
        print()
        try:
            from go_adapter import GoAdapter
            go_output = args.go_output or str(
                _SCRIPT_DIR / "flux_vm_test.go"
            )
            go_adapter = GoAdapter(pkg_import=args.pkg_path)
            go_path = go_adapter.generate_and_write(vectors, go_output)
            go_generated = True
            print(f"  Generated: {go_path}")
            print(f"  Vectors:  {len(vectors)}")
        except Exception as exc:
            print(f"  ERROR generating Go test: {exc}", file=sys.stderr)
            go_generated = False
        print()

    # -- Markdown report -----------------------------------------------
    if args.report:
        report = generate_report(
            results=py_results,
            vectors=vectors,
            go_generated=go_generated,
            go_path=go_path,
        )
        report_path = Path(args.report)
        report_path.parent.mkdir(parents=True, exist_ok=True)
        report_path.write_text(report, encoding="utf-8")
        print(f"  Report written to: {report_path}")
        print()

    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
