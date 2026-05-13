"""Pytest configuration and shared fixtures for the FLUX conformance suite.

This module provides:
- ``adapter`` fixture that parametrises tests across all available runtimes.
- ``python_adapter`` fixture for the Python (micro VM) runtime.
- ``c_adapter`` fixture for the C runtime (skipped if unavailable).
"""

from __future__ import annotations

import pytest

from runtime_adapters import PythonAdapter, CAdapter


@pytest.fixture
def python_adapter() -> PythonAdapter:
    """Provide the Python (micro VM) adapter — always available."""
    return PythonAdapter()


@pytest.fixture
def c_adapter() -> CAdapter:
    """Provide the C adapter — skip tests if the binary is not found."""
    adapter = CAdapter()
    if not adapter.is_available():
        pytest.skip("flux-vm-c binary not found on $PATH")
    return adapter


@pytest.fixture(
    params=["python"],
    ids=["python"],
)
def adapter(request):
    """Parametrised fixture that provides each available runtime adapter.

    Currently only the Python adapter is included by default because the
    C adapter binary is typically not present in CI.  To add the C adapter
    to the parametrisation, change ``params`` to ``["python", "c"]`` and
    handle the skip logic inside the fixture body.
    """
    if request.param == "python":
        return PythonAdapter()
    elif request.param == "c":
        adapter = CAdapter()
        if not adapter.is_available():
            pytest.skip("C runtime not available")
        return adapter
    raise ValueError(f"Unknown adapter: {request.param}")
