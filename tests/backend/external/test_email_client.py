import httpx
import pytest

from backend.app.config import settings
from backend.app.external import email_client
from backend.app.external.errors import ExternalServiceError


@pytest.fixture()
def configured(monkeypatch) -> None:
    monkeypatch.setattr(settings, "brevo_api_key", "test-key")
    monkeypatch.setattr(settings, "brevo_sender_email", "noreply@example.com")


def _patch_transport(monkeypatch, handler) -> None:
    real_client = httpx.AsyncClient

    def _client(**kwargs):
        return real_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(email_client.httpx, "AsyncClient", _client)


async def test_send_email_posts_brevo_payload(configured, monkeypatch) -> None:
    seen: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return httpx.Response(201, json={"messageId": "m1"})

    _patch_transport(monkeypatch, handler)
    await email_client.send_email("to@x.com", "Subj", "<p>hi</p>", "hi")

    assert len(seen) == 1
    req = seen[0]
    assert str(req.url) == email_client.BREVO_SEND_URL
    assert req.headers["api-key"] == "test-key"
    body = __import__("json").loads(req.content)
    assert body["to"] == [{"email": "to@x.com"}]
    assert body["sender"]["email"] == "noreply@example.com"
    assert body["subject"] == "Subj"


async def test_send_email_non_2xx_raises(configured, monkeypatch) -> None:
    _patch_transport(monkeypatch, lambda request: httpx.Response(401, json={"message": "bad key"}))
    with pytest.raises(ExternalServiceError) as exc:
        await email_client.send_email("to@x.com", "Subj", "<p>hi</p>", "hi")
    assert exc.value.code == 401


async def test_send_email_unconfigured_raises(monkeypatch) -> None:
    monkeypatch.setattr(settings, "brevo_api_key", "")
    with pytest.raises(ExternalServiceError):
        await email_client.send_email("to@x.com", "Subj", "<p>hi</p>", "hi")
