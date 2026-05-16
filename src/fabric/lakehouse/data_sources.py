"""Azure Open Datasets source definitions and OneLake shortcut paths.

All data stays on Microsoft-managed Azure storage — no external egress,
no manual download.  Two access patterns are supported:

1. **Azure Open Datasets direct read** (wasbs:// endpoint):
   Fabric notebooks can read directly from the public Azure Blob endpoint
   using the azureml-opendatasets SDK or raw Spark reads.  Zero cost.

2. **OneLake Shortcut** (preferred for production):
   Create a Fabric shortcut pointing at the Azure Open Datasets Blob
   container.  All downstream reads use the OneLake ABFSS path so data
   governance, lineage, and access control stay within Fabric.
   Shortcut creation is a one-time Portal or REST API operation.

References
----------
Azure Open Datasets catalog:
  https://learn.microsoft.com/en-us/azure/open-datasets/dataset-catalog
NYC TLC public Parquet (hosted by Microsoft):
  wasbs://nyctlc@azureopendatastore.blob.core.windows.net/
NOAA ISD weather (hosted by Microsoft):
  wasbs://isd@azureopendatastore.blob.core.windows.net/
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Literal

# ── Azure Open Datasets — direct wasbs:// endpoints (always free) ─────────────

NYCTAXI_BLOB_ACCOUNT = "azureopendatastore"
NYCTAXI_BLOB_CONTAINER = "nyctlc"
NYCTAXI_YELLOW_PATH = (
    "wasbs://nyctlc@azureopendatastore.blob.core.windows.net/yellow"
)
NYCTAXI_GREEN_PATH = (
    "wasbs://nyctlc@azureopendatastore.blob.core.windows.net/green"
)
NOAA_WEATHER_PATH = (
    "wasbs://isd@azureopendatastore.blob.core.windows.net/"
)

# ── OneLake Shortcut paths (set after creating shortcuts in Fabric Portal) ────
# Pattern:
#   abfss://<workspace>@onelake.dfs.fabric.microsoft.com/<lakehouse>.Lakehouse/Files/<shortcut>
#
# Replace WORKSPACE_ID and LAKEHOUSE_NAME via Settings at runtime.

SHORTCUT_NYCTAXI_YELLOW = (
    "abfss://{workspace_id}@onelake.dfs.fabric.microsoft.com/"
    "{lakehouse_name}.Lakehouse/Files/shortcuts/nyctaxi_yellow"
)
SHORTCUT_NYCTAXI_GREEN = (
    "abfss://{workspace_id}@onelake.dfs.fabric.microsoft.com/"
    "{lakehouse_name}.Lakehouse/Files/shortcuts/nyctaxi_green"
)
SHORTCUT_NOAA_WEATHER = (
    "abfss://{workspace_id}@onelake.dfs.fabric.microsoft.com/"
    "{lakehouse_name}.Lakehouse/Files/shortcuts/noaa_weather"
)


@dataclass(frozen=True)
class DataSourceConfig:
    """Configuration for a single ingestion source.

    Parameters
    ----------
    name : str
        Logical name used as the Bronze table suffix (e.g. ``nyctaxi_yellow``).
    shortcut_path_template : str
        OneLake ABFSS path template (preferred).  Contains ``{workspace_id}``
        and ``{lakehouse_name}`` placeholders.
    fallback_wasbs_path : str
        Direct Azure Open Datasets wasbs:// path used when the OneLake
        shortcut has not yet been created.
    format : str
        Spark read format — ``"parquet"`` for all Azure Open Datasets sources.
    year_partition_col : str
        Column name used to filter a single year partition during ingestion.
    date_partition_col : str
        Datetime column used as the primary event timestamp in Bronze.
    numeric_feature_cols : list[str]
        Columns used by the drift detector (must be numeric after casting).
    """

    name: str
    shortcut_path_template: str
    fallback_wasbs_path: str
    format: Literal["parquet", "json", "csv"] = "parquet"
    year_partition_col: str = "puYear"
    date_partition_col: str = "tpepPickupDatetime"
    numeric_feature_cols: list[str] = field(default_factory=lambda: [
        "passengerCount",
        "tripDistance",
        "fareAmount",
        "tipAmount",
        "totalAmount",
    ])

    def resolved_shortcut_path(self, workspace_id: str, lakehouse_name: str) -> str:
        """Return the OneLake shortcut path with placeholders filled.

        Parameters
        ----------
        workspace_id : str
            Fabric workspace GUID.
        lakehouse_name : str
            Fabric Lakehouse name.

        Returns
        -------
        str
            Resolved ABFSS path.
        """
        return self.shortcut_path_template.format(
            workspace_id=workspace_id,
            lakehouse_name=lakehouse_name,
        )


# ── Canonical source registry ─────────────────────────────────────────────────

NYC_TAXI_YELLOW = DataSourceConfig(
    name="nyctaxi_yellow",
    shortcut_path_template=SHORTCUT_NYCTAXI_YELLOW,
    fallback_wasbs_path=NYCTAXI_YELLOW_PATH,
    format="parquet",
    year_partition_col="puYear",
    date_partition_col="tpepPickupDatetime",
    numeric_feature_cols=[
        "passengerCount",
        "tripDistance",
        "fareAmount",
        "tipAmount",
        "totalAmount",
        "improvementSurcharge",
    ],
)

NYC_TAXI_GREEN = DataSourceConfig(
    name="nyctaxi_green",
    shortcut_path_template=SHORTCUT_NYCTAXI_GREEN,
    fallback_wasbs_path=NYCTAXI_GREEN_PATH,
    format="parquet",
    year_partition_col="puYear",
    date_partition_col="lpepPickupDatetime",
    numeric_feature_cols=[
        "passengerCount",
        "tripDistance",
        "fareAmount",
        "tipAmount",
        "totalAmount",
    ],
)

NOAA_WEATHER = DataSourceConfig(
    name="noaa_weather",
    shortcut_path_template=SHORTCUT_NOAA_WEATHER,
    fallback_wasbs_path=NOAA_WEATHER_PATH,
    format="parquet",
    year_partition_col="year",
    date_partition_col="datetime",
    numeric_feature_cols=[
        "temperature",
        "dewPoint",
        "seaLvlPressure",
        "windSpeed",
        "precipTime",
        "precipDepth",
    ],
)

# Master registry — add new sources here only.
SOURCE_REGISTRY: dict[str, DataSourceConfig] = {
    NYC_TAXI_YELLOW.name: NYC_TAXI_YELLOW,
    NYC_TAXI_GREEN.name: NYC_TAXI_GREEN,
    NOAA_WEATHER.name: NOAA_WEATHER,
}
