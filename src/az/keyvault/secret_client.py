"""Azure Key Vault secret retrieval with managed-identity authentication.

Follows the principle of least-privilege: callers receive secret *values*
without ever seeing connection strings in config files or environment
variables.  WorkloadIdentityCredential (or DefaultAzureCredential as
fallback) is used so no client secrets are stored on disk.
"""

from __future__ import annotations

import logging
from functools import lru_cache

from azure.core.exceptions import ResourceNotFoundError, ServiceRequestError
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient

from src.common.exceptions import SecretRetrievalError

logger = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def _get_client(vault_url: str) -> SecretClient:
    """Return a cached SecretClient for *vault_url*.

    The cache ensures a single credential and TCP connection pool is reused
    across the process lifetime.

    Parameters
    ----------
    vault_url : str
        HTTPS URL of the Key Vault instance.

    Returns
    -------
    SecretClient
        Authenticated Key Vault client.
    """
    credential = DefaultAzureCredential()
    return SecretClient(vault_url=vault_url, credential=credential)


def get_secret(vault_url: str, secret_name: str) -> str:
    """Retrieve the latest version of a secret from Key Vault.

    Parameters
    ----------
    vault_url : str
        HTTPS URL of the Key Vault instance.
    secret_name : str
        Name of the secret to retrieve.

    Returns
    -------
    str
        Secret value as a plain string.

    Raises
    ------
    SecretRetrievalError
        If the secret does not exist, access is denied, or the service
        is unavailable.
    """
    client = _get_client(vault_url)
    try:
        bundle = client.get_secret(secret_name)
    except ResourceNotFoundError as exc:
        raise SecretRetrievalError(
            f"Secret '{secret_name}' not found in vault '{vault_url}'. "
            "Verify the secret name and that the managed identity has 'Key Vault Secrets User' role."
        ) from exc
    except ServiceRequestError as exc:
        raise SecretRetrievalError(
            f"Network error contacting Key Vault '{vault_url}': {exc}"
        ) from exc
    except Exception as exc:
        raise SecretRetrievalError(
            f"Unexpected error retrieving secret '{secret_name}': {exc}"
        ) from exc

    if bundle.value is None:
        raise SecretRetrievalError(
            f"Secret '{secret_name}' exists but its value is None. "
            "Check for an empty secret or a soft-deleted version."
        )
    logger.debug("Retrieved secret '%s' from Key Vault.", secret_name)
    return bundle.value
