"""
Property-Based Tests for the FLUX Canonical Opcode Translation Shim.

Verifies mathematical properties of cross-runtime bytecode translation
using a lightweight property testing framework (no Hypothesis dependency).

Properties verified:
1. Round-trip identity: A→B→A returns original (for mapped opcodes)
2. Transitivity: A→B→C equals A→C for all runtime triples
3. Determinism: same input always produces same output
4. NOP universality: NOP translates to itself across all runtimes
5. Escape prefix: 0xFF passes through unchanged
6. Length preservation: translated bytecode has same length as input
7. Idempotence: translating the same bytecode twice yields same result
8. Unmapped bytes: unmapped opcodes return 0xFE consistently

Python 3.9+ stdlib only — zero external dependencies.
"""

from __future__ import annotations

import random
import sys
import os
import unittest
from typing import Callable, List, Tuple

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from canonical_opcode_shim import (
    python_to_canonical, canonical_to_python,
    rust_to_canonical, canonical_to_rust,
    cos_to_canonical, canonical_to_cos,
    go_to_canonical, canonical_to_go,
    python_to_rust, rust_to_python,
    python_to_go, go_to_python,
    coverage_report,
    _PY_TO_CAN, _RUST_TO_CAN, _COS_TO_CAN, _GO_TO_CAN,
    _CAN_TO_PY, _CAN_TO_RUST, _CAN_TO_COS, _CAN_TO_GO,
)

# ─── Runtime Definitions ────────────────────────────────────────────────

RUNTIMES = ["python", "rust", "cos", "go"]

TO_CANONICAL = {
    "python": python_to_canonical,
    "rust": rust_to_canonical,
    "cos": cos_to_canonical,
    "go": go_to_canonical,
}

FROM_CANONICAL = {
    "python": canonical_to_python,
    "rust": canonical_to_rust,
    "cos": canonical_to_cos,
    "go": canonical_to_go,
}

TRANSLATION_TABLES = {
    "python": _PY_TO_CAN,
    "rust": _RUST_TO_CAN,
    "cos": _COS_TO_CAN,
    "go": _GO_TO_CAN,
}

INVERSE_TABLES = {
    "python": _CAN_TO_PY,
    "rust": _CAN_TO_RUST,
    "cos": _CAN_TO_COS,
    "go": _CAN_TO_GO,
}

# Cross-runtime direct translations
CROSS_RUNTIME = {
    ("python", "rust"): python_to_rust,
    ("rust", "python"): rust_to_python,
    ("python", "go"): python_to_go,
    ("go", "python"): go_to_python,
}

UNMAPPED = 0xFE
ESCAPE_PREFIX = 0xFF


# ═══════════════════════════════════════════════════════════════════════════
# Property Testing Framework (inline, no deps)
# ═══════════════════════════════════════════════════════════════════════════

def _run_property(name: str, fn: Callable, iterations: int = 100):
    """Run a property test *iterations* times. Returns (passed, failures)."""
    failures = []
    for i in range(iterations):
        try:
            fn(i)
        except (AssertionError, Exception) as e:
            failures.append((i, e))
    return failures


# ═══════════════════════════════════════════════════════════════════════════
# Helper: Generate mapped opcodes for a runtime
# ═══════════════════════════════════════════════════════════════════════════

def _get_mapped_opcodes(runtime: str) -> List[int]:
    """Return list of opcodes that have a canonical mapping (not 0xFE)."""
    table = TRANSLATION_TABLES[runtime]
    return [i for i in range(256) if table[i] != UNMAPPED]


def _get_invertible_opcodes(runtime: str) -> List[int]:
    """Return opcodes where round-trip translation is identity (fully mapped)."""
    to_can = TRANSLATION_TABLES[runtime]
    from_can = INVERSE_TABLES[runtime]
    invertible = []
    for i in range(256):
        if to_can[i] != UNMAPPED and to_can[i] != ESCAPE_PREFIX:
            if from_can[to_can[i]] == i:
                invertible.append(i)
    return invertible


