"""Unit tests for bronze_ingest.py with NYC Taxi DataSourceConfig."""

from __future__ import annotations

import pytest

pytest.importorskip("pyspark", reason="PySpark not available in this environment")

from unittest.mock import patch

from pyspark.sql import SparkSession

from src.common.exceptions import IngestionError
from src.fabric.lakehouse.data_sources import NYC_TAXI_YELLOW


@pytest.fixture(scope="module")
def spark() -> SparkSession:
    return (
        SparkSession.builder
        .master("local[1]")
        .appName("test-bronze-ingest")
        .getOrCreate()
    )


class TestBronzeIngest:
    def test_raises_on_missing_source(self, spark: SparkSession) -> None:
        """Both shortcut path and fallback fail → IngestionError raised."""
        # Override the config fallback path to a non-existent location.
        import dataclasses

        from src.fabric.lakehouse.bronze_ingest import ingest_to_bronze
        bad_config = dataclasses.replace(
            NYC_TAXI_YELLOW,
            fallback_wasbs_path="/nonexistent/path",
        )
        with patch("src.fabric.lakehouse.bronze_ingest._resolve_source_path",
                   return_value="/nonexistent/path"):
            with pytest.raises(IngestionError, match="Cannot read source"):
                ingest_to_bronze(
                    spark=spark,
                    config=bad_config,
                    workspace_id="ws-test",
                    lakehouse_name="test_lh",
                    year=2023,
                )

    def test_config_name_is_correct(self) -> None:
        assert NYC_TAXI_YELLOW.name == "nyctaxi_yellow"
        assert NYC_TAXI_YELLOW.format == "parquet"
        assert NYC_TAXI_YELLOW.year_partition_col == "puYear"

    def test_resolved_shortcut_path_substitutes_placeholders(self) -> None:
        path = NYC_TAXI_YELLOW.resolved_shortcut_path("ws-abc", "ops_lakehouse")
        assert "ws-abc" in path
        assert "ops_lakehouse" in path
        assert "nyctaxi_yellow" in path
