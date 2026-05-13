"""FLUX Conformance Report Generator.

Reads conformance test results and produces a Markdown report showing
which opcodes/features each runtime supports.  The report includes:

1. A per-runtime summary (pass/fail/skip counts).
2. A cross-runtime conformance matrix (test × runtime).
3. A detailed opcode coverage table.
4. A list of failing tests with diagnostic information.

Usage::

    from conformance_report import ConformanceReporter
    from conformance_suite import ConformanceRunner, ConformanceResult

    runner = ConformanceRunner()
    # ... run tests ...

    reporter = ConformanceReporter(runner.get_results())
    report = reporter.generate_markdown()
    print(report)

    # Or write to file:
    reporter.write_report("conformance_report.md")
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, TextIO

from conformance_suite import ConformanceResult, TestVerdict
from runtime_adapters.python_adapter import FluxOpcode


# ===================================================================
# Opcode groupings for the coverage table
# ===================================================================

OPCODE_GROUPS: Dict[str, List[tuple[str, int]]] = {
    "Control (0x00-0x07)": [
        ("NOP", FluxOpcode.NOP), ("MOV", FluxOpcode.MOV),
        ("LOAD", FluxOpcode.LOAD), ("STORE", FluxOpcode.STORE),
        ("JMP", FluxOpcode.JMP), ("JZ", FluxOpcode.JZ),
        ("JNZ", FluxOpcode.JNZ), ("CALL", FluxOpcode.CALL),
    ],
    "Int Arithmetic (0x08-0x0F)": [
        ("IADD", FluxOpcode.IADD), ("ISUB", FluxOpcode.ISUB),
        ("IMUL", FluxOpcode.IMUL), ("IDIV", FluxOpcode.IDIV),
        ("IMOD", FluxOpcode.IMOD), ("INEG", FluxOpcode.INEG),
        ("INC", FluxOpcode.INC), ("DEC", FluxOpcode.DEC),
    ],
    "Bitwise (0x10-0x17)": [
        ("IAND", FluxOpcode.IAND), ("IOR", FluxOpcode.IOR),
        ("IXOR", FluxOpcode.IXOR), ("INOT", FluxOpcode.INOT),
        ("ISHL", FluxOpcode.ISHL), ("ISHR", FluxOpcode.ISHR),
        ("ROTL", FluxOpcode.ROTL), ("ROTR", FluxOpcode.ROTR),
    ],
    "Compare (0x18-0x1F)": [
        ("ICMP", FluxOpcode.ICMP), ("IEQ", FluxOpcode.IEQ),
        ("ILT", FluxOpcode.ILT), ("ILE", FluxOpcode.ILE),
        ("IGT", FluxOpcode.IGT), ("IGE", FluxOpcode.IGE),
        ("TEST", FluxOpcode.TEST), ("SETCC", FluxOpcode.SETCC),
    ],
    "Stack (0x20-0x27)": [
        ("PUSH", FluxOpcode.PUSH), ("POP", FluxOpcode.POP),
        ("DUP", FluxOpcode.DUP), ("SWAP", FluxOpcode.SWAP),
        ("ROT", FluxOpcode.ROT), ("ENTER", FluxOpcode.ENTER),
        ("LEAVE", FluxOpcode.LEAVE), ("ALLOCA", FluxOpcode.ALLOCA),
    ],
    "Function (0x28-0x2F)": [
        ("RET", FluxOpcode.RET), ("CALL_IND", FluxOpcode.CALL_IND),
        ("TAILCALL", FluxOpcode.TAILCALL), ("MOVI", FluxOpcode.MOVI),
        ("IREM", FluxOpcode.IREM), ("CMP", FluxOpcode.CMP),
        ("JE", FluxOpcode.JE), ("JNE", FluxOpcode.JNE),
    ],
    "Memory/Region (0x30-0x37)": [
        ("REGION_CREATE", FluxOpcode.REGION_CREATE),
        ("REGION_DESTROY", FluxOpcode.REGION_DESTROY),
        ("REGION_TRANSFER", FluxOpcode.REGION_TRANSFER),
        ("MEMCOPY", FluxOpcode.MEMCOPY),
        ("MEMSET", FluxOpcode.MEMSET),
        ("MEMCMP", FluxOpcode.MEMCMP),
    ],
    "Type (0x38-0x3F)": [
        ("CAST", FluxOpcode.CAST), ("BOX", FluxOpcode.BOX),
        ("UNBOX", FluxOpcode.UNBOX), ("CHECK_TYPE", FluxOpcode.CHECK_TYPE),
        ("CHECK_BOUNDS", FluxOpcode.CHECK_BOUNDS),
    ],
    "Float (0x40-0x4B)": [
        ("FADD", FluxOpcode.FADD), ("FSUB", FluxOpcode.FSUB),
        ("FMUL", FluxOpcode.FMUL), ("FDIV", FluxOpcode.FDIV),
        ("FNEG", FluxOpcode.FNEG), ("FABS", FluxOpcode.FABS),
        ("FCMPEQ", FluxOpcode.FCMPEQ), ("FLT", FluxOpcode.FLT),
        ("FLE", FluxOpcode.FLE), ("FGT", FluxOpcode.FGT),
        ("FGE", FluxOpcode.FGE),
    ],
    "SIMD (0x4C-0x53)": [
        ("VLOAD", FluxOpcode.VLOAD), ("VSTORE", FluxOpcode.VSTORE),
        ("VADD", FluxOpcode.VADD), ("VSUB", FluxOpcode.VSUB),
        ("VMUL", FluxOpcode.VMUL), ("VDIV", FluxOpcode.VDIV),
        ("VFMA", FluxOpcode.VFMA),
    ],
    "A2A (0x60-0x6F)": [
        ("TELL", FluxOpcode.TELL), ("ASK", FluxOpcode.ASK),
        ("DELEGATE", FluxOpcode.DELEGATE), ("BROADCAST", FluxOpcode.BROADCAST),
        ("TRUST", FluxOpcode.TRUST), ("CAP", FluxOpcode.CAP),
        ("BARRIER", FluxOpcode.BARRIER), ("SHARE", FluxOpcode.SHARE),
        ("REVOKE", FluxOpcode.REVOKE),
    ],
    "Confidence (0x70-0x7B)": [
        ("C_TELL", FluxOpcode.C_TELL), ("C_ASK", FluxOpcode.C_ASK),
        ("C_DELEGATE", FluxOpcode.C_DELEGATE),
        ("C_BROADCAST", FluxOpcode.C_BROADCAST),
        ("C_TRUST", FluxOpcode.C_TRUST), ("C_CAP", FluxOpcode.C_CAP),
        ("C_SHARE", FluxOpcode.C_SHARE), ("C_REVOKE", FluxOpcode.C_REVOKE),
        ("C_ADD", FluxOpcode.C_ADD), ("C_SUB", FluxOpcode.C_SUB),
        ("C_MUL", FluxOpcode.C_MUL), ("C_MOV", FluxOpcode.C_MOV),
    ],
    "System (0x80-0x84)": [
        ("HALT", FluxOpcode.HALT), ("YIELD", FluxOpcode.YIELD),
        ("RESOURCE_ACQUIRE", FluxOpcode.RESOURCE_ACQUIRE),
        ("RESOURCE_RELEASE", FluxOpcode.RESOURCE_RELEASE),
        ("DEBUG_BREAK", FluxOpcode.DEBUG_BREAK),
    ],
}


class ConformanceReporter:
    """Generate Markdown conformance reports from test results."""

    def __init__(
        self,
        results: Sequence[ConformanceResult],
        *,
        runtime_info: Optional[Dict[str, Dict[str, Any]]] = None,
        supported_opcodes: Optional[Dict[str, set[int]]] = None,
    ) -> None:
        self._results = list(results)
        self._runtime_info = runtime_info or {}
        self._supported_opcodes = supported_opcodes or {}

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate_markdown(self) -> str:
        """Return the full conformance report as a Markdown string."""
        lines: List[str] = []
        self._write_header(lines)
        self._write_summary(lines)
        self._write_matrix(lines)
        self._write_opcode_coverage(lines)
        self._write_failures(lines)
        return "\n".join(lines)

    def write_report(self, path: str) -> None:
        """Write the report to *path*."""
        report = self.generate_markdown()
        with open(path, "w", encoding="utf-8") as fh:
            fh.write(report)

    # ------------------------------------------------------------------
    # Sections
    # ------------------------------------------------------------------

    def _write_header(self, lines: List[str]) -> None:
        """Report header with timestamp."""
        now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
        lines.append("# FLUX ISA v1.0 Conformance Report")
        lines.append("")
        lines.append(f"**Generated**: {now}")
        lines.append("")

    def _write_summary(self, lines: List[str]) -> None:
        """Per-runtime summary table."""
        lines.append("## Summary")
        lines.append("")

        runtimes = sorted({r.runtime_name for r in self._results})

        lines.append("| Runtime | Passed | Failed | Skipped | Error | Total |")
        lines.append("|---------|--------|--------|---------|-------|-------|")

        for rt in runtimes:
            rt_results = [r for r in self._results if r.runtime_name == rt]
            passed = sum(1 for r in rt_results if r.verdict == TestVerdict.PASS)
            failed = sum(1 for r in rt_results if r.verdict == TestVerdict.FAIL)
            skipped = sum(1 for r in rt_results if r.verdict == TestVerdict.SKIP)
            errors = sum(1 for r in rt_results if r.verdict == TestVerdict.ERROR)
            total = len(rt_results)
            lines.append(
                f"| {rt} | {passed} | {failed} | {skipped} | {errors} | {total} |"
            )

        lines.append("")

    def _write_matrix(self, lines: List[str]) -> None:
        """Cross-runtime conformance matrix."""
        lines.append("## Conformance Matrix")
        lines.append("")

        runtimes = sorted({r.runtime_name for r in self._results})
        test_names = list(dict.fromkeys(r.test_name for r in self._results))

        if not test_names or not runtimes:
            lines.append("_No results to display._")
            lines.append("")
            return

        # Header row
        header = "| Test | " + " | ".join(runtimes) + " |"
        sep = "|------|" + "|".join(["------" for _ in runtimes]) + "|"
        lines.append(header)
        lines.append(sep)

        verdict_symbols = {
            TestVerdict.PASS: "✅",
            TestVerdict.FAIL: "❌",
            TestVerdict.SKIP: "⏭️",
            TestVerdict.NOT_IMPLEMENTED: "⚪",
            TestVerdict.ERROR: "💥",
            TestVerdict.TIMEOUT: "⏱️",
        }

        for name in test_names:
            cells = [name]
            for rt in runtimes:
                matching = [
                    r for r in self._results
                    if r.test_name == name and r.runtime_name == rt
                ]
                if matching:
                    cells.append(verdict_symbols.get(matching[0].verdict, "?"))
                else:
                    cells.append("—")
            lines.append("| " + " | ".join(cells) + " |")

        lines.append("")

    def _write_opcode_coverage(self, lines: List[str]) -> None:
        """Opcode coverage table per runtime."""
        lines.append("## Opcode Coverage")
        lines.append("")

        runtimes = sorted(self._supported_opcodes.keys())
        if not runtimes:
            lines.append("_No opcode coverage data available._")
            lines.append("")
            return

        for group_name, opcodes in OPCODE_GROUPS.items():
            lines.append(f"### {group_name}")
            lines.append("")

            header = "| Opcode | " + " | ".join(runtimes) + " |"
            sep = "|--------|" + "|".join(["------" for _ in runtimes]) + "|"
            lines.append(header)
            lines.append(sep)

            for op_name, op_code in opcodes:
                cells = [f"`{op_name}` (0x{op_code:02X})"]
                for rt in runtimes:
                    supported = op_code in self._supported_opcodes.get(rt, set())
                    cells.append("✅" if supported else "❌")
                lines.append("| " + " | ".join(cells) + " |")

            lines.append("")

    def _write_failures(self, lines: List[str]) -> None:
        """Detailed failure list."""
        failures = [
            r for r in self._results
            if r.verdict in (TestVerdict.FAIL, TestVerdict.ERROR)
        ]

        lines.append("## Failures")
        lines.append("")

        if not failures:
            lines.append("_No failures detected._")
            lines.append("")
            return

        for f in failures:
            lines.append(f"### {f.test_name} [{f.runtime_name}]")
            lines.append("")
            lines.append(f"- **Verdict**: {f.verdict.value}")
            lines.append(f"- **Message**: {f.message}")
            if f.execution_result is not None:
                lines.append(f"- **Status**: {f.execution_result.status.value}")
                lines.append(f"- **Cycles**: {f.execution_result.cycles}")
                if f.execution_result.error_message:
                    lines.append(
                        f"- **Error**: {f.execution_result.error_message}"
                    )
            lines.append(f"- **Elapsed**: {f.elapsed_ms:.1f} ms")
            lines.append("")
