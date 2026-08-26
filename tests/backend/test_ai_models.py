"""Tests for backend/app/ai_models.py."""

from unittest.mock import AsyncMock

import pytest

from backend.app import ai_models


class TestModelSlugAt:
    def test_index_zero(self) -> None:
        assert ai_models.model_slug_at(0) == ai_models.AI_MODELS[0]["value"]

    def test_last_index(self) -> None:
        last = len(ai_models.AI_MODELS) - 1
        assert ai_models.model_slug_at(last) == ai_models.AI_MODELS[last]["value"]

    def test_negative_index_clamps_to_zero(self) -> None:
        assert ai_models.model_slug_at(-1) == ai_models.AI_MODELS[0]["value"]
        assert ai_models.model_slug_at(-99999) == ai_models.AI_MODELS[0]["value"]

    def test_out_of_range_index_clamps_to_last(self) -> None:
        last = ai_models.AI_MODELS[-1]["value"]
        assert ai_models.model_slug_at(len(ai_models.AI_MODELS)) == last
        assert ai_models.model_slug_at(10**9) == last

    def test_empty_catalog_raises_runtime_error(self, monkeypatch) -> None:
        monkeypatch.setattr(ai_models, "AI_MODELS", [])
        with pytest.raises(RuntimeError, match="AI_MODELS is empty"):
            ai_models.model_slug_at(0)

    def test_entry_missing_value_key_raises_key_error(self, monkeypatch) -> None:
        monkeypatch.setattr(ai_models, "AI_MODELS", [{"label": "no value field"}])
        with pytest.raises(KeyError):
            ai_models.model_slug_at(0)

    def test_non_int_index_raises_type_error(self) -> None:
        with pytest.raises(TypeError):
            ai_models.model_slug_at(1.7)  # type: ignore[arg-type]

    def test_bool_index_is_treated_as_int(self) -> None:
        # bool is a subclass of int -- True behaves like index 1.
        assert ai_models.model_slug_at(True) == ai_models.AI_MODELS[1]["value"]  # type: ignore[arg-type]

    def test_returns_a_string(self) -> None:
        assert isinstance(ai_models.model_slug_at(0), str)


class TestIsPaidModel:
    def test_real_catalog_has_both_paid_and_free_entries(self) -> None:
        paid = [m for m in ai_models.AI_MODELS if m.get("paid") is True]
        free = [m for m in ai_models.AI_MODELS if m.get("paid") is not True]
        assert paid, "expected at least one paid entry in the real catalog"
        assert free, "expected at least one free entry in the real catalog"

    def test_known_paid_slug_from_real_catalog(self) -> None:
        paid_slug = next(m["value"] for m in ai_models.AI_MODELS if m.get("paid") is True)
        assert ai_models.is_paid_model(paid_slug) is True

    def test_known_free_slug_from_real_catalog(self) -> None:
        free_slug = next(m["value"] for m in ai_models.AI_MODELS if m.get("paid") is not True)
        assert ai_models.is_paid_model(free_slug) is False

    def test_unknown_slug_is_false(self) -> None:
        assert ai_models.is_paid_model("not/a/real-model") is False

    @pytest.mark.parametrize("slug", [None, "", "   ", "\t\n"])
    def test_blank_slug_is_false(self, slug) -> None:
        assert ai_models.is_paid_model(slug) is False

    def test_whitespace_around_a_valid_slug_is_tolerated(self, monkeypatch) -> None:
        monkeypatch.setattr(
            ai_models, "_MODEL_META_BY_SLUG", {"x/y": {"value": "x/y", "paid": True}}
        )
        assert ai_models.is_paid_model("  x/y  ") == True  # noqa: E712
        assert ai_models.is_paid_model("\nx/y\t") == True  # noqa: E712

    def test_internal_whitespace_is_not_tolerated(self, monkeypatch) -> None:
        monkeypatch.setattr(
            ai_models, "_MODEL_META_BY_SLUG", {"x/y": {"value": "x/y", "paid": True}}
        )
        assert ai_models.is_paid_model("x/ y") is False

    def test_case_sensitive(self, monkeypatch) -> None:
        monkeypatch.setattr(
            ai_models, "_MODEL_META_BY_SLUG", {"x/y": {"value": "x/y", "paid": True}}
        )
        assert ai_models.is_paid_model("X/Y") is False

    def test_paid_check_is_strict_identity_not_truthiness(self, monkeypatch) -> None:
        # `paid: 1`, `paid: "true"` etc. must NOT count as paid -- only the
        # JSON literal `true` (Python `True`) does.
        monkeypatch.setattr(
            ai_models,
            "_MODEL_META_BY_SLUG",
            {
                "int-one": {"value": "int-one", "paid": 1},
                "str-true": {"value": "str-true", "paid": "true"},
                "list-truthy": {"value": "list-truthy", "paid": [1]},
                "real-true": {"value": "real-true", "paid": True},
            },
        )
        assert ai_models.is_paid_model("int-one") is False
        assert ai_models.is_paid_model("str-true") is False
        assert ai_models.is_paid_model("list-truthy") is False
        assert ai_models.is_paid_model("real-true") is True

    def test_monkeypatching_ai_models_alone_does_not_affect_is_paid_model(
        self, monkeypatch
    ) -> None:
        # _MODEL_META_BY_SLUG is built once at import time from AI_MODELS;
        # it is a frozen snapshot, not a live view.
        monkeypatch.setattr(ai_models, "AI_MODELS", [{"value": "new/model", "paid": True}])
        assert ai_models.is_paid_model("new/model") is False


