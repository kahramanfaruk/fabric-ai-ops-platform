"""Unit tests for drift_detector.py.

Test philosophy
---------------
- Use synthetic distributions with known statistical properties so
  assertions can be derived analytically, not just empirically.
- Parametrise boundary conditions: empty arrays, constant features,
  identical distributions (PSI = 0).
- Verify that raise_on_drift propagates DriftThresholdExceeded correctly.
"""

from __future__ import annotations

import numpy as np
import pytest

from src.aiops.drift_detector import DriftReport, _compute_psi, detect_drift
from src.common.exceptions import DriftThresholdExceeded


class TestComputePSI:
    def test_identical_distributions_returns_near_zero(self, rng: np.random.Generator) -> None:
        data = rng.normal(0, 1, 1_000).astype(np.float64)
        psi = _compute_psi(data, data)
        # PSI of identical distributions is epsilon-only noise → < 0.01.
        assert psi < 0.01

    def test_heavily_shifted_distribution_exceeds_threshold(
        self, rng: np.random.Generator
    ) -> None:
        ref = rng.normal(0, 1, 2_000).astype(np.float64)
        cur = rng.normal(5, 1, 2_000).astype(np.float64)  # 5σ shift
        psi = _compute_psi(ref, cur)
        assert psi > 0.2, f"Expected PSI > 0.2 for a 5σ shift, got {psi:.4f}"

    def test_constant_feature_returns_zero(self) -> None:
        ref = np.ones(100, dtype=np.float64)
        cur = np.ones(100, dtype=np.float64)
        psi = _compute_psi(ref, cur)
        assert psi == 0.0


class TestDetectDrift:
    def test_no_drift_for_same_distribution(self, rng: np.random.Generator) -> None:
        data = rng.normal(0, 1, 2_000).astype(np.float64)
        report = detect_drift("temperature", data, data)
        assert isinstance(report, DriftReport)
        assert not report.is_drifted

    def test_drift_detected_for_large_shift(self, rng: np.random.Generator) -> None:
        ref = rng.normal(0, 1, 2_000).astype(np.float64)
        cur = rng.normal(4, 1, 2_000).astype(np.float64)
        report = detect_drift("pressure", ref, cur)
        assert report.is_drifted
        assert report.psi > 0.0
        assert report.ks_statistic > 0.0
        assert report.wasserstein > 0.0

    def test_raises_on_drift_when_requested(self, rng: np.random.Generator) -> None:
        ref = rng.normal(0, 1, 2_000).astype(np.float64)
        cur = rng.normal(4, 1, 2_000).astype(np.float64)
        with pytest.raises(DriftThresholdExceeded) as exc_info:
            detect_drift("flow_rate", ref, cur, raise_on_drift=True)
        assert "flow_rate" in str(exc_info.value)

    def test_raises_on_empty_reference(self) -> None:
        with pytest.raises(ValueError, match="Reference array"):
            detect_drift("x", np.array([]), np.array([1.0, 2.0]))

    def test_raises_on_empty_current(self) -> None:
        with pytest.raises(ValueError, match="Current array"):
            detect_drift("x", np.array([1.0, 2.0]), np.array([]))

    def test_report_feature_name_preserved(self, rng: np.random.Generator) -> None:
        data = rng.normal(0, 1, 500).astype(np.float64)
        report = detect_drift("my_feature", data, data)
        assert report.feature == "my_feature"
