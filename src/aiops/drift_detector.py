"""Statistical data-drift detection for production ML pipelines.

Implements three complementary drift statistics:
- Population Stability Index (PSI): measures distributional shift in
  binned histograms.  PSI > 0.2 indicates significant drift (industry
  standard, Siddiqi 2006).
- Kolmogorov-Smirnov (KS) test: non-parametric two-sample test on
  empirical CDFs; sensitive to location and shape changes.
- Wasserstein distance (Earth Mover's Distance): measures the minimum
  transport cost between two distributions; scale-aware, useful for
  continuous variables.

Together these three statistics provide orthogonal evidence:
PSI captures population-level stability, KS detects distributional shape
differences with a p-value, Wasserstein quantifies magnitude.

References
----------
Siddiqi, N. (2006). Credit Risk Scorecards. Wiley.
Massey, F.J. (1951). J. Amer. Statist. Assoc. 46(253):68-78.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import numpy as np
from numpy.typing import NDArray
from scipy.stats import ks_2samp, wasserstein_distance

from src.common.exceptions import DriftThresholdExceeded

logger = logging.getLogger(__name__)

_PSI_EPSILON = 1e-6   # Laplace smoothing to avoid log(0).
_PSI_N_BINS = 10


@dataclass(frozen=True)
class DriftReport:
    """Drift statistics for a single feature.

    Parameters
    ----------
    feature : str
        Feature name.
    psi : float
        Population Stability Index.
    ks_statistic : float
        KS two-sample test statistic.
    ks_p_value : float
        Two-tailed p-value of the KS test.
    wasserstein : float
        Wasserstein-1 distance between reference and current distributions.
    is_drifted : bool
        True if any threshold is exceeded.
    """

    feature: str
    psi: float
    ks_statistic: float
    ks_p_value: float
    wasserstein: float
    is_drifted: bool


def _compute_psi(
    reference: NDArray[np.floating],
    current: NDArray[np.floating],
    n_bins: int = _PSI_N_BINS,
) -> float:
    """Compute PSI between *reference* and *current* distributions.

    Bins are derived from the reference distribution quantiles so that
    each bin contains roughly equal reference mass, which improves PSI
    stability compared to equal-width bins.

    Parameters
    ----------
    reference : NDArray[np.floating]
        Reference (training) distribution values.
    current : NDArray[np.floating]
        Current (production) distribution values.
    n_bins : int
        Number of histogram bins.

    Returns
    -------
    float
        PSI value in [0, ∞).
    """
    breakpoints = np.unique(
        np.percentile(reference, np.linspace(0, 100, n_bins + 1))
    )
    if len(breakpoints) < 2:
        # Degenerate distribution (constant feature); PSI is undefined → 0.
        return 0.0

    ref_counts, _ = np.histogram(reference, bins=breakpoints)
    cur_counts, _ = np.histogram(current, bins=breakpoints)

    ref_pct = (ref_counts / ref_counts.sum()) + _PSI_EPSILON
    cur_pct = (cur_counts / cur_counts.sum()) + _PSI_EPSILON

    psi: float = float(np.sum((cur_pct - ref_pct) * np.log(cur_pct / ref_pct)))
    return psi


def detect_drift(
    feature: str,
    reference: NDArray[np.floating],
    current: NDArray[np.floating],
    psi_threshold: float = 0.2,
    ks_threshold: float = 0.1,
    raise_on_drift: bool = False,
) -> DriftReport:
    """Compute drift statistics and optionally raise on threshold violation.

    Parameters
    ----------
    feature : str
        Human-readable feature name (used in log messages and errors).
    reference : NDArray[np.floating]
        Training/baseline distribution values.  Must not be empty.
    current : NDArray[np.floating]
        Production distribution values.  Must not be empty.
    psi_threshold : float
        PSI alert threshold.  Defaults to the industry-standard 0.2.
    ks_threshold : float
        KS statistic alert threshold.  Typical values 0.05-0.15.
    raise_on_drift : bool
        If True and drift is detected, raise DriftThresholdExceeded.

    Returns
    -------
    DriftReport
        Full drift statistics for the feature.

    Raises
    ------
    ValueError
        If reference or current arrays are empty.
    DriftThresholdExceeded
        If *raise_on_drift* is True and any threshold is exceeded.
    """
    if len(reference) == 0:
        raise ValueError(f"Reference array for feature '{feature}' is empty.")
    if len(current) == 0:
        raise ValueError(f"Current array for feature '{feature}' is empty.")

    psi = _compute_psi(reference, current)
    ks_result = ks_2samp(reference, current)
    wass = float(wasserstein_distance(reference, current))

    is_drifted = psi > psi_threshold or ks_result.statistic > ks_threshold

    report = DriftReport(
        feature=feature,
        psi=psi,
        ks_statistic=float(ks_result.statistic),
        ks_p_value=float(ks_result.pvalue),
        wasserstein=wass,
        is_drifted=is_drifted,
    )

    if is_drifted:
        logger.warning(
            "Drift detected for feature '%s': PSI=%.4f (threshold=%.4f), "
            "KS=%.4f (threshold=%.4f), Wasserstein=%.4f",
            feature,
            psi,
            psi_threshold,
            ks_result.statistic,
            ks_threshold,
            wass,
        )
        if raise_on_drift:
            dominant_score = psi if psi > psi_threshold else ks_result.statistic
            dominant_threshold = psi_threshold if psi > psi_threshold else ks_threshold
            raise DriftThresholdExceeded(
                feature=feature, score=dominant_score, threshold=dominant_threshold
            )
    else:
        logger.debug(
            "No drift detected for feature '%s': PSI=%.4f, KS=%.4f, Wasserstein=%.4f",
            feature,
            psi,
            ks_result.statistic,
            wass,
        )

    return report
