#!/usr/bin/env python3
"""
FLUX Conformance Framework Tests.

Tests for the test framework itself: vector schema validation, manifest
consistency, BytecodeBuilder correctness, unified runner parsing, and
vector content quality checks.

Zero external dependencies — runs with stdlib + pytest only.
"""

import json
import os
import re
import struct
import sys
from pathlib import Path

import pytest

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------

REPO_ROOT = Path(__file__).resolve().parent.parent
VECTORS_DIR = REPO_ROOT / "runners" / "vectors"
UNIFIED_DIR = VECTORS_DIR / "unified"
MANIFEST_PATH = VECTORS_DIR / "manifest.json"
SCHEMA_PATH = REPO_ROOT / "schema" / "test-vector-schema.json"
BUILDER_PATH = REPO_ROOT / "runners" / "python" / "bytecode_builder.py"
RUNNER_PATH = REPO_ROOT / "runners" / "unified_runner.py"

VALID_CATEGORIES = {
    "arithmetic", "float", "logic", "comparison", "branch",
    "stack", "memory", "call", "regions", "a2a", "type",
    "simd", "system", "edge-case",
}

VALID_STATES = {"HALTED", "YIELDED", "ERRORED", "CYCLE_LIMIT"}


# ===========================================================================
# Helper: load a JSON file
# ===========================================================================

def _load_json(path):
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


# ===========================================================================
# 1. MANIFEST CONSISTENCY TESTS
# ===========================================================================

class TestManifestConsistency:
    """Tests that the manifest.json is consistent with actual vector files."""

    @pytest.fixture(scope="class")
    def manifest(self):
        return _load_json(MANIFEST_PATH)

    def test_manifest_exists(self):
        assert MANIFEST_PATH.is_file(), "manifest.json must exist"

    def test_manifest_has_required_fields(self, manifest):
        assert "version" in manifest
        assert "total_vectors" in manifest
        assert "categories" in manifest

    def test_manifest_total_matches_categories(self, manifest):
        """Sum of all category entries must equal total_vectors."""
        actual = sum(len(v) for v in manifest["categories"].values())
        assert actual == manifest["total_vectors"], (
            f"Manifest total {manifest['total_vectors']} != sum of categories {actual}"
        )

    def test_all_manifest_ids_have_files(self, manifest):
        """Every ID in the manifest must have a corresponding .json file."""
        missing = []
        for cat, ids in manifest["categories"].items():
            for vid in ids:
                fpath = VECTORS_DIR / f"{vid}.json"
                if not fpath.is_file():
                    missing.append(f"{cat}/{vid}")
        assert not missing, f"Missing vector files: {missing}"

    def test_no_duplicate_ids_in_manifest(self, manifest):
        """No vector ID should appear in more than one category."""
        seen = {}
        dupes = []
        for cat, ids in manifest["categories"].items():
            for vid in ids:
                if vid in seen:
                    dupes.append(f"{vid} in {seen[vid]} and {cat}")
                else:
                    seen[vid] = cat
        assert not dupes, f"Duplicate IDs: {dupes}"

    def test_all_json_files_in_manifest(self, manifest):
        """Every .json file (except manifest.json) in vectors/ must be in manifest."""
        all_ids = set()
        for ids in manifest["categories"].values():
            all_ids.update(ids)

        orphan_files = []
        for fpath in sorted(VECTORS_DIR.glob("*.json")):
            if fpath.name == "manifest.json":
                continue
            if fpath.stem not in all_ids:
                orphan_files.append(fpath.name)
        assert not orphan_files, f"Orphan vector files not in manifest: {orphan_files}"

    def test_categories_are_valid(self, manifest):
        for cat in manifest["categories"]:
            assert cat in VALID_CATEGORIES, f"Invalid category: {cat}"

    def test_minimum_vectors_per_category(self, manifest):
        """Each non-edge category should have at least 3 vectors."""
        for cat, ids in manifest["categories"].items():
            if cat not in ("edge-case", "a2a"):
                assert len(ids) >= 3, (
                    f"Category '{cat}' has only {len(ids)} vectors (minimum 3)"
                )


