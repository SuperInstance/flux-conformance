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

__all__ = [
    "OpcodeDef",
    "ImplementationDef",
    "TestCoverageEntry",
    "ImplementationRegistry",
    "ConformanceMatrix",
    "CoverageAnalyzer",
    "GapReporter",
    "MatrixExporter",
]
