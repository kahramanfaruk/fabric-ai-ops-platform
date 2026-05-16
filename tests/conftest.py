"""Shared pytest fixtures.

Heavy SDK dependencies (Azure, PySpark, OpenAI) are always mocked so
the test suite runs in CI without live credentials or a running cluster.
"""

from __future__ import annotations

import numpy as np
import pytest


@pytest.fixture()
def rng() -> np.random.Generator:
    """Seeded NumPy random generator for deterministic test data."""
    return np.random.default_rng(seed=42)