# ===========================================================================
# 2. VECTOR SCHEMA / FORMAT VALIDATION TESTS
# ===========================================================================

class TestVectorSchema:
    """Tests that each vector JSON file conforms to the expected format."""

    @pytest.fixture(scope="class")
    def all_vectors(self):
        vectors = []
        for fpath in sorted(VECTORS_DIR.glob("*.json")):
            if fpath.name == "manifest.json":
                continue
            vectors.append((fpath.stem, _load_json(fpath)))
        return vectors

    @pytest.fixture(scope="class")
    def manifest(self):
        return _load_json(MANIFEST_PATH)

    def test_vector_required_fields(self, all_vectors):
        """Each vector must have: id, name, category, description, bytecode_hex, expected."""
        missing = []
        for vid, vec in all_vectors:
            required = {"id", "name", "category", "description", "bytecode_hex", "expected"}
            actual_keys = set(vec.keys())
            missing_fields = required - actual_keys
            if missing_fields:
                missing.append(f"{vid}: missing {missing_fields}")
        assert not missing, f"Vectors with missing fields: {missing}"

    def test_vector_id_matches_filename(self, all_vectors):
        """Vector 'id' must match its filename (without extension)."""
        bad = []
        for vid, vec in all_vectors:
            if vec.get("id") != vid:
                bad.append(f"file={vid}, id={vec.get('id')}")
        assert not bad, f"ID/filename mismatches: {bad}"

    def test_vector_id_format(self, all_vectors):
        """Vector IDs should use lowercase alphanumeric with hyphens."""
        bad = []
        for vid, vec in all_vectors:
            if not re.match(r'^[a-z0-9][a-z0-9-]*$', vid):
                bad.append(vid)
        assert not bad, f"Invalid ID format: {bad}"

    def test_vector_category_valid(self, all_vectors):
        """Each vector category must be in the valid set."""
        bad = []
        for vid, vec in all_vectors:
            if vec.get("category") not in VALID_CATEGORIES:
                bad.append(f"{vid}: {vec.get('category')}")
        assert not bad, f"Invalid categories: {bad}"

    def test_vector_bytecode_hex_format(self, all_vectors):
        """bytecode_hex must be a valid hex string."""
        bad = []
        for vid, vec in all_vectors:
            bc = vec.get("bytecode_hex", "")
            if not bc:
                bad.append(f"{vid}: empty bytecode_hex")
                continue
            cleaned = bc.replace(" ", "").replace("\n", "").replace("\t", "")
            if not re.match(r'^[0-9a-fA-F]+$', cleaned):
                bad.append(f"{vid}: non-hex chars in bytecode_hex")
            if len(cleaned) % 2 != 0:
                bad.append(f"{vid}: odd-length hex string")
        assert not bad, f"Bad bytecode_hex: {bad}"

    def test_vector_expected_has_final_state(self, all_vectors):
        """expected.final_state must be present and valid."""
        bad = []
        for vid, vec in all_vectors:
            exp = vec.get("expected", {})
            state = exp.get("final_state", "")
            if state not in VALID_STATES:
                bad.append(f"{vid}: invalid final_state '{state}'")
        assert not bad, f"Invalid final_state: {bad}"

    def test_vector_bytecode_not_empty(self, all_vectors):
        """bytecode_hex should not be empty (except for special cases)."""
        bad = []
        for vid, vec in all_vectors:
            bc = vec.get("bytecode_hex", "").strip()
            if not bc:
                bad.append(vid)
        assert not bad, f"Empty bytecode: {bad}"

    def test_vector_description_not_empty(self, all_vectors):
        bad = []
        for vid, vec in all_vectors:
            if not vec.get("description", "").strip():
                bad.append(vid)
        assert not bad, f"Empty description: {bad}"

    def test_vector_manifest_category_match(self, all_vectors, manifest):
        """Each vector's category must match what the manifest says."""
        bad = []
        manifest_cat = {}
        for cat, ids in manifest["categories"].items():
            for vid in ids:
                manifest_cat[vid] = cat
        for vid, vec in all_vectors:
            if vid in manifest_cat:
                if manifest_cat[vid] != vec.get("category"):
                    bad.append(f"{vid}: manifest={manifest_cat[vid]}, vector={vec.get('category')}")
        assert not bad, f"Category mismatches: {bad}"