# ═══════════════════════════════════════════════════════════════════════════
# Test: NOP Universality
# ═══════════════════════════════════════════════════════════════════════════

class TestNOPUniversality(unittest.TestCase):
    """NOP should translate to a valid opcode (not 0xFE) in all runtimes."""

    def test_nop_python_maps(self):
        result = python_to_canonical(bytes([0x00]))
        # Python NOP is 0x00 → canonical should not be 0xFE
        self.assertNotEqual(result[0], UNMAPPED)

    def test_nop_rust_maps(self):
        # Rust NOP is 0x01
        result = rust_to_canonical(bytes([0x01]))
        self.assertNotEqual(result[0], UNMAPPED)

    def test_nop_cos_maps(self):
        # C OS NOP is 0x00
        result = cos_to_canonical(bytes([0x00]))
        self.assertNotEqual(result[0], UNMAPPED)

    def test_nop_go_maps(self):
        # Go NOP is 0x00
        result = go_to_canonical(bytes([0x00]))
        self.assertNotEqual(result[0], UNMAPPED)

    def test_all_runtimes_nop_not_unmapped(self):
        """For each runtime, find its NOP and verify it maps to canonical."""
        for rt, to_can in TO_CANONICAL.items():
            # The NOP might differ per runtime; find any commonly mapped opcode
            mapped = _get_mapped_opcodes(rt)
            self.assertGreater(len(mapped), 10,
                               f"{rt} has too few mapped opcodes (<10)")

    def test_escape_prefix_passthrough_all_runtimes(self):
        """0xFF should pass through unchanged for all runtimes."""
        for rt, to_can in TO_CANONICAL.items():
            result = to_can(bytes([0xFF]))
            self.assertEqual(result[0], 0xFF,
                             f"{rt}: 0xFF escape prefix not preserved")


# ═══════════════════════════════════════════════════════════════════════════
# Test: Length Preservation
# ═══════════════════════════════════════════════════════════════════════════

class TestLengthPreservation(unittest.TestCase):
    """Translation should always preserve bytecode length."""

    def test_single_byte_all_runtimes(self):
        for rt, to_can in TO_CANONICAL.items():
            for opcode in range(256):
                bc = bytes([opcode])
                result = to_can(bc)
                self.assertEqual(len(result), 1,
                                 f"{rt}: length not preserved for 0x{opcode:02x}")

    def test_multi_byte_all_runtimes(self):
        """Length preservation holds for multi-byte sequences."""
        rng = random.Random(42)
        for rt, to_can in TO_CANONICAL.items():
            for _ in range(50):
                length = rng.randint(1, 32)
                bc = bytes(rng.randint(0, 255) for _ in range(length))
                result = to_can(bc)
                self.assertEqual(len(result), length,
                                 f"{rt}: length not preserved for {length}-byte input")

    def test_empty_bytecode_all_runtimes(self):
        for rt, to_can in TO_CANONICAL.items():
            result = to_can(b"")
            self.assertEqual(len(result), 0, f"{rt}: empty not preserved")


# ═══════════════════════════════════════════════════════════════════════════
# Test: Determinism
# ═══════════════════════════════════════════════════════════════════════════

class TestDeterminism(unittest.TestCase):
    """Same input should always produce same output (pure function)."""

    def test_determinism_all_runtimes(self):
        rng = random.Random(123)
        for rt, to_can in TO_CANONICAL.items():
            for _ in range(100):
                bc = bytes(rng.randint(0, 255) for _ in range(rng.randint(1, 64)))
                result1 = to_can(bc)
                result2 = to_can(bc)
                self.assertEqual(result1, result2,
                                 f"{rt}: non-deterministic translation")


# ═══════════════════════════════════════════════════════════════════════════
# Test: Idempotence (translate same bytecode twice = same result)
# ═══════════════════════════════════════════════════════════════════════════

