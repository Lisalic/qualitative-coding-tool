"""SQLAlchemy ORM models, all registered on ``backend.app.core.database.Base``.

Importing this package (or any module in it) registers every table on
``Base.metadata``: Alembic's ``env.py``, the startup schema check and the
tests' ``create_all`` all need the full set, not just the tables some
caller happened to import.
"""

from backend.app.models import job, storage, versioning, workspace  # noqa: F401
