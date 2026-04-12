"""FLUX Conformance Matrix — Cross-language VM opcode tracking."""

from .matrix import (
    OpcodeDef,
    ImplementationDef,
    TestCoverageEntry,
    ImplementationRegistry,
    ConformanceMatrix,
    CoverageAnalyzer,
    GapReporter,
    MatrixExporter,
)

from .runner import (
    MiniVM,
    Flags,
    TestVector,
    ConformanceResult,
    VectorGenerator,
    ConformanceRunner,
    ConformanceReporter,
    # Encoding helpers
    encode_a,
    encode_b,
    encode_c,
    encode_d,
    encode_e,
    encode_f,
    encode_g,
)

__all__ = [
    # Matrix module
    "OpcodeDef",
    "ImplementationDef",
    "TestCoverageEntry",
    "ImplementationRegistry",
    "ConformanceMatrix",
    "CoverageAnalyzer",
    "GapReporter",
    "MatrixExporter",
    # Runner module
    "MiniVM",
    "Flags",
    "TestVector",
    "ConformanceResult",
    "VectorGenerator",
    "ConformanceRunner",
    "ConformanceReporter",
    # Encoding helpers
    "encode_a",
    "encode_b",
    "encode_c",
    "encode_d",
    "encode_e",
    "encode_f",
    "encode_g",
]
