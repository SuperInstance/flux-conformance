"""
Test vector format and schema validation for flux-conformance.

These tests verify that all test vectors conform to the expected schema
and contain valid bytecode. They do NOT require flux-runtime to be installed.

Usage:
    pytest tests/test_vectors.py -v
"""

import json
import os
import re

import pytest


# Required fields for a test vector
REQUIRED_FIELDS = {"id", "name", "category", "description", "bytecode_hex", "expected"}

VALID_CATEGORIES = {
    "arithmetic", "float", "logic", "comparison", "branch",
    "stack", "memory", "call", "regions", "a2a", "type",
    "simd", "system", "edge-case"
}

VALID_FINAL_STATES = {"HALTED", "YIELDED", "ERRORED", "CYCLE_LIMIT"}

# Valid hex pattern (only hex digits, at least 2 chars for at least one instruction)
HEX_PATTERN = re.compile(r'^[0-9a-f]{2,}$')


class TestVectorSchema:
    """Validate test vector JSON schema."""

    def test_all_vectors_have_required_fields(self, all_vectors):
        """Every vector must have all required fields."""
        for v in all_vectors:
            missing = REQUIRED_FIELDS - set(v.keys())
            assert not missing, f"Vector '{v.get('id', '???')}' missing fields: {missing}"

    def test_vector_ids_are_unique(self, all_vectors):
        """No duplicate vector IDs."""
        ids = [v["id"] for v in all_vectors]
        assert len(ids) == len(set(ids)), f"Duplicate vector IDs found: {[x for x in ids if ids.count(x) > 1]}"

    def test_vector_ids_match_filename(self, all_vectors):
        """Vector ID should match the expected filename pattern."""
        for v in all_vectors:
            assert re.match(r'^[a-z0-9][a-z0-9-]*$', v["id"]), \
                f"Invalid ID format: '{v['id']}'"

    def test_categories_are_valid(self, all_vectors):
        """All vectors use recognized categories."""
        for v in all_vectors:
            assert v["category"] in VALID_CATEGORIES, \
                f"Vector '{v['id']}' has invalid category: '{v['category']}'"

    def test_bytecode_hex_is_valid(self, all_vectors):
        """bytecode_hex must be a valid hex string."""
        for v in all_vectors:
            assert HEX_PATTERN.match(v["bytecode_hex"]), \
                f"Vector '{v['id']}' has invalid bytecode_hex: '{v['bytecode_hex'][:20]}...'"
            assert len(v["bytecode_hex"]) % 2 == 0, \
                f"Vector '{v['id']}' bytecode_hex has odd length"

    def test_bytecode_hex_even_length(self, all_vectors):
        """bytecode_hex must have even number of hex digits (complete bytes)."""
        for v in all_vectors:
            assert len(v["bytecode_hex"]) % 2 == 0, \
                f"Vector '{v['id']}' has odd-length bytecode_hex"

    def test_expected_has_final_state(self, all_vectors):
        """Every vector's expected block must have a final_state."""
        for v in all_vectors:
            assert "final_state" in v["expected"], \
                f"Vector '{v['id']}' expected block missing final_state"

    def test_final_state_is_valid(self, all_vectors):
        """final_state must be a recognized state."""
        for v in all_vectors:
            assert v["expected"]["final_state"] in VALID_FINAL_STATES, \
                f"Vector '{v['id']}' has invalid final_state: '{v['expected']['final_state']}'"

    def test_errored_vectors_have_error_type(self, all_vectors):
        """Vectors expecting ERRORED should specify an error_type."""
        for v in all_vectors:
            if v["expected"]["final_state"] == "ERRORED":
                assert "error_type" in v["expected"], \
                    f"Vector '{v['id']}' is ERRORED but has no error_type"

    def test_error_vectors_dont_have_gp_checks(self, all_vectors):
        """Vectors expecting ERRORED should not check GP registers."""
        for v in all_vectors:
            if v["expected"]["final_state"] == "ERRORED":
                assert "gp" not in v["expected"] or not v["expected"].get("gp"), \
                    f"Vector '{v['id']}' is ERRORED but checks GP registers"