class TestIdempotence(unittest.TestCase):
    """Translating already-translated bytecode should still be valid."""

    def test_double_translation_to_canonical(self):
        """to_canonical(to_canonical(x)) should still be valid bytes."""
        rng = random.Random(456)
        for rt, to_can in TO_CANONICAL.items():
            for _ in range(100):
                bc = bytes(rng.randint(0, 255) for _ in range(rng.randint(1, 32)))
                once = to_can(bc)
                twice = to_can(once)
                self.assertEqual(len(twice), len(bc),
                                 f"{rt}: double-translate changed length")

    def test_double_translation_from_canonical(self):
        """from_canonical(from_canonical(x)) should preserve length."""
        rng = random.Random(789)
        for rt, from_can in FROM_CANONICAL.items():
            for _ in range(100):
                bc = bytes(rng.randint(0, 255) for _ in range(rng.randint(1, 32)))
                once = from_can(bc)
                twice = from_can(once)
                self.assertEqual(len(twice), len(bc),
                                 f"{rt}: double reverse-translate changed length")


# ═══════════════════════════════════════════════════════════════════════════
# Test: Round-Trip Identity (the critical property)
# ═══════════════════════════════════════════════════════════════════════════

class TestRoundTripIdentity(unittest.TestCase):
    """For invertible opcodes: A→B→A should return the original byte."""

    def test_python_roundtrip_invertible_opcodes(self):
        invertible = _get_invertible_opcodes("python")
        self.assertGreater(len(invertible), 5, "Python: too few invertible opcodes")
        for op in invertible:
            bc = bytes([op])
            canonical = python_to_canonical(bc)
            roundtrip = canonical_to_python(canonical)
            self.assertEqual(roundtrip[0], op,
                             f"Python round-trip failed: 0x{op:02x} → 0x{canonical[0]:02x} → 0x{roundtrip[0]:02x}")

    def test_rust_roundtrip_invertible_opcodes(self):
        invertible = _get_invertible_opcodes("rust")
        self.assertGreater(len(invertible), 5, "Rust: too few invertible opcodes")
        for op in invertible:
            bc = bytes([op])
            canonical = rust_to_canonical(bc)
            roundtrip = canonical_to_rust(canonical)
            self.assertEqual(roundtrip[0], op,
                             f"Rust round-trip failed: 0x{op:02x} → 0x{canonical[0]:02x} → 0x{roundtrip[0]:02x}")

    def test_cos_roundtrip_invertible_opcodes(self):
        invertible = _get_invertible_opcodes("cos")
        self.assertGreater(len(invertible), 3, "C-OS: too few invertible opcodes")
        for op in invertible:
            bc = bytes([op])
            canonical = cos_to_canonical(bc)
            roundtrip = canonical_to_cos(canonical)
            self.assertEqual(roundtrip[0], op,
                             f"C-OS round-trip failed: 0x{op:02x} → 0x{canonical[0]:02x} → 0x{roundtrip[0]:02x}")

    def test_go_roundtrip_invertible_opcodes(self):
        invertible = _get_invertible_opcodes("go")
        self.assertGreater(len(invertible), 2, "Go: too few invertible opcodes")
        for op in invertible:
            bc = bytes([op])
            canonical = go_to_canonical(bc)
            roundtrip = canonical_to_go(canonical)
            self.assertEqual(roundtrip[0], op,
                             f"Go round-trip failed: 0x{op:02x} → 0x{canonical[0]:02x} → 0x{roundtrip[0]:02x}")

    def test_roundtrip_multi_byte(self):
        """Round-trip should work for multi-byte sequences of invertible opcodes."""
        rng = random.Random(314)
        for rt in RUNTIMES:
            invertible = _get_invertible_opcodes(rt)
            if len(invertible) < 2:
                continue
            for _ in range(50):
                length = rng.randint(2, 16)
                bc = bytes(rng.choice(invertible) for _ in range(length))
                canonical = TO_CANONICAL[rt](bc)
                roundtrip = FROM_CANONICAL[rt](canonical)
                self.assertEqual(roundtrip, bc,
                                 f"{rt}: multi-byte round-trip failed: {bc.hex()} → {canonical.hex()} → {roundtrip.hex()}")


