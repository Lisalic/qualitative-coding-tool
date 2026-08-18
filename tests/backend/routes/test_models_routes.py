"""Tests for GET /api/models -- exposes the in-memory OpenRouter catalog."""

import pytest

from backend.app import ai_models


class TestListAiModels:
    def test_requires_auth(self, client) -> None:
        resp = client.get("/api/models")
        assert resp.status_code == 401

    def test_returns_current_catalog(self, client, auth_cookies, monkeypatch) -> None:
        monkeypatch.setattr(
            ai_models,
            "AI_MODELS",
            [
                {"value": "free/a", "label": "Free A", "paid": False},
                {
                    "value": "paid/b",
                    "label": "Paid B",
                    "paid": True,
                    "pricing": {"inputUsdPerMillion": 1.5, "outputUsdPerMillion": 3.0},
                },
            ],
        )

        resp = client.get("/api/models", cookies=auth_cookies)

        assert resp.status_code == 200
        body = resp.json()
        assert body == [
            {"value": "free/a", "label": "Free A", "paid": False, "pricing": None},
            {
                "value": "paid/b",
                "label": "Paid B",
                "paid": True,
                "pricing": {"inputUsdPerMillion": 1.5, "outputUsdPerMillion": 3.0},
            },
        ]