# ===========================================================================
# 3. BYTECODEBUILDER UNIT TESTS
# ===========================================================================

class TestBytecodeBuilder:
    """Tests for the BytecodeBuilder utility."""

    def test_import(self):
        sys.path.insert(0, str(BUILDER_PATH.parent))
        from bytecode_builder import BytecodeBuilder
        assert BytecodeBuilder is not None

    @pytest.fixture(scope="class")
    def Builder(self):
        sys.path.insert(0, str(BUILDER_PATH.parent))
        from bytecode_builder import BytecodeBuilder
        return BytecodeBuilder

    def test_halt_single_byte(self, Builder):
        bc = Builder().halt()
        assert bc.build() == bytes([0x80])

    def test_nop_single_byte(self, Builder):
        bc = Builder().nop()
        assert bc.build() == bytes([0x00])

    def test_movi_produces_4_bytes(self, Builder):
        bc = Builder().movi(1, 42)
        result = bc.build()
        assert len(result) == 4
        assert result[0] == 0x2B  # MOVI opcode
        assert result[1] == 1     # register
        imm = struct.unpack('<h', bytes(result[2:4]))[0]
        assert imm == 42

    def test_movi_negative(self, Builder):
        bc = Builder().movi(0, -1)
        result = bc.build()
        imm = struct.unpack('<h', bytes(result[2:4]))[0]
        assert imm == -1

    def test_movi_max_i16(self, Builder):
        bc = Builder().movi(0, 32767)
        result = bc.build()
        imm = struct.unpack('<h', bytes(result[2:4]))[0]
        assert imm == 32767

    def test_movi_min_i16(self, Builder):
        bc = Builder().movi(0, -32768)
        result = bc.build()
        imm = struct.unpack('<h', bytes(result[2:4]))[0]
        assert imm == -32768

    def test_hex_method(self, Builder):
        bc = Builder().halt()
        assert bc.hex() == "80"

    def test_size_method(self, Builder):
        bc = Builder().nop().nop().halt()
        assert bc.size() == 3
        assert len(bc) == 3

    def test_iadd_format_e(self, Builder):
        """IADD should be Format E: [opcode][rd][rs1][rs2] = 4 bytes."""
        bc = Builder().iadd(0, 1, 2)
        result = bc.build()
        assert len(result) == 4
        assert result[0] == 0x08  # IADD
        assert result[1] == 0     # rd
        assert result[2] == 1     # rs1
        assert result[3] == 2     # rs2

    def test_push_pop_format_b(self, Builder):
        """PUSH and POP should be Format B: 2 bytes."""
        bc = Builder().push(1).pop(0)
        result = bc.build()
        assert len(result) == 4
        assert result[0] == 0x20  # PUSH
        assert result[1] == 1
        assert result[2] == 0x21  # POP
        assert result[3] == 0

    def test_label_forward_jump(self, Builder):
        """Forward label references should resolve correctly."""
        bc = Builder()
        bc.jmp_label("target")
        bc.movi(0, 0).halt()
        bc.label("target")
        bc.movi(0, 1).halt()
        result = bc.build()
        assert len(result) > 0
        # Should not raise ValueError for unresolved labels
        bc.build()

    def test_label_backward_jump(self, Builder):
        """Backward label references should resolve correctly."""
        bc = Builder()
        bc.label("start")
        bc.movi(0, 42)
        bc.jmp_label("start")  # backward jump
        bc.halt()
        result = bc.build()
        assert len(result) > 0

    def test_unresolved_label_raises(self, Builder):
        """Building with unresolved labels should raise ValueError."""
        bc = Builder().jmp_label("nonexistent").halt()
        with pytest.raises(ValueError, match="Unresolved labels"):
            bc.build()

    def test_chaining_returns_self(self, Builder):
        """Builder methods should return self for chaining."""
        bc = Builder()
        assert bc.nop() is bc
        assert bc.halt() is bc
        assert bc.movi(0, 1) is bc
        assert bc.iadd(0, 1, 2) is bc

    def test_empty_builder(self, Builder):
        """Empty builder produces empty bytecode."""
        bc = Builder()
        assert bc.build() == b""
        assert bc.hex() == ""

    def test_icmp_format(self, Builder):
        """ICMP should be 4 bytes: [opcode][cond][a_reg][b_reg]."""
        bc = Builder().icmp(0, 1, 2)
        result = bc.build()
        assert len(result) == 4
        assert result[0] == 0x18  # ICMP
        assert result[1] == 0     # EQ condition
        assert result[2] == 1
        assert result[3] == 2