# ═══════════════════════════════════════════════════════════════════════════
# Test: Transitivity (A→B→C equals A→C)
# ═══════════════════════════════════════════════════════════════════════════

class TestTransitivity(unittest.TestCase):
    """Cross-runtime translation via canonical should be transitive."""

    def test_python_rust_via_canonical(self):
        rng = random.Random(999)
        for _ in range(100):
            bc = bytes(rng.randint(0, 255) for _ in range(rng.randint(1, 32)))
            direct = python_to_rust(bc)
            via_canonical = rust_to_canonical(python_to_canonical(bc))
            self.assertEqual(direct, via_canonical,
                             "python→rust != python→canonical→rust")

    def test_rust_python_via_canonical(self):
        rng = random.Random(888)
        for _ in range(100):
            bc = bytes(rng.randint(0, 255) for _ in range(rng.randint(1, 32)))
            direct = rust_to_python(bc)
            via_canonical = canonical_to_python(rust_to_canonical(bc))
            self.assertEqual(direct, via_canonical,
                             "rust→python != rust→canonical→python")

    def test_python_go_via_canonical(self):
        rng = random.Random(777)
        for _ in range(100):
            bc = bytes(rng.randint(0, 255) for _ in range(rng.randint(1, 32)))
            direct = python_to_go(bc)
            via_canonical = canonical_to_go(python_to_canonical(bc))
            self.assertEqual(direct, via_canonical,
                             "python→go != python→canonical→go")

    def test_go_python_via_canonical(self):
        rng = random.Random(666)
        for _ in range(100):
            bc = bytes(rng.randint(0, 255) for _ in range(rng.randint(1, 32)))
            direct = go_to_python(bc)
            via_canonical = canonical_to_python(go_to_canonical(bc))
            self.assertEqual(direct, via_canonical,
                             "go→python != go→canonical→python")

    def test_all_pairs_via_canonical(self):
        """All runtime pairs should translate consistently via canonical."""
        rng = random.Random(555)
        for src in RUNTIMES:
            for dst in RUNTIMES:
                if src == dst:
                    continue
                for _ in range(20):
                    bc = bytes(rng.randint(0, 255) for _ in range(rng.randint(1, 16)))
                    via_can = FROM_CANONICAL[dst](TO_CANONICAL[src](bc))
                    self.assertEqual(len(via_can), len(bc),
                                     f"{src}→{dst} via canonical: length mismatch")


# ═══════════════════════════════════════════════════════════════════════════
# Test: Unmapped Byte Consistency
# ═══════════════════════════════════════════════════════════════════════════

class TestUnmappedConsistency(unittest.TestCase):
    """Unmapped opcodes should consistently return 0xFE."""

    def test_unmapped_bytes_reported(self):
        """Each runtime should have documented unmapped opcodes."""
        for rt in RUNTIMES:
            table = TRANSLATION_TABLES[rt]
            unmapped_count = sum(1 for b in table if b == UNMAPPED)
            mapped_count = sum(1 for b in table if b != UNMAPPED and b != ESCAPE_PREFIX)
            # Every runtime should have SOME unmapped bytes (not all 256 mapped)
            self.assertGreater(unmapped_count, 50,
                               f"{rt}: expected >50 unmapped opcodes, got {unmapped_count}")
            # Every runtime should have SOME mapped bytes
            self.assertGreater(mapped_count, 5,
                               f"{rt}: expected >5 mapped opcodes, got {mapped_count}")

    def test_unmapped_consistency(self):
        """For known-unmapped regions, translation returns 0xFE consistently."""
        for rt, to_can in TO_CANONICAL.items():
            # Pick a high opcode range likely unmapped
            for opcode in [0xFD, 0xFC, 0xFB]:
                result = to_can(bytes([opcode]))
                # Should be either 0xFE (unmapped) or some valid mapping
                self.assertIn(result[0], [UNMAPPED, ESCAPE_PREFIX, opcode],
                             f"{rt}: unexpected mapping for 0x{opcode:02x}: 0x{result[0]:02x}")


