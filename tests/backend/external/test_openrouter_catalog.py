from unittest.mock import AsyncMock, MagicMock

import pytest

from backend.app.external.openrouter_catalog import (
    _is_text_model,
    _map_model,
    fetch_openrouter_catalog,
)


class TestIsTextModel:
    def test_text_to_text_is_kept(self) -> None:
        assert _is_text_model({"input_modalities": ["text"], "output_modalities": ["text"]})

    def test_image_output_only_is_rejected(self) -> None:
        assert not _is_text_model({"input_modalities": ["text"], "output_modalities": ["image"]})

    def test_missing_modalities_defaults_to_permissive(self) -> None:
        assert _is_text_model({})


class TestMapModel:
    def test_free_model_has_no_pricing_key(self) -> None:
        raw = {
            "id": "meta/llama:free",
            "name": "Meta: Llama (free)",
            "pricing": {"prompt": "0", "completion": "0"},
            "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
        }
        assert _map_model(raw) == {
            "value": "meta/llama:free",
            "label": "Meta: Llama (free)",
            "paid": False,
        }

    def test_paid_model_converts_per_token_to_per_million(self) -> None:
        raw = {
            "id": "anthropic/claude",
            "name": "Anthropic: Claude",
            "pricing": {"prompt": "0.000003", "completion": "0.000015"},
            "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
        }
        mapped = _map_model(raw)
        assert mapped["paid"] is True
        assert mapped["pricing"] == {"inputUsdPerMillion": 3.0, "outputUsdPerMillion": 15.0}

    def test_missing_id_is_dropped(self) -> None:
        assert _map_model({"name": "no id"}) is None

    def test_non_text_model_is_dropped(self) -> None:
        raw = {
            "id": "img/gen",
            "architecture": {"input_modalities": ["text"], "output_modalities": ["image"]},
        }
        assert _map_model(raw) is None

    def test_missing_label_falls_back_to_slug(self) -> None:
        raw = {"id": "a/b", "pricing": {}, "architecture": {}}
        assert _map_model(raw)["label"] == "a/b"

    def test_malformed_pricing_treated_as_free(self) -> None:
        raw = {"id": "a/b", "pricing": {"prompt": "n/a", "completion": None}, "architecture": {}}
        mapped = _map_model(raw)
        assert mapped["paid"] is False
        assert "pricing" not in mapped


class TestFetchOpenrouterCatalog:
    async def test_maps_and_filters_response_data(self, monkeypatch) -> None:
        payload = {
            "data": [
                {
                    "id": "free/a",
                    "name": "Free A",
                    "pricing": {"prompt": "0", "completion": "0"},
                    "architecture": {"input_modalities": ["text"], "output_modalities": ["text"]},
                },
                {"id": "img/only", "architecture": {"output_modalities": ["image"], "input_modalities": ["text"]}},
            ]
        }
        mock_response = MagicMock()
        mock_response.json.return_value = payload
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = False

        monkeypatch.setattr(
            "backend.app.external.openrouter_catalog.httpx.AsyncClient",
            MagicMock(return_value=mock_client),
        )

        models = await fetch_openrouter_catalog()

        assert models == [{"value": "free/a", "label": "Free A", "paid": False}]

    async def test_empty_result_raises(self, monkeypatch) -> None:
        mock_response = MagicMock()
        mock_response.json.return_value = {"data": []}
        mock_response.raise_for_status = MagicMock()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__.return_value = mock_client
        mock_client.__aexit__.return_value = False

        monkeypatch.setattr(
            "backend.app.external.openrouter_catalog.httpx.AsyncClient",
            MagicMock(return_value=mock_client),
        )

        with pytest.raises(ValueError, match="no usable text models"):
            await fetch_openrouter_catalog()