# ===========================================================================
# 4. UNIFIED RUNNER PARSER TESTS
# ===========================================================================

class TestUnifiedRunnerParser:
    """Tests for the unified runner's bytecode/reg parsing."""

    @pytest.fixture(scope="class")
    def runner_mod(self):
        sys.path.insert(0, str(RUNNER_PATH.parent))
        import unified_runner
        return unified_runner

    def test_parse_bytecode_list(self, runner_mod):
        result = runner_mod.ConformanceRunner._parse_bytecode(
            {"bytecode": [0x00, 0x01, 0x02]}
        )
        assert result == bytes([0x00, 0x01, 0x02])

    def test_parse_bytecode_hex_string(self, runner_mod):
        result = runner_mod.ConformanceRunner._parse_bytecode(
            {"bytecode_hex": "000102"}
        )
        assert result == bytes([0x00, 0x01, 0x02])

    def test_parse_bytecode_hex_with_spaces(self, runner_mod):
        """Hex strings with spaces should be handled."""
        result = runner_mod.ConformanceRunner._parse_bytecode(
            {"bytecode_hex": "00 01 02 03"}
        )
        assert result == bytes([0x00, 0x01, 0x02, 0x03])

    def test_parse_bytecode_hex_with_0x_prefix(self, runner_mod):
        result = runner_mod.ConformanceRunner._parse_bytecode(
            {"bytecode_hex": "0x000102"}
        )
        assert result == bytes([0x00, 0x01, 0x02])

    def test_parse_bytecode_missing_raises(self, runner_mod):
        with pytest.raises(KeyError):
            runner_mod.ConformanceRunner._parse_bytecode({})

    def test_parse_regs_none(self, runner_mod):
        assert runner_mod.ConformanceRunner._parse_regs(None) == {}

    def test_parse_regs_dict_r_format(self, runner_mod):
        result = runner_mod.ConformanceRunner._parse_regs({"R1": 42, "R3": 7})
        assert result == {1: 42, 3: 7}

    def test_parse_regs_dict_lowercase(self, runner_mod):
        result = runner_mod.ConformanceRunner._parse_regs({"r2": 99})
        assert result == {2: 99}

    def test_parse_regs_dict_int_keys(self, runner_mod):
        result = runner_mod.ConformanceRunner._parse_regs({1: 42})
        assert result == {1: 42}

    def test_parse_regs_list(self, runner_mod):
        result = runner_mod.ConformanceRunner._parse_regs([0, 42, 7])
        assert result == {1: 42, 2: 7}  # R0 skipped

    def test_parse_expected_regs_flat(self, runner_mod):
        vec = {"expected_registers": {"R1": 42}}
        result = runner_mod.ConformanceRunner._parse_expected_regs(vec)
        assert result == {1: 42}

    def test_parse_expected_regs_nested_gp(self, runner_mod):
        vec = {"expected": {"gp": {"1": 42, "2": 7}}}
        result = runner_mod.ConformanceRunner._parse_expected_regs(vec)
        assert result == {1: 42, 2: 7}

    def test_parse_expected_halt_nested(self, runner_mod):
        vec = {"expected": {"final_state": "HALTED"}}
        halted, error = runner_mod.ConformanceRunner._parse_expected_halt(vec)
        assert halted is True
        assert error is None

    def test_parse_expected_halt_errored(self, runner_mod):
        vec = {"expected": {"final_state": "ERRORED"}}
        halted, error = runner_mod.ConformanceRunner._parse_expected_halt(vec)
        assert error is True

    def test_parse_expected_halt_flat(self, runner_mod):
        vec = {"expected_halted": True}
        halted, error = runner_mod.ConformanceRunner._parse_expected_halt(vec)
        assert halted is True


