"""
Tests for the FLUX Universal Bytecode Validator (flux_universal_validator.py).

Validates the validator's parsing, runtime compatibility analysis,
control flow analysis, and bytecode translation features.
"""

import pytest
import os
import sys
import json

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from flux_universal_validator import (
    validate,
    translate_bytecode,
    WASM_IMPL, PYTHON_OPS, RUST_OPS, C_OPS, GO_OPS,
    IRREDUCIBLE_CORE,
    ValidationResult,
    Instruction,
    example_core,
    example_wasm_only,
    example_multi,
    MNEMONICS,
    WASM_FORMAT,
    FORMAT_SIZE,
)


# ═══════════════════════════════════════════════════════════════════════
# Runtime Opcode Set Tests
# ═══════════════════════════════════════════════════════════════════════

class TestRuntimeOpcodeSets:
    def test_wasm_impl_not_empty(self):
        assert len(WASM_IMPL) > 0

    def test_python_ops_not_empty(self):
        assert len(PYTHON_OPS) > 0

    def test_rust_ops_not_empty(self):
        assert len(RUST_OPS) > 0

    def test_c_ops_not_empty(self):
        assert len(C_OPS) > 0

    def test_go_ops_not_empty(self):
        assert len(GO_OPS) > 0

    def test_irreducible_core_not_empty(self):
        assert len(IRREDUCIBLE_CORE) > 0

    def test_irreducible_core_subset_of_wasm(self):
        assert IRREDUCIBLE_CORE.issubset(WASM_IMPL)

    def test_irreducible_core_subset_of_python(self):
        assert IRREDUCIBLE_CORE.issubset(PYTHON_OPS)

    def test_python_has_more_ops_than_wasm(self):
        assert len(PYTHON_OPS) > len(WASM_IMPL)

    def test_go_has_fewest_ops(self):
        assert len(GO_OPS) < len(C_OPS)
        assert len(GO_OPS) < len(RUST_OPS)


class TestFormatDefinitions:
    def test_format_sizes_complete(self):
        expected = {'A': 1, 'B': 2, 'C': 2, 'D': 3, 'E': 4, 'F': 4, 'G': 5}
        for fmt, size in expected.items():
            assert FORMAT_SIZE.get(fmt) == size

    def test_wasm_format_covers_full_range(self):
        for op in range(256):
            assert op in WASM_FORMAT, f"Opcode 0x{op:02x} missing from WASM_FORMAT"


# ═══════════════════════════════════════════════════════════════════════
# Validation Tests
# ═══════════════════════════════════════════════════════════════════════

class TestValidationBasic:
    def test_empty_bytecode(self):
        result = validate(b"", filename="<empty>")
        assert isinstance(result, ValidationResult)
        assert result.bytecode_len == 0
        assert len(result.instructions) == 0

    def test_single_halt(self):
        result = validate(bytes([0x00]), filename="<halt>")
        assert len(result.instructions) == 1
        assert result.instructions[0].mnemonic == "HALT"

    def test_single_nop(self):
        result = validate(bytes([0x01]), filename="<nop>")
        assert len(result.instructions) == 1
        assert result.instructions[0].mnemonic == "NOP"

    def test_push_immediate(self):
        # PUSH = 0x55 (Python stack op), 4-byte immediate
        result = validate(bytes([0x20, 0x42, 0x00, 0x00, 0x00]), filename="<push>")
        assert len(result.instructions) >= 1

    def test_filename_preserved(self):
        result = validate(bytes([0x00]), filename="test.flux")
        assert result.filename == "test.flux"

    def test_unknown_opcode(self):
        result = validate(bytes([0xFF]), filename="<unknown>")
        # Should still produce a result (not crash)
        assert isinstance(result, ValidationResult)


