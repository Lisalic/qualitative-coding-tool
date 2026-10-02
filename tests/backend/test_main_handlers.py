"""Global exception handlers in backend/app/main.py."""

import json

from sqlalchemy.exc import IntegrityError
from starlette.requests import Request

from backend.app.main import integrity_error_handler


async def test_integrity_error_is_a_409_without_the_sql() -> None:
    request = Request({"type": "http", "method": "POST", "path": "/api/x", "headers": [], "query_string": b""})
    exc = IntegrityError("INSERT INTO row_memos ...", {"body": "secret note"}, Exception("duplicate key"))

    response = await integrity_error_handler(request, exc)

    assert response.status_code == 409
    body = json.loads(response.body)
    assert "INSERT" not in body["error"] and "secret" not in body["error"]
