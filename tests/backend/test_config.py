"""Tests for backend/app/config.py::Settings."""

from backend.app.config import Settings


class TestSettingsDefaults:
    def test_defaults_with_cleared_environment(self, monkeypatch) -> None:
        for key in [
            "DATABASE_URL",
            "SECRET_KEY",
            "AUTH_DATABASE_URL",
            "JWT_SECRET_KEY",
            "JWT_ALGORITHM",
            "JWT_ACCESS_TOKEN_EXPIRE_MINUTES",
            "JWT_REFRESH_TOKEN_EXPIRE_MINUTES",
        ]:
            monkeypatch.delenv(key, raising=False)
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.database_url == ""
        assert s.secret_key == "your-secret-key-here"
        assert s.auth_database_url == ""
        assert s.jwt_secret_key == ""
        assert s.jwt_algorithm == "HS256"
        assert s.jwt_access_token_expire_minutes == 480
        assert s.jwt_refresh_token_expire_minutes == 10080

    def test_env_var_overrides_default(self, monkeypatch) -> None:
        monkeypatch.setenv("JWT_SECRET_KEY", "from-env")
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.jwt_secret_key == "from-env"

    def test_env_var_names_are_case_insensitive(self, monkeypatch) -> None:
        monkeypatch.setenv("jwt_secret_key", "lowercase-env")
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.jwt_secret_key == "lowercase-env"

    def test_int_field_coerces_numeric_string(self, monkeypatch) -> None:
        monkeypatch.setenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "10")
        s = Settings(_env_file=None)  # type: ignore[call-arg]
        assert s.jwt_access_token_expire_minutes == 10

    def test_int_field_rejects_non_numeric_string(self, monkeypatch) -> None:
        import pytest
        from pydantic import ValidationError

        monkeypatch.setenv("JWT_ACCESS_TOKEN_EXPIRE_MINUTES", "not-a-number")
        with pytest.raises(ValidationError):
            Settings(_env_file=None)  # type: ignore[call-arg]

    def test_extra_env_vars_are_allowed_not_rejected(self, monkeypatch) -> None:
        monkeypatch.setenv("SOME_UNRELATED_APP_SETTING", "x")
        # extra="allow" -- must not raise even though this field isn't declared.
        Settings(_env_file=None)  # type: ignore[call-arg]
