"""Domain-specific exceptions for the platform.

All exceptions carry a human-readable, actionable message and—where
applicable—the upstream cause via exception chaining (`raise X from Y`).
"""

from __future__ import annotations


class PlatformError(Exception):
    """Base class for all platform errors."""


class ConfigurationError(PlatformError):
    """Raised when a required configuration value is absent or invalid.

    Parameters
    ----------
    field : str
        The setting key that failed validation.
    reason : str
        Human-readable explanation of the failure.
    """

    def __init__(self, field: str, reason: str) -> None:
        super().__init__(f"Configuration error for '{field}': {reason}")
        self.field = field


class SecretRetrievalError(PlatformError):
    """Raised when Azure Key Vault cannot return a requested secret."""


class IndexingError(PlatformError):
    """Raised when an AI Search indexing operation fails."""


class IngestionError(PlatformError):
    """Raised when a Lakehouse ingestion step encounters an unrecoverable error."""


class DriftThresholdExceeded(PlatformError):
    """Raised when a monitored feature's drift score exceeds its threshold.

    Parameters
    ----------
    feature : str
        Name of the drifting feature.
    score : float
        Measured drift score.
    threshold : float
        Configured alert threshold.
    """

    def __init__(self, feature: str, score: float, threshold: float) -> None:
        super().__init__(
            f"Drift threshold exceeded for feature '{feature}': "
            f"score={score:.4f} > threshold={threshold:.4f}"
        )
        self.feature = feature
        self.score = score
        self.threshold = threshold


class EvaluationError(PlatformError):
    """Raised when GenAI response evaluation cannot be completed."""
