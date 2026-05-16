"""Structured JSON logging initialisation.

Integrates with Azure Monitor via OpenTelemetry so all log records are
shipped to Log Analytics workspace alongside traces and metrics.
"""

from __future__ import annotations

import logging
import sys


def configure_logging(level: str = "INFO", service_name: str = "fabric-ai-ops-platform") -> None:
    """Configure root logger with structured output.

    In production (Azure Functions / Fabric notebooks) the Azure Monitor
    exporter picks up the root handler automatically.  Locally, output goes
    to stdout in a human-readable format.

    Parameters
    ----------
    level : str
        Logging level string.  Defaults to "INFO".
    service_name : str
        Logical service name embedded in every log record.
    """
    numeric_level = getattr(logging, level.upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(numeric_level)
    formatter = logging.Formatter(
        fmt='{"time":"%(asctime)s","level":"%(levelname)s","service":"' + service_name + '","name":"%(name)s","msg":"%(message)s"}',
        datefmt="%Y-%m-%dT%H:%M:%SZ",
    )
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.setLevel(numeric_level)
    # Avoid duplicate handlers when called multiple times (e.g., in notebooks).
    if not any(isinstance(h, logging.StreamHandler) for h in root.handlers):
        root.addHandler(handler)
