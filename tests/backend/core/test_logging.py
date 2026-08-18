import logging

from backend.app.core import logging as core_logging


class TestConfigureLogging:
    def test_idempotent(self, monkeypatch) -> None:
        monkeypatch.setattr(core_logging, "_CONFIGURED", False)
        calls = []
        monkeypatch.setattr(
            core_logging.logging, "basicConfig", lambda **kw: calls.append(kw)
        )
        core_logging.configure_logging()
        core_logging.configure_logging()
        assert len(calls) == 1

    def test_respects_log_level_env_var(self, monkeypatch) -> None:
        monkeypatch.setattr(core_logging, "_CONFIGURED", False)
        monkeypatch.setenv("LOG_LEVEL", "DEBUG")
        captured = {}
        monkeypatch.setattr(
            core_logging.logging, "basicConfig", lambda **kw: captured.update(kw)
        )
        core_logging.configure_logging()
        assert captured["level"] == logging.DEBUG


class TestGetLogger:
    def test_returns_named_logger(self) -> None:
        logger = core_logging.get_logger("my.module")
        assert logger.name == "my.module"