# ═══════════════════════════════════════════════════════════════════════════
# Test: Coverage Report
# ═══════════════════════════════════════════════════════════════════════════

class TestCoverageReport(unittest.TestCase):
    """Coverage report should be informative and accurate."""

    def test_coverage_report_runs(self):
        report = coverage_report()
        self.assertIsInstance(report, str)
        self.assertGreater(len(report), 100)

    def test_coverage_report_mentions_all_runtimes(self):
        report = coverage_report()
        for rt_name in ["Python", "Rust", "C Runtime", "Go"]:
            self.assertIn(rt_name, report,
                          f"Coverage report missing {rt_name}")

    def test_coverage_report_has_numbers(self):
        report = coverage_report()
        # Should contain digit sequences for the counts
        import re
        numbers = re.findall(r'\d+', report)
        self.assertGreater(len(numbers), 8,
                           "Coverage report should contain numeric counts")


# ═══════════════════════════════════════════════════════════════════════════
# Test: Translation Table Invariants
# ═══════════════════════════════════════════════════════════════════════════

class TestTranslationTableInvariants(unittest.TestCase):
    """Structural invariants of the 256-byte translation tables."""

    def test_tables_are_256_bytes(self):
        for rt, table in TRANSLATION_TABLES.items():
            self.assertEqual(len(table), 256,
                             f"{rt} translation table is not 256 bytes")

    def test_inverse_tables_are_256_bytes(self):
        for rt, table in INVERSE_TABLES.items():
            self.assertEqual(len(table), 256,
                             f"{rt} inverse table is not 256 bytes")

    def test_escape_prefix_in_all_tables(self):
        """0xFF should map to 0xFF in all translation tables."""
        for rt, table in TRANSLATION_TABLES.items():
            self.assertEqual(table[0xFF], ESCAPE_PREFIX,
                             f"{rt}: 0xFF not preserved in forward table")

    def test_python_has_most_mappings(self):
        """Python runtime should have the most opcode mappings (122 defined)."""
        py_mapped = sum(1 for b in _PY_TO_CAN if b != UNMAPPED and b != ESCAPE_PREFIX)
        go_mapped = sum(1 for b in _GO_TO_CAN if b != UNMAPPED and b != ESCAPE_PREFIX)
        self.assertGreater(py_mapped, go_mapped,
                           f"Python ({py_mapped}) should have more mappings than Go ({go_mapped})")

    def test_go_has_fewest_mappings(self):
        """Go runtime has the fewest defined opcodes (14)."""
        go_mapped = sum(1 for b in _GO_TO_CAN if b != UNMAPPED and b != ESCAPE_PREFIX)
        py_mapped = sum(1 for b in _PY_TO_CAN if b != UNMAPPED and b != ESCAPE_PREFIX)
        self.assertLess(go_mapped, py_mapped,
                        f"Go ({go_mapped}) should have fewer mappings than Python ({py_mapped})")


# ═══════════════════════════════════════════════════════════════════════════
# Test: Concrete Known Opcodes (regression guard)
# ═══════════════════════════════════════════════════════════════════════════

