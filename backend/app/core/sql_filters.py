"""Filters built from user-controlled input: membership in a list of
values (:func:`in_values`) and substring search (:func:`contains_pattern`).

``column.in_(values)`` binds one parameter per value, and Postgres (via
asyncpg) refuses any statement with more than 32,767 parameters -- so a
filter that keeps 35,000 posts failed outright. :func:`in_values` binds
the whole list as ONE array parameter on Postgres (``col = ANY($1)``) and
falls back to a plain ``IN`` elsewhere (SQLite in the unit tests), so
callers never have to chunk.

Use it for any list whose length the user controls (row ids from a
selection, a filter, a move); a handful of internal ids can stay on
``in_``.
"""

from __future__ import annotations

from collections.abc import Iterable
from typing import Any

from sqlalchemy import any_, bindparam
from sqlalchemy.dialects.postgresql import ARRAY
from sqlalchemy.ext.compiler import compiles
from sqlalchemy.sql.elements import ColumnElement
from sqlalchemy.types import Boolean


class _InValues(ColumnElement):
    # The values differ on every call, so a cached compiled form would be
    # wrong -- opt out of the statement cache rather than key on them.
    inherit_cache = False
    type = Boolean()

    def __init__(self, column: ColumnElement, values: list[Any]) -> None:
        self.column = column
        self.values = values


@compiles(_InValues)
def _compile_in(element: _InValues, compiler: Any, **kw: Any) -> str:
    return compiler.process(element.column.in_(element.values), **kw)


@compiles(_InValues, "postgresql")
def _compile_any(element: _InValues, compiler: Any, **kw: Any) -> str:
    param = bindparam(None, element.values, type_=ARRAY(element.column.type))
    return compiler.process(element.column == any_(param), **kw)


def in_values(column: ColumnElement, values: Iterable[Any]) -> ColumnElement:
    """``column IN values``, as a single bound parameter on Postgres."""
    return _InValues(column, list(values))


LIKE_ESCAPE = "\\"


def contains_pattern(term: str) -> str:
    """A ``LIKE``/``ILIKE`` pattern matching ``term`` anywhere, literally.

    ``%`` and ``_`` are wildcards in a pattern, so a search for "50%" or
    "snake_case" matched the wrong rows until escaped. Pass
    ``escape=LIKE_ESCAPE`` alongside it.
    """
    escaped = term.replace(LIKE_ESCAPE, LIKE_ESCAPE * 2).replace("%", LIKE_ESCAPE + "%").replace("_", LIKE_ESCAPE + "_")
    return f"%{escaped}%"