# ===========================================================================
# 5. UNIFIED RUNNER VM TESTS (built-in minimal VM)
# ===========================================================================

class TestUnifiedRunnerVM:
    """Tests for the FluxMiniVM inside unified_runner."""

    @pytest.fixture(scope="class")
    def runner_mod(self):
        sys.path.insert(0, str(RUNNER_PATH.parent))
        import unified_runner
        return unified_runner

    @pytest.fixture
    def vm(self, runner_mod):
        return runner_mod.FluxMiniVM()

    def test_vm_initial_state(self, vm):
        assert not vm.halted
        assert not vm.error_flag
        assert vm.pc == 0
        assert vm.insn_count == 0

    def test_vm_r0_immutable(self, runner_mod):
        vm = runner_mod.FluxMiniVM()
        vm.wr(0, 42)
        assert vm.rr(0) == 0  # R0 always reads as 0

    def test_vm_halt(self, runner_mod):
        vm = runner_mod.FluxMiniVM()
        vm.execute(bytes([0x00]))  # HALT
        assert vm.halted

    def test_vm_nop(self, runner_mod):
        vm = runner_mod.FluxMiniVM()
        vm.execute(bytes([0x01, 0x00]))  # NOP, HALT
        assert vm.halted
        assert vm.insn_count == 2

    def test_vm_movi(self, runner_mod):
        vm = runner_mod.FluxMiniVM()
        # MOVI R1, 42 = [0x18, 0x01, 0x2A, 0x00]
        vm.execute(bytes([0x18, 0x01, 0x2A, 0x00, 0x00]))
        assert vm.rr(1) == 42
        assert vm.halted

    def test_vm_add(self, runner_mod):
        vm = runner_mod.FluxMiniVM()
        # MOVI R1, 3; MOVI R2, 4; ADD R1, R1, R2; HALT
        bytecode = bytes([
            0x18, 0x01, 0x03, 0x00,  # MOVI R1, 3
            0x18, 0x02, 0x04, 0x00,  # MOVI R2, 4
            0x20, 0x01, 0x01, 0x02,  # ADD R1, R1, R2
            0x00,                    # HALT
        ])
        vm.execute(bytecode)
        assert vm.rr(1) == 7

    def test_vm_sub(self, runner_mod):
        vm = runner_mod.FluxMiniVM()
        bytecode = bytes([
            0x18, 0x01, 0x0A, 0x00,  # MOVI R1, 10
            0x18, 0x02, 0x03, 0x00,  # MOVI R2, 3
            0x21, 0x01, 0x01, 0x02,  # SUB R1, R1, R2
            0x00,
        ])
        vm.execute(bytecode)
        assert vm.rr(1) == 7

    def test_vm_mul(self, runner_mod):
        vm = runner_mod.FluxMiniVM()
        bytecode = bytes([
            0x18, 0x01, 0x06, 0x00,  # MOVI R1, 6
            0x18, 0x02, 0x07, 0x00,  # MOVI R2, 7
            0x22, 0x01, 0x01, 0x02,  # MUL R1, R1, R2
            0x00,
        ])
        vm.execute(bytecode)
        assert vm.rr(1) == 42

    def test_vm_div_by_zero(self, runner_mod):
        vm = runner_mod.FluxMiniVM()
        bytecode = bytes([
            0x18, 0x01, 0x2A, 0x00,  # MOVI R1, 42
            0x18, 0x02, 0x00, 0x00,  # MOVI R2, 0
            0x23, 0x01, 0x01, 0x02,  # DIV R1, R1, R2
            0x00,
        ])
        vm.execute(bytecode)
        assert vm.error_flag
        assert vm.halted

    def test_vm_jz_taken(self, runner_mod):
        vm = runner_mod.FluxMiniVM()
        # MOVI R1, 0; JZ R1, +3; MOVI R2, 1; MOVI R2, 0; HALT
        # Jump over MOVI R2, 1 → R2 stays 0
        bytecode = bytes([
            0x18, 0x01, 0x00, 0x00,  # MOVI R1, 0
            0x44, 0x01, 0x05, 0x00,  # JZ R1, +5
            0x18, 0x02, 0x01, 0x00,  # MOVI R2, 1 (skipped)
            0x18, 0x02, 0x00, 0x00,  # MOVI R2, 0
            0x00,                    # HALT
        ])
        vm.execute(bytecode)
        assert vm.rr(2) == 0

    def test_vm_jz_not_taken(self, runner_mod):
        vm = runner_mod.FluxMiniVM()
        # MOVI R1, 5; JZ R1, +3; MOVI R2, 1; HALT
        bytecode = bytes([
            0x18, 0x01, 0x05, 0x00,  # MOVI R1, 5
            0x44, 0x01, 0x05, 0x00,  # JZ R1, +5 (not taken)
            0x18, 0x02, 0x01, 0x00,  # MOVI R2, 1 (executed)
            0x00,                    # HALT
        ])
        vm.execute(bytecode)
        assert vm.rr(2) == 1

    def test_vm_jnz_loop(self, runner_mod):
        vm = runner_mod.FluxMiniVM()
        # MOVI R1, 3; [loop] DEC R1; JNZ R1, -6; HALT
        # After JNZ fetch (offset 6, 4 bytes), PC=10, target=4, imm=4-10=-6
        bytecode = bytes([
            0x18, 0x01, 0x03, 0x00,  # MOVI R1, 3
            0x09, 0x01,               # DEC R1
            0x45, 0x01, 0xFA, 0xFF,  # JNZ R1, -6
            0x00,                    # HALT
        ])
        vm.execute(bytecode)
        assert vm.rr(1) == 0
        assert vm.halted

    def test_vm_push_pop(self, runner_mod):
        vm = runner_mod.FluxMiniVM()
        # MOVI R1, 42; PUSH R1; MOVI R1, 0; POP R2; HALT
        bytecode = bytes([
            0x18, 0x01, 0x2A, 0x00,  # MOVI R1, 42
            0x0C, 0x01,               # PUSH R1
            0x18, 0x01, 0x00, 0x00,  # MOVI R1, 0
            0x0D, 0x02,               # POP R2
            0x00,                    # HALT
        ])
        vm.execute(bytecode)
        assert vm.rr(2) == 42

    def test_vm_call_ret(self, runner_mod):
        vm = runner_mod.FluxMiniVM()
        # MOVI R1, 21; CALL +1; HALT; (func:) ADD R1, R1, R1; RET
        # After CALL fetch (offset 4, 4 bytes), PC=8, target=9, imm=9-8=1
        bytecode = bytes([
            0x18, 0x01, 0x15, 0x00,  # MOVI R1, 21
            0x4A, 0x00, 0x01, 0x00,  # CALL +1 (to offset 9)
            0x00,                    # HALT (return lands here)
            0x20, 0x01, 0x01, 0x01,  # ADD R1, R1, R1 (R1 = 42)
            0x02,                    # RET (returns to offset 8 = HALT)
        ])
        vm.execute(bytecode)
        assert vm.rr(1) == 42
        assert vm.halted