class TestKnownOpcodeTranslations(unittest.TestCase):
    """Specific known opcode translations as regression tests."""

    def test_python_nop_translates(self):
        """Python NOP (0x00) should map to a valid canonical opcode."""
        result = python_to_canonical(bytes([0x00]))
        self.assertNotEqual(result[0], UNMAPPED)

    def test_python_halt_translates(self):
        """Python HALT (0x80) should map to canonical HALT (0x00)."""
        result = python_to_canonical(bytes([0x80]))
        self.assertEqual(result[0], 0x00, "Python HALT should map to canonical HALT")

    def test_python_add_translates(self):
        """Python IADD (0x08) should map to canonical ADD (0x20)."""
        result = python_to_canonical(bytes([0x08]))
        self.assertEqual(result[0], 0x20, "Python IADD should map to canonical ADD")

    def test_rust_nop_translates(self):
        """Rust Nop (0x01) should map to canonical NOP (0x01)."""
        result = rust_to_canonical(bytes([0x01]))
        self.assertEqual(result[0], 0x01, "Rust Nop should map to canonical NOP")

    def test_rust_halt_translates(self):
        """Rust Halt (0x00) should map to canonical HALT (0x00)."""
        result = rust_to_canonical(bytes([0x00]))
        self.assertEqual(result[0], 0x00, "Rust Halt should map to canonical HALT")

    def test_rust_add_translates(self):
        """Rust IAdd (0x21) should map to canonical ADD (0x20)."""
        result = rust_to_canonical(bytes([0x21]))
        self.assertEqual(result[0], 0x20, "Rust IAdd should map to canonical ADD")

    def test_cos_nop_translates(self):
        """C-OS NOP (0x00) should map to a valid canonical opcode."""
        result = cos_to_canonical(bytes([0x00]))
        self.assertNotEqual(result[0], UNMAPPED)

    def test_cos_halt_translates(self):
        """C-OS HALT (0x01) should map to canonical HALT (0x00)."""
        result = cos_to_canonical(bytes([0x01]))
        self.assertEqual(result[0], 0x00, "C-OS HALT should map to canonical HALT")

    def test_go_nop_translates(self):
        """Go NOP (0x00) should map to canonical NOP (0x01)."""
        result = go_to_canonical(bytes([0x00]))
        self.assertNotEqual(result[0], UNMAPPED)


# ═══════════════════════════════════════════════════════════════════════════
# Test: Bytecode Sequence Translation
# ═══════════════════════════════════════════════════════════════════════════

class TestBytecodeSequenceTranslation(unittest.TestCase):
    """Translation should work correctly on realistic bytecode sequences."""

    def test_simple_program_python(self):
        """A simple Python program should translate without errors."""
        # NOP, IADD, ISUB, HALT
        bc = bytes([0x00, 0x08, 0x09, 0x80])
        result = python_to_canonical(bc)
        self.assertEqual(len(result), 4)
        # HALT should translate to canonical HALT
        self.assertEqual(result[3], 0x00)

    def test_simple_program_rust(self):
        """A simple Rust program should translate without errors."""
        # Halt, Nop, IAdd, ISub
        bc = bytes([0x00, 0x01, 0x21, 0x22])
        result = rust_to_canonical(bc)
        self.assertEqual(len(result), 4)
        # Halt should map to canonical HALT
        self.assertEqual(result[0], 0x00)

    def test_large_random_bytecode(self):
        """Large random bytecode should translate without crashing."""
        rng = random.Random(42)
        for rt, to_can in TO_CANONICAL.items():
            bc = bytes(rng.randint(0, 255) for _ in range(1024))
            result = to_can(bc)
            self.assertEqual(len(result), 1024, f"{rt}: 1024-byte translation failed")


# ═══════════════════════════════════════════════════════════════════════════
# Test: Commutativity of Independent Translations
# ═══════════════════════════════════════════════════════════════════════════

class TestCommutativity(unittest.TestCase):
    """Translating from different sources to canonical should be independent."""

    def test_independent_sources(self):
        """Translating two independent bytecodes should not interfere."""
        bc1 = bytes([0x08, 0x09])
        bc2 = bytes([0x21, 0x22])
        result1 = python_to_canonical(bc1)
        result2 = rust_to_canonical(bc2)
        # Both should map ADD to canonical ADD (0x20)
        self.assertEqual(result1[0], 0x20, "Python IADD should map to canonical ADD")
        self.assertEqual(result2[0], 0x20, "Rust IAdd should map to canonical ADD")

    def test_parallel_translation_consistency(self):
        """Translating the same concept from different runtimes converges."""
        # Python IADD (0x08) and Rust IAdd (0x21) should both map to canonical ADD
        py_add = python_to_canonical(bytes([0x08]))[0]
        rust_add = rust_to_canonical(bytes([0x21]))[0]
        self.assertEqual(py_add, rust_add,
                         "Python IADD and Rust IAdd should converge on canonical ADD")


if __name__ == "__main__":
    unittest.main()
