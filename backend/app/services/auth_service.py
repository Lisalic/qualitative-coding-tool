"""Password reset via emailed, stateless signed tokens.

A reset token is a short-lived token from ``backend/app/auth.py`` carrying
``purpose="pwd_reset"`` and ``pwh`` -- a fingerprint of the user's current
password hash. Changing the password changes the fingerprint, so a token
stops working as soon as it is used (or the password changes any other
way). Nothing is stored per token, so any backend instance can verify one
with just the shared secret.

The only stored state is ``users.password_reset_requested_at``, a
per-account cooldown claimed with one conditional ``UPDATE`` so concurrent
requests across instances can't each send an email.
"""

import hmac
from datetime import datetime, timedelta, timezone
from html import escape
from typing import Optional

from sqlalchemy import func, or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.utils import _hash_password
from backend.app.auth import create_access_token, decode_access_token, password_fingerprint
from backend.app.config import settings
from backend.app.core.exceptions import ValidationAppError
from backend.app.core.logging import get_logger
from backend.app.database import User
from backend.app.external.email_client import email_configured, send_email

logger = get_logger(__name__)

RESET_PURPOSE = "pwd_reset"
INVALID_TOKEN_MESSAGE = "This reset link is invalid or has expired. Request a new one."

_password_fingerprint = password_fingerprint


async def find_user_by_email(db: AsyncSession, email: str) -> Optional[User]:
    """Case-insensitive lookup; ``email`` must already be normalized (lowercased).

    Takes the oldest match rather than requiring exactly one: on a
    database the ``uq_users_email_lower`` revision couldn't apply to (it
    refuses while case-duplicate accounts exist), ``scalar_one_or_none``
    raised and every login for that address returned a 500.
    """
    result = await db.execute(select(User).where(func.lower(User.email) == email).order_by(User.id).limit(1))
    return result.scalars().first()


def create_reset_token(user: User) -> str:
    return create_access_token(
        {"sub": str(user.id), "purpose": RESET_PURPOSE, "pwh": _password_fingerprint(user.password)},
        expires_minutes=settings.password_reset_token_expire_minutes,
    )


def build_reset_link(token: str) -> str:
    return f"{settings.frontend_url.rstrip('/')}/reset-password?token={token}"


async def request_password_reset(db: AsyncSession, email: str) -> Optional[tuple[str, str]]:
    """Return ``(email, reset_link)`` to send, or ``None`` when nothing should go out.

    ``None`` covers an unknown email, a request inside the cooldown window,
    and unconfigured email -- the route answers identically in every case
    so the response never reveals whether an account exists.
    """
    user = await find_user_by_email(db, email)
    if user is None:
        return None
    if not email_configured():
        logger.warning("Password reset requested but Brevo email is not configured; nothing sent")
        return None

    now = datetime.now(timezone.utc)
    cutoff = now - timedelta(seconds=settings.password_reset_cooldown_seconds)
    claimed = await db.execute(
        update(User)
        .where(
            User.id == user.id,
            or_(User.password_reset_requested_at.is_(None), User.password_reset_requested_at < cutoff),
        )
        .values(password_reset_requested_at=now)
        # Let the database alone decide the claim; in-Python session sync
        # would re-evaluate the WHERE against a possibly stale loaded row.
        .execution_options(synchronize_session=False)
    )
    await db.commit()
    if claimed.rowcount == 0:
        return None
    return user.email, build_reset_link(create_reset_token(user))


async def send_reset_email(to: str, link: str) -> None:
    """Background task: send the reset email, logging (never raising) on failure."""
    minutes = settings.password_reset_token_expire_minutes
    subject = "Reset your Qualitative Coding Tool password"
    text = (
        "We received a request to reset your password.\n\n"
        f"Open this link to choose a new one (valid for {minutes} minutes):\n{link}\n\n"
        "If you didn't ask for this, you can ignore this email."
    )
    safe_link = escape(link, quote=True)
    html = (
        "<p>We received a request to reset your password.</p>"
        f'<p><a href="{safe_link}">Choose a new password</a> (valid for {minutes} minutes).</p>'
        f"<p>Or paste this link into your browser:<br>{safe_link}</p>"
        "<p>If you didn't ask for this, you can ignore this email.</p>"
    )
    try:
        await send_email(to, subject, html, text)
    except Exception:  # noqa: BLE001 - a failed send must not surface to the requester
        logger.exception("Failed to send password reset email")


async def reset_password(db: AsyncSession, token: str, new_password: str) -> None:
    """Set a new password from a valid reset token, or raise ``ValidationAppError``."""
    try:
        payload = decode_access_token(token)
    except ValueError:
        raise ValidationAppError(INVALID_TOKEN_MESSAGE) from None
    if payload.get("purpose") != RESET_PURPOSE:
        raise ValidationAppError(INVALID_TOKEN_MESSAGE)

    try:
        user_id = int(payload.get("sub"))
    except (TypeError, ValueError):
        raise ValidationAppError(INVALID_TOKEN_MESSAGE) from None
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one_or_none()
    if user is None or not hmac.compare_digest(
        str(payload.get("pwh", "")), _password_fingerprint(user.password)
    ):
        raise ValidationAppError(INVALID_TOKEN_MESSAGE)

    user.password = _hash_password(new_password)
    await db.commit()
