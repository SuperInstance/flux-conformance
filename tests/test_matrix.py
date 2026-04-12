"""Comprehensive tests for the FLUX Cross-Language Conformance Matrix.

Tests cover:
1. Data models (OpcodeDef, ImplementationDef, TestCoverageEntry)
2. ImplementationRegistry (registration, queries, seed data)
3. ConformanceMatrix (build, filter, cross-impl analysis)
4. CoverageAnalyzer (stats, untested, failing, summaries)
5. GapReporter (per-impl gaps, category gaps, format gaps, priority)
6. ConformanceScore (ISA, category, format, test, composite, ranking)
7. MatrixExporter (Markdown, JSON, CSV, dict)
8. Edge cases and error handling
"""

import json

import pytest

from flux_conformance.matrix import (
    Category,
    ConformanceMatrix,
    ConformanceScore,
    CoverageAnalyzer,
    Format,
    GapReporter,
    ImplementationDef,
    ImplementationRegistry,
    MatrixExporter,
    OpcodeDef,
    TestCoverageEntry,
    PYTHON_OPCODES,
    PYTHON_OPCODE_MAP,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def registry() -> ImplementationRegistry:
    """Return a registry seeded with all 4 default implementations."""
    return ImplementationRegistry.seed_default()


@pytest.fixture
def empty_registry() -> ImplementationRegistry:
    """Return an empty registry."""
    return ImplementationRegistry()


# ===========================================================================
# 1. Data Model Tests
# ===========================================================================

class TestOpcodeDef:
    """Tests for OpcodeDef data model."""

    def test_create_basic(self) -> None:
        op = OpcodeDef(0x00, "HALT", Format.A, Category.SYSTEM, "Halt execution")
        assert op.code == 0x00
        assert op.mnemonic == "HALT"
        assert op.format == Format.A
        assert op.category == Category.SYSTEM
        assert op.description == "Halt execution"

    def test_frozen(self) -> None:
        op = OpcodeDef(0x01, "NOP", Format.A, Category.SYSTEM)
        with pytest.raises(AttributeError):
            op.code = 0x99  # type: ignore[misc]

    def test_hashable(self) -> None:
        op1 = OpcodeDef(0x01, "NOP", Format.A, Category.SYSTEM)
        op2 = OpcodeDef(0x01, "NOP", Format.A, Category.SYSTEM)
        assert hash(op1) == hash(op2)
        assert op1 == op2

    def test_default_description(self) -> None:
        op = OpcodeDef(0x02, "RET", Format.A, Category.SYSTEM)
        assert op.description == ""

    def test_all_formats(self) -> None:
        for fmt in Format:
            op = OpcodeDef(0x00, "TEST", fmt, Category.SYSTEM)
            assert op.format == fmt

    def test_all_categories(self) -> None:
        for cat in Category:
            op = OpcodeDef(0x00, "TEST", Format.A, cat)
            assert op.category == cat


class TestImplementationDef:
    """Tests for ImplementationDef data model."""

    def test_create_minimal(self) -> None:
        impl = ImplementationDef(name="test-vm", language="Rust")
        assert impl.name == "test-vm"
        assert impl.language == "Rust"
        assert impl.version == "0.0.0"
        assert impl.opcode_codes == set()
        assert impl.supported_formats == set()

    def test_create_full(self) -> None:
        impl = ImplementationDef(
            name="flux-runtime",
            language="Python",
            repo="github.com/flux-lang/flux-runtime",
            version="2.1.0",
            opcode_codes={0x00, 0x01, 0x02},
            supported_formats={Format.A, Format.B},
            supported_categories={Category.SYSTEM},
        )
        assert len(impl.opcode_codes) == 3
        assert Format.A in impl.supported_formats

    def test_mutable(self) -> None:
        impl = ImplementationDef(name="test", language="Test")
        impl.opcode_codes.add(0x00)
        assert 0x00 in impl.opcode_codes


class TestTestCoverageEntry:
    """Tests for TestCoverageEntry data model."""

    def test_create(self) -> None:
        entry = TestCoverageEntry(
            implementation_name="flux-runtime",
            opcode_code=0x20,
            test_file="test_opcodes.py",
            test_function="test_add",
            passed=True,
        )
        assert entry.implementation_name == "flux-runtime"
        assert entry.opcode_code == 0x20
        assert entry.passed is True

    def test_frozen(self) -> None:
        entry = TestCoverageEntry("test", 0x00)
        with pytest.raises(AttributeError):
            entry.passed = False  # type: ignore[misc]

    def test_default_passed(self) -> None:
        entry = TestCoverageEntry("test", 0x00)
        assert entry.passed is True


# ===========================================================================
# 2. Seed Data Tests
# ===========================================================================

class TestSeedData:
    """Tests for the seed opcode data."""

    def test_python_opcodes_count(self) -> None:
        assert len(PYTHON_OPCODES) >= 200

    def test_python_opcode_map_consistency(self) -> None:
        codes_from_list = {op.code for op in PYTHON_OPCODES}
        codes_from_map = set(PYTHON_OPCODE_MAP.keys())
        assert codes_from_list == codes_from_map

    def test_no_duplicate_codes(self) -> None:
        codes = [op.code for op in PYTHON_OPCODES]
        assert len(codes) == len(set(codes))

    def test_halt_opcode(self) -> None:
        halt = PYTHON_OPCODE_MAP[0x00]
        assert halt.mnemonic == "HALT"
        assert halt.format == Format.A
        assert halt.category == Category.SYSTEM

    def test_a2a_opcodes(self) -> None:
        a2a = [op for op in PYTHON_OPCODES if op.category == Category.A2A]
        assert len(a2a) == 16
        assert all(op.format == Format.E for op in a2a)

    def test_confidence_opcodes(self) -> None:
        conf = [op for op in PYTHON_OPCODES if op.category == Category.CONFIDENCE]
        assert len(conf) == 16

    def test_extended_math_opcodes(self) -> None:
        ext = [op for op in PYTHON_OPCODES if op.category == Category.EXTENDED]
        assert len(ext) >= 4

    def test_system_opcodes_include_halt_nop_ret_iret(self) -> None:
        sys_ops = [op for op in PYTHON_OPCODES if op.category == Category.SYSTEM]
        mnemonics = {op.mnemonic for op in sys_ops}
        assert "HALT" in mnemonics
        assert "NOP" in mnemonics
        assert "RET" in mnemonics
        assert "IRET" in mnemonics


# ===========================================================================
# 3. ImplementationRegistry Tests
# ===========================================================================

class TestImplementationRegistry:
    """Tests for ImplementationRegistry."""

    def test_seed_default_has_four_implementations(self, registry: ImplementationRegistry) -> None:
        assert len(registry.implementations) == 4

    def test_seed_default_names(self, registry: ImplementationRegistry) -> None:
        names = set(registry.implementation_names)
        assert "flux-runtime" in names
        assert "greenhorn-runtime" in names
        assert "flux-runtime-c" in names
        assert "flux-vm-ts" in names

    def test_register_new(self, empty_registry: ImplementationRegistry) -> None:
        impl = ImplementationDef(name="test-vm", language="Rust", opcode_codes={0x00, 0x01})
        empty_registry.register(impl)
        assert empty_registry.get("test-vm") is not None
        assert len(empty_registry.implementation_names) == 1

    def test_register_duplicate_raises(self, registry: ImplementationRegistry) -> None:
        impl = ImplementationDef(name="flux-runtime", language="Python")
        with pytest.raises(ValueError, match="already registered"):
            registry.register(impl)

    def test_get_unknown_returns_none(self, registry: ImplementationRegistry) -> None:
        assert registry.get("nonexistent") is None

    def test_get_opcode_existing(self, registry: ImplementationRegistry) -> None:
        op = registry.get_opcode(0x00)
        assert op is not None
        assert op.mnemonic == "HALT"

    def test_get_opcode_unknown(self, registry: ImplementationRegistry) -> None:
        assert registry.get_opcode(0xFE) is None

    def test_total_opcodes(self, registry: ImplementationRegistry) -> None:
        assert registry.total_opcodes == len(PYTHON_OPCODES)

    def test_opcodes_by_category(self, registry: ImplementationRegistry) -> None:
        a2a = registry.opcodes_by_category(Category.A2A)
        assert len(a2a) == 16

    def test_opcodes_by_format(self, registry: ImplementationRegistry) -> None:
        fmt_a = registry.opcodes_by_format(Format.A)
        assert len(fmt_a) >= 4  # HALT, NOP, RET, IRET at minimum

    def test_python_impl_has_all_opcodes(self, registry: ImplementationRegistry) -> None:
        py = registry.get("flux-runtime")
        assert py is not None
        assert len(py.opcode_codes) == registry.total_opcodes

    def test_python_impl_has_all_formats(self, registry: ImplementationRegistry) -> None:
        py = registry.get("flux-runtime")
        assert py is not None
        assert py.supported_formats == set(Format)

    def test_go_impl_subset(self, registry: ImplementationRegistry) -> None:
        go = registry.get("greenhorn-runtime")
        assert go is not None
        assert len(go.opcode_codes) < registry.total_opcodes
        assert Format.G in go.supported_formats
        assert Category.A2A in go.supported_categories

    def test_c_impl_subset(self, registry: ImplementationRegistry) -> None:
        c = registry.get("flux-runtime-c")
        assert c is not None
        assert Format.C not in c.supported_formats
        assert Category.CONTROL in c.supported_categories

    def test_ts_impl_subset(self, registry: ImplementationRegistry) -> None:
        ts = registry.get("flux-vm-ts")
        assert ts is not None
        assert len(ts.opcode_codes) < registry.total_opcodes
        assert Format.C not in ts.supported_formats

    def test_register_coverage(self, empty_registry: ImplementationRegistry) -> None:
        entry = TestCoverageEntry("test", 0x00, "test.py", "test_halt", True)
        empty_registry.register_coverage(entry)
        assert len(empty_registry.coverage) == 1

    def test_register_coverage_batch(self, empty_registry: ImplementationRegistry) -> None:
        entries = [
            TestCoverageEntry("a", 0x00),
            TestCoverageEntry("a", 0x01),
            TestCoverageEntry("b", 0x00),
        ]
        empty_registry.register_coverage_batch(entries)
        assert len(empty_registry.coverage) == 3

    def test_implementations_returns_copy(self, registry: ImplementationRegistry) -> None:
        impls1 = registry.implementations
        impls2 = registry.implementations
        assert impls1 is not impls2
        assert impls1 == impls2


# ===========================================================================
# 4. ConformanceMatrix Tests
# ===========================================================================

class TestConformanceMatrix:
    """Tests for ConformanceMatrix."""

    def test_build_returns_all_implementations(self, registry: ImplementationRegistry) -> None:
        matrix = ConformanceMatrix(registry)
        result = matrix.build()
        assert set(result.keys()) == set(registry.implementation_names)

    def test_build_python_all_true(self, registry: ImplementationRegistry) -> None:
        matrix = ConformanceMatrix(registry)
        result = matrix.build()
        py = result["flux-runtime"]
        assert all(py.values())

    def test_build_ts_not_all_true(self, registry: ImplementationRegistry) -> None:
        matrix = ConformanceMatrix(registry)
        result = matrix.build()
        ts = result["flux-vm-ts"]
        assert not all(ts.values())

    def test_build_detailed_structure(self, registry: ImplementationRegistry) -> None:
        matrix = ConformanceMatrix(registry)
        result = matrix.build_detailed()
        first_code = min(registry.opcode_table.keys())
        entry = result["flux-runtime"][first_code]
        assert "implemented" in entry
        assert "mnemonic" in entry
        assert "format" in entry
        assert "category" in entry

    def test_filter_by_category_a2a(self, registry: ImplementationRegistry) -> None:
        matrix = ConformanceMatrix(registry)
        result = matrix.filter_by_category(Category.A2A)
        # Python has all a2a, Go has some a2a
        assert all(result["flux-runtime"].values())
        assert not all(result["flux-runtime-c"].values())  # C has no a2a

    def test_filter_by_format_a(self, registry: ImplementationRegistry) -> None:
        matrix = ConformanceMatrix(registry)
        result = matrix.filter_by_format(Format.A)
        # All implementations should have at least HALT (Format A)
        for name in registry.implementation_names:
            assert any(result[name].values())

    def test_filter_by_format_c(self, registry: ImplementationRegistry) -> None:
        matrix = ConformanceMatrix(registry)
        result = matrix.filter_by_format(Format.C)
        # Only Python has Format C
        assert any(result["flux-runtime"].values())
        assert not any(result["greenhorn-runtime"].values())

    def test_get_implemented_count(self, registry: ImplementationRegistry) -> None:
        matrix = ConformanceMatrix(registry)
        py_count = matrix.get_implemented_count("flux-runtime")
        assert py_count == registry.total_opcodes

    def test_get_implemented_count_unknown_raises(self, registry: ImplementationRegistry) -> None:
        matrix = ConformanceMatrix(registry)
        with pytest.raises(KeyError, match="Unknown implementation"):
            matrix.get_implemented_count("nonexistent")

    def test_get_missing_opcodes_python_empty(self, registry: ImplementationRegistry) -> None:
        matrix = ConformanceMatrix(registry)
        missing = matrix.get_missing_opcodes("flux-runtime")
        assert len(missing) == 0

    def test_get_missing_opcodes_ts_nonempty(self, registry: ImplementationRegistry) -> None:
        matrix = ConformanceMatrix(registry)
        missing = matrix.get_missing_opcodes("flux-vm-ts")
        assert len(missing) > 0

    def test_cross_implementation_opcodes(self, registry: ImplementationRegistry) -> None:
        matrix = ConformanceMatrix(registry)
        common = matrix.cross_implementation_opcodes()
        # HALT (0x00) and NOP (0x01) should be in all
        assert 0x00 in common
        assert 0x01 in common

    def test_unique_opcodes_python(self, registry: ImplementationRegistry) -> None:
        matrix = ConformanceMatrix(registry)
        unique = matrix.unique_opcodes("flux-runtime")
        # Python should have many unique opcodes
        assert len(unique) > 100

    def test_unique_opcodes_ts(self, registry: ImplementationRegistry) -> None:
        matrix = ConformanceMatrix(registry)
        unique = matrix.unique_opcodes("flux-vm-ts")
        # TS has the smallest set, might have few unique ones
        # but at minimum some should be unique or shared
        assert isinstance(unique, set)

    def test_cross_implementation_empty_registry(self, empty_registry: ImplementationRegistry) -> None:
        matrix = ConformanceMatrix(empty_registry)
        assert matrix.cross_implementation_opcodes() == set()


# ===========================================================================
# 5. CoverageAnalyzer Tests
# ===========================================================================

class TestCoverageAnalyzer:
    """Tests for CoverageAnalyzer."""

    def test_coverage_by_implementation_keys(self, registry: ImplementationRegistry) -> None:
        analyzer = CoverageAnalyzer(registry)
        result = analyzer.coverage_by_implementation()
        assert set(result.keys()) == set(registry.implementation_names)

    def test_coverage_python_high(self, registry: ImplementationRegistry) -> None:
        analyzer = CoverageAnalyzer(registry)
        stats = analyzer.coverage_by_implementation()
        py = stats["flux-runtime"]
        assert py["coverage_rate"] > 0.90

    def test_coverage_ts_lower(self, registry: ImplementationRegistry) -> None:
        analyzer = CoverageAnalyzer(registry)
        stats = analyzer.coverage_by_implementation()
        ts = stats["flux-vm-ts"]
        assert ts["coverage_rate"] < stats["flux-runtime"]["coverage_rate"]

    def test_coverage_for_opcode_halt(self, registry: ImplementationRegistry) -> None:
        analyzer = CoverageAnalyzer(registry)
        result = analyzer.coverage_for_opcode(0x00)
        # HALT should be tested in all implementations
        assert all(result.values())

    def test_coverage_for_opcode_untested(self, registry: ImplementationRegistry) -> None:
        analyzer = CoverageAnalyzer(registry)
        # 0xFF ILLEGAL is explicitly excluded from coverage seed
        result = analyzer.coverage_for_opcode(0xFF)
        assert not any(result.values())

    def test_untested_opcodes_go(self, registry: ImplementationRegistry) -> None:
        analyzer = CoverageAnalyzer(registry)
        untested = analyzer.untested_opcodes("greenhorn-runtime")
        assert len(untested) > 0
        assert all(op.code != 0x00 for op in untested)  # HALT is tested

    def test_untested_opcodes_unknown_raises(self, registry: ImplementationRegistry) -> None:
        analyzer = CoverageAnalyzer(registry)
        with pytest.raises(KeyError, match="Unknown implementation"):
            analyzer.untested_opcodes("nonexistent")

    def test_failing_tests_exist(self, registry: ImplementationRegistry) -> None:
        analyzer = CoverageAnalyzer(registry)
        c_failing = analyzer.failing_tests("flux-runtime-c")
        assert len(c_failing) >= 1
        assert all(not e.passed for e in c_failing)

    def test_failing_tests_ts(self, registry: ImplementationRegistry) -> None:
        analyzer = CoverageAnalyzer(registry)
        ts_failing = analyzer.failing_tests("flux-vm-ts")
        assert len(ts_failing) >= 1

    def test_overall_summary_structure(self, registry: ImplementationRegistry) -> None:
        analyzer = CoverageAnalyzer(registry)
        summary = analyzer.overall_coverage_summary()
        assert summary["implementations"] == 4
        assert "avg_coverage_rate" in summary
        assert "avg_pass_rate" in summary
        assert "per_implementation" in summary

    def test_overall_summary_rates_bounded(self, registry: ImplementationRegistry) -> None:
        analyzer = CoverageAnalyzer(registry)
        summary = analyzer.overall_coverage_summary()
        assert 0.0 <= summary["avg_coverage_rate"] <= 1.0
        assert 0.0 <= summary["avg_pass_rate"] <= 1.0

    def test_fully_covered_opcodes(self, registry: ImplementationRegistry) -> None:
        analyzer = CoverageAnalyzer(registry)
        fully = analyzer.fully_covered_opcodes()
        # HALT should be fully covered
        assert 0x00 in fully

    def test_overall_coverage_empty_registry(self, empty_registry: ImplementationRegistry) -> None:
        analyzer = CoverageAnalyzer(empty_registry)
        summary = analyzer.overall_coverage_summary()
        assert summary["implementations"] == 0


# ===========================================================================
# 6. GapReporter Tests
# ===========================================================================

class TestGapReporter:
    """Tests for GapReporter."""

    def test_implementation_gaps_structure(self, registry: ImplementationRegistry) -> None:
        reporter = GapReporter(registry)
        gaps = reporter.implementation_gaps("flux-vm-ts")
        assert gaps["implementation"] == "flux-vm-ts"
        assert gaps["language"] == "TypeScript"
        assert "missing_opcodes" in gaps
        assert "missing_by_category" in gaps
        assert "untested_opcodes" in gaps
        assert "failing_opcodes" in gaps
        assert "missing_formats" in gaps
        assert "missing_categories" in gaps

    def test_implementation_gaps_python_empty_missing(self, registry: ImplementationRegistry) -> None:
        reporter = GapReporter(registry)
        gaps = reporter.implementation_gaps("flux-runtime")
        assert gaps["missing_count"] == 0
        assert len(gaps["missing_opcodes"]) == 0

    def test_implementation_gaps_ts_has_missing(self, registry: ImplementationRegistry) -> None:
        reporter = GapReporter(registry)
        gaps = reporter.implementation_gaps("flux-vm-ts")
        assert gaps["missing_count"] > 0

    def test_implementation_gaps_unknown_raises(self, registry: ImplementationRegistry) -> None:
        reporter = GapReporter(registry)
        with pytest.raises(KeyError, match="Unknown implementation"):
            reporter.implementation_gaps("nonexistent")

    def test_category_gaps_keys(self, registry: ImplementationRegistry) -> None:
        reporter = GapReporter(registry)
        gaps = reporter.category_gaps()
        # Should have at least system, arithmetic, memory, a2a
        assert "system" in gaps
        assert "arithmetic" in gaps

    def test_category_gaps_python_all_full(self, registry: ImplementationRegistry) -> None:
        reporter = GapReporter(registry)
        gaps = reporter.category_gaps()
        for cat_name, per_impl in gaps.items():
            py_stats = per_impl["flux-runtime"]
            assert py_stats["rate"] == 1.0

    def test_category_gaps_a2a_c_missing(self, registry: ImplementationRegistry) -> None:
        reporter = GapReporter(registry)
        gaps = reporter.category_gaps()
        if "a2a" in gaps:
            c_stats = gaps["a2a"]["flux-runtime-c"]
            assert c_stats["implemented"] == 0

    def test_format_gaps_structure(self, registry: ImplementationRegistry) -> None:
        reporter = GapReporter(registry)
        gaps = reporter.format_gaps()
        for fmt_name in [f.value for f in Format]:
            assert fmt_name in gaps

    def test_format_gaps_python_all_true(self, registry: ImplementationRegistry) -> None:
        reporter = GapReporter(registry)
        gaps = reporter.format_gaps()
        for fmt_name in [f.value for f in Format]:
            assert gaps[fmt_name]["flux-runtime"] is True

    def test_format_gaps_go_missing_c(self, registry: ImplementationRegistry) -> None:
        reporter = GapReporter(registry)
        gaps = reporter.format_gaps()
        # Go doesn't have Format C
        assert gaps["C"]["greenhorn-runtime"] is False

    def test_cross_impl_summary_structure(self, registry: ImplementationRegistry) -> None:
        reporter = GapReporter(registry)
        summary = reporter.cross_implementation_summary()
        assert "isa_size" in summary
        assert "common_opcodes" in summary
        assert "common_opcode_names" in summary
        assert "per_implementation" in summary

    def test_cross_impl_summary_common_opcodes(self, registry: ImplementationRegistry) -> None:
        reporter = GapReporter(registry)
        summary = reporter.cross_implementation_summary()
        assert "HALT" in summary["common_opcode_names"]
        assert "NOP" in summary["common_opcode_names"]

    def test_priority_gaps_returns_list(self, registry: ImplementationRegistry) -> None:
        reporter = GapReporter(registry)
        gaps = reporter.priority_gaps(top_n=5)
        assert isinstance(gaps, list)
        assert len(gaps) <= 5

    def test_priority_gaps_structure(self, registry: ImplementationRegistry) -> None:
        reporter = GapReporter(registry)
        gaps = reporter.priority_gaps(top_n=10)
        for gap in gaps:
            assert "opcode" in gap
            assert "code" in gap
            assert "format" in gap
            assert "category" in gap
            assert "missing_from" in gap

    def test_priority_gaps_sorted_descending(self, registry: ImplementationRegistry) -> None:
        reporter = GapReporter(registry)
        gaps = reporter.priority_gaps(top_n=20)
        if len(gaps) >= 2:
            assert gaps[0]["missing_from"] >= gaps[1]["missing_from"]

    def test_priority_gaps_top_n_respected(self, registry: ImplementationRegistry) -> None:
        reporter = GapReporter(registry)
        gaps = reporter.priority_gaps(top_n=3)
        assert len(gaps) <= 3


# ===========================================================================
# 7. ConformanceScore Tests
# ===========================================================================

class TestConformanceScore:
    """Tests for ConformanceScore."""

    def test_isa_coverage_python_is_one(self, registry: ImplementationRegistry) -> None:
        scorer = ConformanceScore(registry)
        assert scorer.isa_coverage_score("flux-runtime") == 1.0

    def test_isa_coverage_python_gt_go(self, registry: ImplementationRegistry) -> None:
        scorer = ConformanceScore(registry)
        py = scorer.isa_coverage_score("flux-runtime")
        go = scorer.isa_coverage_score("greenhorn-runtime")
        assert py > go

    def test_isa_coverage_ts_lowest(self, registry: ImplementationRegistry) -> None:
        scorer = ConformanceScore(registry)
        scores = {name: scorer.isa_coverage_score(name) for name in registry.implementation_names}
        ts = scores["flux-vm-ts"]
        for name, score in scores.items():
            if name != "flux-vm-ts":
                assert score >= ts

    def test_isa_coverage_unknown_raises(self, registry: ImplementationRegistry) -> None:
        scorer = ConformanceScore(registry)
        with pytest.raises(KeyError):
            scorer.isa_coverage_score("nonexistent")

    def test_category_coverage_python_is_one(self, registry: ImplementationRegistry) -> None:
        scorer = ConformanceScore(registry)
        assert scorer.category_coverage_score("flux-runtime") == 1.0

    def test_category_coverage_ts_less_than_one(self, registry: ImplementationRegistry) -> None:
        scorer = ConformanceScore(registry)
        score = scorer.category_coverage_score("flux-vm-ts")
        assert score < 1.0

    def test_format_coverage_python_is_one(self, registry: ImplementationRegistry) -> None:
        scorer = ConformanceScore(registry)
        assert scorer.format_coverage_score("flux-runtime") == 1.0

    def test_format_coverage_go_has_g(self, registry: ImplementationRegistry) -> None:
        scorer = ConformanceScore(registry)
        go_fmt = scorer.format_coverage_score("greenhorn-runtime")
        ts_fmt = scorer.format_coverage_score("flux-vm-ts")
        # Go supports Format G, TS doesn't
        assert go_fmt > ts_fmt

    def test_format_coverage_unknown_raises(self, registry: ImplementationRegistry) -> None:
        scorer = ConformanceScore(registry)
        with pytest.raises(KeyError):
            scorer.format_coverage_score("nonexistent")

    def test_test_coverage_python_high(self, registry: ImplementationRegistry) -> None:
        scorer = ConformanceScore(registry)
        score = scorer.test_coverage_score("flux-runtime")
        assert score > 0.9

    def test_test_coverage_ts_lower(self, registry: ImplementationRegistry) -> None:
        scorer = ConformanceScore(registry)
        ts = scorer.test_coverage_score("flux-vm-ts")
        py = scorer.test_coverage_score("flux-runtime")
        assert ts < py

    def test_composite_score_structure(self, registry: ImplementationRegistry) -> None:
        scorer = ConformanceScore(registry)
        score = scorer.composite_score("flux-runtime")
        assert "isa_coverage" in score
        assert "category_coverage" in score
        assert "format_coverage" in score
        assert "test_coverage" in score
        assert "composite" in score

    def test_composite_score_python_is_one(self, registry: ImplementationRegistry) -> None:
        scorer = ConformanceScore(registry)
        score = scorer.composite_score("flux-runtime")
        assert score["composite"] == 1.0

    def test_composite_score_bounded(self, registry: ImplementationRegistry) -> None:
        scorer = ConformanceScore(registry)
        for name in registry.implementation_names:
            score = scorer.composite_score(name)
            assert 0.0 <= score["composite"] <= 1.0

    def test_ranking_returns_all(self, registry: ImplementationRegistry) -> None:
        scorer = ConformanceScore(registry)
        ranking = scorer.ranking()
        assert len(ranking) == 4
        names = [r[0] for r in ranking]
        assert set(names) == set(registry.implementation_names)

    def test_ranking_python_first(self, registry: ImplementationRegistry) -> None:
        scorer = ConformanceScore(registry)
        ranking = scorer.ranking()
        assert ranking[0][0] == "flux-runtime"

    def test_ranking_descending(self, registry: ImplementationRegistry) -> None:
        scorer = ConformanceScore(registry)
        ranking = scorer.ranking()
        scores = [r[1] for r in ranking]
        assert scores == sorted(scores, reverse=True)

    def test_format_support_matrix_structure(self, registry: ImplementationRegistry) -> None:
        scorer = ConformanceScore(registry)
        matrix = scorer.format_support_matrix()
        for fmt in Format:
            assert fmt.value in matrix
            for name in registry.implementation_names:
                assert name in matrix[fmt.value]
                assert isinstance(matrix[fmt.value][name], bool)

    def test_format_support_matrix_python_all_true(self, registry: ImplementationRegistry) -> None:
        scorer = ConformanceScore(registry)
        matrix = scorer.format_support_matrix()
        for fmt_name in matrix:
            assert matrix[fmt_name]["flux-runtime"] is True

    def test_isa_coverage_empty_registry(self, empty_registry: ImplementationRegistry) -> None:
        # Register a dummy impl
        empty_registry.register(ImplementationDef(name="dummy", language="Test"))
        scorer = ConformanceScore(empty_registry)
        assert scorer.isa_coverage_score("dummy") == 0.0


# ===========================================================================
# 8. MatrixExporter Tests
# ===========================================================================

class TestMatrixExporter:
    """Tests for MatrixExporter."""

    def test_to_markdown_not_empty(self, registry: ImplementationRegistry) -> None:
        exporter = MatrixExporter(registry)
        md = exporter.to_markdown()
        assert len(md) > 0

    def test_to_markdown_contains_header(self, registry: ImplementationRegistry) -> None:
        exporter = MatrixExporter(registry)
        md = exporter.to_markdown()
        assert "Conformance Matrix" in md
        assert "Conformance Scores" in md

    def test_to_markdown_contains_impl_names(self, registry: ImplementationRegistry) -> None:
        exporter = MatrixExporter(registry)
        md = exporter.to_markdown()
        assert "flux-runtime" in md
        assert "greenhorn-runtime" in md
        assert "flux-runtime-c" in md
        assert "flux-vm-ts" in md

    def test_to_markdown_contains_format_support(self, registry: ImplementationRegistry) -> None:
        exporter = MatrixExporter(registry)
        md = exporter.to_markdown()
        assert "Format Support" in md

    def test_to_markdown_contains_priority_gaps(self, registry: ImplementationRegistry) -> None:
        exporter = MatrixExporter(registry)
        md = exporter.to_markdown()
        assert "Priority Gaps" in md

    def test_to_json_valid(self, registry: ImplementationRegistry) -> None:
        exporter = MatrixExporter(registry)
        json_str = exporter.to_json()
        data = json.loads(json_str)
        assert "isa_size" in data
        assert "implementations" in data
        assert "matrix" in data
        assert "scores" in data
        assert "coverage" in data

    def test_to_json_contains_all_impls(self, registry: ImplementationRegistry) -> None:
        exporter = MatrixExporter(registry)
        data = json.loads(exporter.to_json())
        assert set(data["implementations"].keys()) == set(registry.implementation_names)

    def test_to_json_matrix_opcodes_hex_keys(self, registry: ImplementationRegistry) -> None:
        exporter = MatrixExporter(registry)
        data = json.loads(exporter.to_json())
        py_matrix = data["matrix"]["flux-runtime"]
        assert "0x00" in py_matrix
        assert py_matrix["0x00"] is True

    def test_to_csv_not_empty(self, registry: ImplementationRegistry) -> None:
        exporter = MatrixExporter(registry)
        csv_str = exporter.to_csv()
        assert len(csv_str) > 0

    def test_to_csv_contains_header(self, registry: ImplementationRegistry) -> None:
        exporter = MatrixExporter(registry)
        csv_str = exporter.to_csv()
        lines = csv_str.strip().split("\n")
        header = lines[0]
        assert "Opcode" in header
        assert "flux-runtime" in header

    def test_to_csv_contains_halt_row(self, registry: ImplementationRegistry) -> None:
        exporter = MatrixExporter(registry)
        csv_str = exporter.to_csv()
        assert "HALT" in csv_str

    def test_to_dict_matches_json(self, registry: ImplementationRegistry) -> None:
        exporter = MatrixExporter(registry)
        data = exporter.to_dict()
        json_data = json.loads(exporter.to_json())
        assert data == json_data


# ===========================================================================
# 9. Integration & Edge Case Tests
# ===========================================================================

class TestIntegration:
    """Integration and edge case tests."""

    def test_full_workflow(self, empty_registry: ImplementationRegistry) -> None:
        """Test creating a registry, adding impls, computing scores, exporting."""
        empty_registry.register(ImplementationDef(
            name="mini-vm", language="Rust",
            opcode_codes={0x00, 0x01, 0x20},
            supported_formats={Format.A, Format.E},
            supported_categories={Category.SYSTEM, Category.ARITHMETIC},
        ))
        empty_registry.register_coverage(TestCoverageEntry("mini-vm", 0x00, "test.rs"))
        empty_registry.register_coverage(TestCoverageEntry("mini-vm", 0x20, "test.rs"))

        matrix = ConformanceMatrix(empty_registry)
        assert matrix.get_implemented_count("mini-vm") == 3
        assert len(matrix.get_missing_opcodes("mini-vm")) > 0

        analyzer = CoverageAnalyzer(empty_registry)
        untested = analyzer.untested_opcodes("mini-vm")
        assert len(untested) == 1  # Only 0x01 is untested
        assert untested[0].mnemonic == "NOP"

        scorer = ConformanceScore(empty_registry)
        isa = scorer.isa_coverage_score("mini-vm")
        assert 0.0 < isa < 1.0

        exporter = MatrixExporter(empty_registry)
        md = exporter.to_markdown()
        assert "mini-vm" in md

    def test_empty_matrix_export(self, empty_registry: ImplementationRegistry) -> None:
        exporter = MatrixExporter(empty_registry)
        md = exporter.to_markdown()
        assert "0 opcodes" not in md  # Empty impls means 0 impls, not 0 opcodes

    def test_opcode_consistency_across_registry_and_matrix(self, registry: ImplementationRegistry) -> None:
        matrix = ConformanceMatrix(registry)
        built = matrix.build()
        for name, op_map in built.items():
            assert len(op_map) == registry.total_opcodes

    def test_scores_consistency(self, registry: ImplementationRegistry) -> None:
        scorer = ConformanceScore(registry)
        matrix = ConformanceMatrix(registry)
        for name in registry.implementation_names:
            expected = matrix.get_implemented_count(name) / registry.total_opcodes
            actual = scorer.isa_coverage_score(name)
            assert abs(actual - expected) < 1e-9

    def test_all_categories_have_opcodes(self, registry: ImplementationRegistry) -> None:
        used_cats = {op.category for op in registry.opcode_table.values()}
        # Check at least the main categories are represented
        assert Category.SYSTEM in used_cats
        assert Category.ARITHMETIC in used_cats
        assert Category.MEMORY in used_cats

    def test_format_a_opcodes_all_system_or_debug(self) -> None:
        fmt_a = [op for op in PYTHON_OPCODES if op.format == Format.A]
        for op in fmt_a:
            assert op.category in (Category.SYSTEM, Category.DEBUG)

    def test_implementations_sorted_in_matrix(self, registry: ImplementationRegistry) -> None:
        exporter = MatrixExporter(registry)
        data = exporter.to_dict()
        matrix = data["matrix"]
        for name, op_map in matrix.items():
            codes = [int(k, 16) for k in op_map.keys()]
            assert codes == sorted(codes)
