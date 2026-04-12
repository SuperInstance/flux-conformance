"""Shared fixtures for flux-conformance tests."""

import json
import os
import pytest


@pytest.fixture
def vectors_dir():
    """Return path to the test vectors directory."""
    return os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "runners", "vectors")


@pytest.fixture
def all_vectors(vectors_dir):
    """Load all test vectors from the manifest and return as list of dicts."""
    manifest_path = os.path.join(vectors_dir, "manifest.json")
    with open(manifest_path) as f:
        manifest = json.load(f)

    vectors = []
    for category, vector_ids in manifest.get("categories", {}).items():
        for vid in vector_ids:
            vpath = os.path.join(vectors_dir, f"{vid}.json")
            if os.path.exists(vpath):
                with open(vpath) as f:
                    vectors.append(json.load(f))
    return vectors


@pytest.fixture
def manifest(vectors_dir):
    """Load the manifest as a dict."""
    manifest_path = os.path.join(vectors_dir, "manifest.json")
    with open(manifest_path) as f:
        return json.load(f)
