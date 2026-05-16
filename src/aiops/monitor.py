"""Azure Monitor metric publisher for AI-Ops telemetry.

Emits custom metrics via OpenTelemetry SDK → Azure Monitor exporter so
all drift scores, evaluation results, and pipeline health signals appear
in the same Log Analytics workspace as infra metrics.
"""

from __future__ import annotations

import logging
from typing import Any

from opentelemetry import metrics

logger = logging.getLogger(__name__)

_METER_NAME = "fabric-ai-ops-platform.aiops"
_meter: metrics.Meter | None = None


def _get_meter() -> metrics.Meter:
    global _meter
    if _meter is None:
        _meter = metrics.get_meter(_METER_NAME)
    return _meter


def record_drift_score(feature: str, psi: float, ks_statistic: float, wasserstein: float) -> None:
    """Emit drift scores as OpenTelemetry gauges.

    Parameters
    ----------
    feature : str
        Feature name (used as metric attribute).
    psi : float
        PSI score.
    ks_statistic : float
        KS test statistic.
    wasserstein : float
        Wasserstein-1 distance.
    """
    meter = _get_meter()
    attrs: dict[str, Any] = {"feature": feature}
    meter.create_gauge("drift.psi").set(psi, attrs)
    meter.create_gauge("drift.ks_statistic").set(ks_statistic, attrs)
    meter.create_gauge("drift.wasserstein").set(wasserstein, attrs)
    logger.debug("Recorded drift metrics for feature '%s'.", feature)


def record_evaluation_scores(
    deployment: str, groundedness: int, relevance: int, coherence: int
) -> None:
    """Emit LLM evaluation scores as OpenTelemetry gauges.

    Parameters
    ----------
    deployment : str
        Azure OpenAI deployment name.
    groundedness : int
        Groundedness score 0-5.
    relevance : int
        Relevance score 0-5.
    coherence : int
        Coherence score 0-5.
    """
    meter = _get_meter()
    attrs: dict[str, Any] = {"deployment": deployment}
    meter.create_gauge("llm.eval.groundedness").set(groundedness, attrs)
    meter.create_gauge("llm.eval.relevance").set(relevance, attrs)
    meter.create_gauge("llm.eval.coherence").set(coherence, attrs)
    logger.debug("Recorded evaluation metrics for deployment '%s'.", deployment)