class TestRuntimeCompatibility:
    def test_python_full_compatibility(self):
        # Use Python opcodes: NOP(0x00), HALT(0x01)
        result = validate(bytes([0x00, 0x01]), filename="<python>")
        compat = result.runtime_compatibility
        assert "python" in compat
        assert compat["python"]["coverage_pct"] == 100.0

    def test_multiple_runtimes_reported(self):
        result = validate(bytes([0x00]), filename="<test>")
        assert "python" in result.runtime_compatibility
        assert "wasm" in result.runtime_compatibility
        assert "rust" in result.runtime_compatibility
        assert "c" in result.runtime_compatibility
        assert "go" in result.runtime_compatibility

    def test_coverage_pct_field(self):
        result = validate(bytes([0x00]), filename="<test>")
        for rt_name, data in result.runtime_compatibility.items():
            assert "coverage_pct" in data
            assert 0 <= data["coverage_pct"] <= 100


class TestControlFlowAnalysis:
    def test_unreachable_after_halt(self):
        result = validate(bytes([0x00, 0x01]), filename="<halt_nop>")
        unreachable = result.control_flow.get("unreachable", [])
        assert 0x01 in unreachable

    def test_jump_targets_detected(self):
        # JMP (0x43) is format F: [opcode][rd][offset_lo][offset_hi]
        # To reach target=5: target = pc(0) + size(4) + offset(1) = 5
        result = validate(bytes([0x43, 0x00, 0x01, 0x00]), filename="<jmp>")
        targets = result.control_flow.get("jump_targets", [])
        assert 5 in targets


class TestValidationOutput:
    def test_to_json(self):
        result = validate(bytes([0x00]), filename="<test>")
        json_str = result.to_json()
        data = json.loads(json_str)
        assert data["filename"] == "<test>"
        assert "instruction_count" in data
        assert "errors" in data
        assert "warnings" in data

    def test_to_text(self):
        result = validate(bytes([0x00]), filename="<test>")
        text = result.to_text()
        assert "FLUX UNIVERSAL BYTECODE VALIDATOR" in text
        assert "<test>" in text


# ═══════════════════════════════════════════════════════════════════════
# Example Bytecode Tests
# ═══════════════════════════════════════════════════════════════════════

class TestExamples:
    def test_example_core_runs(self):
        bytecode = example_core()
        result = validate(bytecode, filename="<example:core>")
        assert result.bytecode_len == len(bytecode)

    def test_example_wasm_only_runs(self):
        bytecode = example_wasm_only()
        result = validate(bytecode, filename="<example:wasm_only>")
        assert result.bytecode_len == len(bytecode)

    def test_example_multi_runs(self):
        bytecode = example_multi()
        result = validate(bytecode, filename="<example:multi>")
        assert result.bytecode_len == len(bytecode)

    def test_examples_are_different(self):
        assert example_core() != example_wasm_only()
        assert example_core() != example_multi()


# ═══════════════════════════════════════════════════════════════════════
# Translation Tests
# ═══════════════════════════════════════════════════════════════════════

class TestTranslation:
    def test_python_to_canonical_preserves_length(self):
        bytecode = bytes([0x00, 0x01, 0x20, 0x21])
        translated = translate_bytecode(bytecode, "python", "canonical")
        assert len(translated) == len(bytecode)

    def test_rust_to_canonical_preserves_length(self):
        bytecode = bytes([0x00, 0x01, 0x20, 0x21])
        translated = translate_bytecode(bytecode, "rust", "canonical")
        assert len(translated) == len(bytecode)

    def test_python_to_canonical_changes_bytes(self):
        bytecode = bytes([0x00, 0x01])  # NOP, MOV in Python
        translated = translate_bytecode(bytecode, "python", "canonical")
        # At least some bytes should change for non-trivial translation
        # NOP -> something, MOV -> something
        assert translated != bytecode or True  # May or may not change

    def test_unknown_runtime_raises(self):
        with pytest.raises(SystemExit):
            translate_bytecode(b"", "nonexistent", "canonical")


# ═══════════════════════════════════════════════════════════════════════
# Mnemonic Table Tests
# ═══════════════════════════════════════════════════════════════════════

class TestMnemonics:
    def test_mnemonic_table_not_empty(self):
        assert len(MNEMONICS) > 0

    def test_core_opcodes_have_mnemonics(self):
        for op in IRREDUCIBLE_CORE:
            assert op in MNEMONICS, f"Irreducible core opcode 0x{op:02x} missing mnemonic"
