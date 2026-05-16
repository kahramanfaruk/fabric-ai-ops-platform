"""Unit tests for Key Vault secret_client.py."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from src.common.exceptions import SecretRetrievalError


class TestGetSecret:
    def test_returns_secret_value(self) -> None:
        mock_bundle = MagicMock()
        mock_bundle.value = "supersecret"
        mock_client = MagicMock()
        mock_client.get_secret.return_value = mock_bundle

        with patch("src.az.keyvault.secret_client._get_client", return_value=mock_client):
            from src.az.keyvault.secret_client import get_secret
            result = get_secret("https://vault.azure.net", "my-secret")

        assert result == "supersecret"

    def test_raises_when_secret_not_found(self) -> None:
        from azure.core.exceptions import ResourceNotFoundError
        mock_client = MagicMock()
        mock_client.get_secret.side_effect = ResourceNotFoundError(message="Not found")

        with patch("src.az.keyvault.secret_client._get_client", return_value=mock_client):
            from src.az.keyvault.secret_client import get_secret
            with pytest.raises(SecretRetrievalError, match="not found"):
                get_secret("https://vault.azure.net", "missing-secret")

    def test_raises_when_value_is_none(self) -> None:
        mock_bundle = MagicMock()
        mock_bundle.value = None
        mock_client = MagicMock()
        mock_client.get_secret.return_value = mock_bundle

        with patch("src.az.keyvault.secret_client._get_client", return_value=mock_client):
            from src.az.keyvault.secret_client import get_secret
            with pytest.raises(SecretRetrievalError, match="None"):
                get_secret("https://vault.azure.net", "empty-secret")