# ===========================================================================
# 6. CONTENT QUALITY TESTS
# ===========================================================================

class TestContentQuality:
    """Tests for quality of test vector content."""

    @pytest.fixture(scope="class")
    def all_vectors(self):
        vectors = []
        for fpath in sorted(VECTORS_DIR.glob("*.json")):
            if fpath.name == "manifest.json":
                continue
            vectors.append((fpath.stem, _load_json(fpath)))
        return vectors

    def test_no_zero_length_bytecode(self, all_vectors):
        """No vector should have empty bytecode."""
        bad = [vid for vid, v in all_vectors if not v.get("bytecode_hex", "").strip()]
        assert not bad, f"Zero-length bytecode: {bad}"

    def test_description_min_length(self, all_vectors):
        """Descriptions should be at least 10 characters."""
        bad = [vid for vid, v in all_vectors if len(v.get("description", "")) < 10]
        assert not bad, f"Short descriptions (< 10 chars): {bad}"

    def test_name_includes_opcode_or_category(self, all_vectors):
        """Vector names should reference an opcode or concept."""
        # This is a soft check — just verify no empty names
        bad = [vid for vid, v in all_vectors if not v.get("name", "").strip()]
        assert not bad, f"Empty names: {bad}"

    def test_error_vectors_have_error_type(self, all_vectors):
        """Vectors expecting ERRORED should have error_type set."""
        bad = []
        for vid, v in all_vectors:
            exp = v.get("expected", {})
            if exp.get("final_state") == "ERRORED":
                if "error_type" not in exp:
                    bad.append(vid)
        assert not bad, f"ERRORED vectors missing error_type: {bad}"