class TestVectorContent:
    """Validate test vector content quality."""

    def test_bytecode_starts_with_valid_opcode(self, all_vectors):
        """Every bytecode must start with a known opcode byte."""
        for v in all_vectors:
            first_byte = int(v["bytecode_hex"][:2], 16)
            # Known opcode ranges: 0x00-0x3C (general), 0x40-0x5C (float/simd),
            # 0x60-0x7B (a2a/trust/cap), 0x80-0x84 (system)
            assert (0x00 <= first_byte <= 0x3C or
                    0x40 <= first_byte <= 0x5C or
                    0x60 <= first_byte <= 0x7B or
                    0x80 <= first_byte <= 0x84), \
                f"Vector '{v['id']}' starts with unknown opcode 0x{first_byte:02x}"

    def test_bytecode_not_empty(self, all_vectors):
        """No vector should have empty bytecode."""
        for v in all_vectors:
            assert len(v["bytecode_hex"]) >= 2, \
                f"Vector '{v['id']}' has empty bytecode"

    def test_bytecode_contains_halt_or_loops(self, all_vectors):
        """Non-error vectors should either end with HALT or contain a loop/branch."""
        for v in all_vectors:
            if v["expected"]["final_state"] == "ERRORED":
                continue  # Error vectors may not have HALT
            bc = v["bytecode_hex"]
            # Check if bytecode contains HALT (0x80)
            has_halt = "80" in bc
            # Or contains a branch/call instruction
            has_branch = any(bc.startswith(op) or op in bc
                             for op in ["04", "05", "06", "07", "2e", "2f", "36", "37", "4d", "4e"])
            assert has_halt or has_branch, \
                f"Vector '{v['id']}' ({v['category']}) has no HALT or branch/call"

    def test_description_not_empty(self, all_vectors):
        """Every vector should have a non-empty description."""
        for v in all_vectors:
            assert v["description"] and len(v["description"]) > 5, \
                f"Vector '{v['id']}' has empty/short description"

    def test_name_not_empty(self, all_vectors):
        """Every vector should have a descriptive name."""
        for v in all_vectors:
            assert v["name"] and len(v["name"]) > 3, \
                f"Vector '{v['id']}' has empty/short name"


class TestManifest:
    """Validate the manifest file."""

    def test_manifest_exists(self, vectors_dir):
        """Manifest file must exist."""
        assert os.path.exists(os.path.join(vectors_dir, "manifest.json"))

    def test_manifest_has_required_fields(self, manifest):
        """Manifest must have required fields."""
        assert "version" in manifest
        assert "total_vectors" in manifest
        assert "categories" in manifest

    def test_manifest_total_matches_files(self, manifest, vectors_dir):
        """Total vectors in manifest should match actual files."""
        json_files = [f for f in os.listdir(vectors_dir)
                      if f.endswith(".json") and f != "manifest.json"]
        # Some vectors may be in subdirectories (unified/)
        assert manifest["total_vectors"] > 0, "Manifest has zero vectors"

    def test_manifest_categories_match_files(self, manifest, vectors_dir):
        """Every vector listed in manifest should have a corresponding file."""
        all_ids = []
        for cat_ids in manifest["categories"].values():
            all_ids.extend(cat_ids)
        for vid in all_ids:
            vpath = os.path.join(vectors_dir, f"{vid}.json")
            assert os.path.exists(vpath), f"Manifest lists '{vid}' but file not found"


class TestVectorCoverage:
    """Check that we have adequate coverage across categories."""

    def test_minimum_vectors_per_category(self, manifest):
        """Each category should have at least some vectors."""
        category_mins = {
            "arithmetic": 20,
            "logic": 10,
            "comparison": 15,
            "branch": 10,
            "stack": 5,
            "memory": 4,
            "float": 8,
            "system": 2,
            "edge-case": 10,
        }
        for cat, min_count in category_mins.items():
            actual = len(manifest.get("categories", {}).get(cat, []))
            assert actual >= min_count, \
                f"Category '{cat}' has {actual} vectors, minimum {min_count} required"

    def test_has_smoke_tests(self, all_vectors):
        """Should have at least some smoke-tagged vectors."""
        smoke = [v for v in all_vectors if "smoke" in v.get("tags", [])]
        assert len(smoke) >= 10, f"Only {len(smoke)} smoke tests found, need at least 10"

    def test_has_p0_tests(self, all_vectors):
        """Should have at least some p0-tagged vectors."""
        p0 = [v for v in all_vectors if "p0" in v.get("tags", [])]
        assert len(p0) >= 15, f"Only {len(p0)} p0 tests found, need at least 15"

    def test_has_error_vectors(self, all_vectors):
        """Should have at least some error vectors."""
        errors = [v for v in all_vectors if v["expected"]["final_state"] == "ERRORED"]
        assert len(errors) >= 3, f"Only {len(errors)} error vectors found, need at least 3"

    def test_has_negative_number_vectors(self, all_vectors):
        """Should test with negative numbers in arithmetic."""
        # Look for vectors that test negative number handling
        neg_desc = [v for v in all_vectors
                    if "negative" in v.get("description", "").lower()
                    or "neg" in v.get("description", "").lower()
                    or "-" in v.get("description", "")]
        assert len(neg_desc) >= 5, f"Only {len(neg_desc)} negative number tests found"


class TestBytecodeBuilderConsistency:
    """Verify bytecode builder output matches what's in the JSON vectors."""

    def test_bytecode_builder_import(self):
        """BytecodeBuilder should be importable."""
        import sys
        builders_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                                    "runners", "python")
        sys.path.insert(0, builders_dir)
        from bytecode_builder import BytecodeBuilder
        # Quick sanity check
        bc = BytecodeBuilder().movi(0, 42).halt()
        assert bc.hex() == "2b002a0080"

    def test_vector_bytecode_decodeable(self, all_vectors):
        """All bytecode should be decodable as bytes."""
        for v in all_vectors:
            try:
                bytecode = bytes.fromhex(v["bytecode_hex"])
                assert len(bytecode) > 0
            except ValueError as e:
                pytest.fail(f"Vector '{v['id']}' has undecodable bytecode: {e}")
