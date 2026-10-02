"""Single seam for outbound transactional email, via Brevo's REST API.

A plain ``httpx`` POST -- no SDK -- so swapping providers later is a change
to this one module.
"""

import httpx

from backend.app.config import settings
from backend.app.core.logging import get_logger
from backend.app.external.errors import ExternalServiceError

logger = get_logger(__name__)

BREVO_SEND_URL = "https://api.brevo.com/v3/smtp/email"


def email_configured() -> bool:
    return bool(settings.brevo_api_key and settings.brevo_sender_email)


async def send_email(to: str, subject: str, html: str, text: str) -> None:
    """Send one email. Raises ``ExternalServiceError`` on a non-2xx response."""
    if not email_configured():
        raise ExternalServiceError("Email is not configured (BREVO_API_KEY / BREVO_SENDER_EMAIL)")

    payload = {
        "sender": {"name": settings.brevo_sender_name, "email": settings.brevo_sender_email},
        "to": [{"email": to}],
        "subject": subject,
        "htmlContent": html,
        "textContent": text,
    }
    headers = {"api-key": settings.brevo_api_key, "accept": "application/json"}
    async with httpx.AsyncClient(timeout=10.0) as client:
        resp = await client.post(BREVO_SEND_URL, json=payload, headers=headers)
    if resp.status_code >= 300:
        raise ExternalServiceError(f"Brevo send failed: {resp.text}", code=resp.status_code)