# ===========================================================================
# 7. COVERAGE ENFORCEMENT TESTS
# ===========================================================================

class TestCoverageEnforcement:
    """Ensure adequate coverage across all categories."""

    @pytest.fixture(scope="class")
    def manifest(self):
        return _load_json(MANIFEST_PATH)

    def test_total_vector_count(self, manifest):
        """Should have at least 100 total vectors."""
        assert manifest["total_vectors"] >= 100, (
            f"Only {manifest['total_vectors']} vectors (need >= 100)"
        )

    def test_all_10_categories_present(self, manifest):
        """All 10 main categories must be represented."""
        required = {"arithmetic", "logic", "comparison", "branch", "stack",
                     "memory", "float", "a2a", "system", "edge-case"}
        present = set(manifest["categories"].keys())
        missing = required - present
        assert not missing, f"Missing categories: {missing}"

    def test_arithmetic_coverage(self, manifest):
        """Arithmetic should cover ADD, SUB, MUL, DIV, MOD, NEG, INC, DEC, MOV, MOVI."""
        ids = manifest["categories"].get("arithmetic", [])
        opcodes = ["iadd", "isub", "imul", "idiv", "imod", "ineg", "inc", "dec", "mov", "movi"]
        missing = [op for op in opcodes if not any(op in vid for vid in ids)]
        assert not missing, f"Arithmetic missing coverage for: {missing}"

    def test_logic_coverage(self, manifest):
        """Logic should cover AND, OR, XOR, NOT, SHL, SHR."""
        ids = manifest["categories"].get("logic", [])
        opcodes = ["iand", "ior", "ixor", "inot", "ishl", "ishr"]
        missing = [op for op in opcodes if not any(op in vid for vid in ids)]
        assert not missing, f"Logic missing coverage for: {missing}"

    def test_branch_coverage(self, manifest):
        """Branch should cover JMP, JZ, JNZ, CALL, RET."""
        ids = manifest["categories"].get("branch", [])
        opcodes = ["jmp", "jz", "jnz", "call"]
        missing = [op for op in opcodes if not any(op in vid for vid in ids)]
        assert not missing, f"Branch missing coverage for: {missing}"

    def test_stack_coverage(self, manifest):
        """Stack should cover PUSH, POP, DUP, SWAP."""
        ids = manifest["categories"].get("stack", [])
        ops = ["push", "pop", "dup", "swap"]
        missing = [op for op in ops if not any(op in vid for vid in ids)]
        assert not missing, f"Stack missing coverage for: {missing}"

    def test_edge_case_has_division_by_zero(self, manifest):
        """Edge cases should include division by zero."""
        ids = manifest["categories"].get("edge-case", [])
        has_div_zero = any("div-zero" in vid or "mod-zero" in vid or "rem-zero" in vid for vid in ids)
        assert has_div_zero, "Edge case missing division/modulo by zero test"


# ===========================================================================
# 8. SCHEMA FILE TESTS
# ===========================================================================

class TestSchemaFile:
    """Tests for the JSON schema file itself."""

    def test_schema_exists(self):
        assert SCHEMA_PATH.is_file(), "test-vector-schema.json must exist"

    def test_schema_valid_json(self):
        data = _load_json(SCHEMA_PATH)
        assert "$schema" in data
        assert "properties" in data
        assert "required" in data

    def test_schema_required_fields_match(self):
        data = _load_json(SCHEMA_PATH)
        required = set(data.get("required", []))
        expected = {"id", "name", "category", "description", "bytecode_hex", "expected"}
        assert expected.issubset(required), f"Schema missing required fields: {expected - required}"
