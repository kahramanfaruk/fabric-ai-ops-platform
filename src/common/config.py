"""Centralised settings loaded from environment variables and Azure Key Vault.

Uses pydantic-settings so every field is type-validated at startup.
Secrets (API keys, connection strings) are *never* stored in source code;
they are resolved at runtime from Key Vault via the Key Vault client.
"""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Platform-wide runtime configuration.

    All values are sourced from environment variables.  Sensitive values
    are referenced by their Key Vault secret *name* (a non-secret string)
    and resolved at runtime by :mod:`src.az.keyvault.secret_client`.

    Parameters
    ----------
    azure_tenant_id : str
        Entra ID tenant identifier.
    azure_client_id : str
        Managed-identity / service-principal client ID.
    keyvault_url : str
        HTTPS URL of the Azure Key Vault instance.
    aisearch_endpoint : str
        HTTPS endpoint of the Azure AI Search service.
    aisearch_index_name : str
        Name of the default search index.
    openai_endpoint : str
        Azure OpenAI endpoint URL.
    openai_deployment : str
        Name of the chat-completion deployment.
    fabric_workspace_id : str
        Microsoft Fabric workspace GUID.
    lakehouse_name : str
        Name of the Fabric Lakehouse.
    drift_psi_threshold : float
        PSI value above which a feature is flagged as drifted.
    drift_ks_threshold : float
        KS statistic above which a feature is flagged as drifted.
    log_level : str
        Python logging level string (e.g. "INFO", "DEBUG").
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    azure_tenant_id: str = Field(..., alias="AZURE_TENANT_ID")
    azure_client_id: str = Field(..., alias="AZURE_CLIENT_ID")
    keyvault_url: str = Field(..., alias="KEYVAULT_URL")

    aisearch_endpoint: str = Field(..., alias="AISEARCH_ENDPOINT")
    aisearch_index_name: str = Field(default="operations-index", alias="AISEARCH_INDEX_NAME")

    openai_endpoint: str = Field(..., alias="OPENAI_ENDPOINT")
    openai_deployment: str = Field(default="gpt-4o", alias="OPENAI_DEPLOYMENT")

    fabric_workspace_id: str = Field(..., alias="FABRIC_WORKSPACE_ID")
    lakehouse_name: str = Field(default="ops_lakehouse", alias="LAKEHOUSE_NAME")

    drift_psi_threshold: float = Field(default=0.2, alias="DRIFT_PSI_THRESHOLD")
    drift_ks_threshold: float = Field(default=0.1, alias="DRIFT_KS_THRESHOLD")

    log_level: str = Field(default="INFO", alias="LOG_LEVEL")


def get_settings() -> Settings:
    """Return a validated Settings instance.

    Returns
    -------
    Settings
        Populated and validated settings object.

    Raises
    ------
    ConfigurationError
        If any required environment variable is absent.
    """
    from pydantic import ValidationError

    from src.common.exceptions import ConfigurationError

    try:
        return Settings()  # type: ignore[call-arg]
    except ValidationError as exc:
        missing = [str(e["loc"][0]) for e in exc.errors()]
        raise ConfigurationError(
            field=", ".join(missing),
            reason="Required environment variable(s) not set.",
        ) from exc