class TestContextLengthFor:
    def test_known_slug_returns_catalog_value(self, monkeypatch) -> None:
        monkeypatch.setattr(
            ai_models, "_MODEL_META_BY_SLUG", {"x/y": {"value": "x/y", "context_length": 131072}}
        )
        assert ai_models.context_length_for("x/y") == 131072

    def test_unknown_slug_returns_default(self) -> None:
        assert ai_models.context_length_for("not/a/real-model") == 32_000

    def test_custom_default_is_honored(self) -> None:
        assert ai_models.context_length_for("not/a/real-model", default=50_000) == 50_000

    def test_missing_context_length_field_falls_back_to_default(self, monkeypatch) -> None:
        monkeypatch.setattr(ai_models, "_MODEL_META_BY_SLUG", {"x/y": {"value": "x/y"}})
        assert ai_models.context_length_for("x/y") == 32_000

    def test_non_positive_context_length_falls_back_to_default(self, monkeypatch) -> None:
        monkeypatch.setattr(
            ai_models, "_MODEL_META_BY_SLUG", {"x/y": {"value": "x/y", "context_length": 0}}
        )
        assert ai_models.context_length_for("x/y") == 32_000

    def test_non_int_context_length_falls_back_to_default(self, monkeypatch) -> None:
        monkeypatch.setattr(
            ai_models, "_MODEL_META_BY_SLUG", {"x/y": {"value": "x/y", "context_length": "131072"}}
        )
        assert ai_models.context_length_for("x/y") == 32_000

    def test_blank_slug_returns_default(self) -> None:
        assert ai_models.context_length_for("") == 32_000
        assert ai_models.context_length_for(None) == 32_000


class TestSetCatalog:
    def test_replaces_both_ai_models_and_meta_index(self, monkeypatch) -> None:
        monkeypatch.setattr(ai_models, "AI_MODELS", [])
        monkeypatch.setattr(ai_models, "_MODEL_META_BY_SLUG", {})

        ai_models.set_catalog([{"value": "new/model", "label": "New", "paid": True}])

        assert ai_models.AI_MODELS == [{"value": "new/model", "label": "New", "paid": True}]
        assert ai_models.is_paid_model("new/model") is True

    def test_empty_list_raises_and_leaves_catalog_untouched(self, monkeypatch) -> None:
        original = [{"value": "keep/me", "paid": False}]
        monkeypatch.setattr(ai_models, "AI_MODELS", original)

        with pytest.raises(ValueError, match="empty model catalog"):
            ai_models.set_catalog([])

        assert ai_models.AI_MODELS == original


class TestRefreshFromOpenrouter:
    @pytest.fixture(autouse=True)
    def _restore_catalog(self):
        # refresh_from_openrouter -> set_catalog reassigns module globals via
        # `global`, which monkeypatch.setattr can't auto-undo -- restore by hand.
        original_models = ai_models.AI_MODELS
        original_meta = ai_models._MODEL_META_BY_SLUG
        yield
        ai_models.AI_MODELS = original_models
        ai_models._MODEL_META_BY_SLUG = original_meta

    async def test_success_installs_fetched_catalog(self, monkeypatch) -> None:
        fetched = [{"value": "fresh/model", "label": "Fresh", "paid": False}]
        monkeypatch.setattr(
            "backend.app.external.openrouter_catalog.fetch_openrouter_catalog",
            AsyncMock(return_value=fetched),
        )

        await ai_models.refresh_from_openrouter()

        assert ai_models.AI_MODELS == fetched

    async def test_propagates_fetch_failure_without_changing_catalog(self, monkeypatch) -> None:
        original = list(ai_models.AI_MODELS)
        monkeypatch.setattr(
            "backend.app.external.openrouter_catalog.fetch_openrouter_catalog",
            AsyncMock(side_effect=RuntimeError("network down")),
        )

        with pytest.raises(RuntimeError, match="network down"):
            await ai_models.refresh_from_openrouter()

        assert ai_models.AI_MODELS == original
