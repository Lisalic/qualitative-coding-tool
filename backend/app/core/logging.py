"""One place to configure logging; replaces scattered ``print()`` calls.

``configure_logging()`` is called once from ``main.py`` at startup.
Existing ``print()`` calls are migrated to ``get_logger(__name__)`` per
call site as each file is touched by a later stage, not all at once.
"""

import logging
import os

_CONFIGURED = False


def configure_logging() -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return
    level_name = os.environ.get("LOG_LEVEL", "INFO").upper()
    level = getattr(logging, level_name, logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )
    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
