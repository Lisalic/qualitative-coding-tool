from fastapi import APIRouter, BackgroundTasks, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from backend.app.api.utils import _hash_password, _verify_password
from backend.app.database import get_async_db, User
from backend.app.auth import create_access_token, password_fingerprint
from backend.app.core.auth_dependency import session_user_id
from backend.app.config import settings
from backend.app.api.schemas import (
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RegisterRequest,
    ResetPasswordRequest,
)
from backend.app.services import auth_service

router = APIRouter()


def _session_response(user: User) -> JSONResponse:
    """The login/register response: a session token in the body and the
    cookie. ``pwh`` ties the token to the current password, so a reset
    ends it (see ``core/auth_dependency.py``).
    """
    token = create_access_token({
        "sub": str(user.id),
        "email": user.email,
        "pwh": password_fingerprint(user.password),
    })
    resp = JSONResponse({"id": str(user.id), "email": user.email, "access_token": token})
    max_age = int(settings.jwt_access_token_expire_minutes) * 60
    resp.set_cookie("access_token", token, httponly=True, samesite="lax", max_age=max_age)
    return resp


@router.post("/login/")
async def login(payload: LoginRequest, db: AsyncSession = Depends(get_async_db)):
    user = await auth_service.find_user_by_email(db, payload.email)
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not _verify_password(user.password, payload.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    return _session_response(user)


@router.post("/register/")
async def register(payload: RegisterRequest, db: AsyncSession = Depends(get_async_db)):
    if await auth_service.find_user_by_email(db, payload.email):
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed = _hash_password(payload.password)

    user = User(email=payload.email, password=hashed)
    db.add(user)
    try:
        await db.commit()
    except IntegrityError:
        # A concurrent registration for the same address won the race to
        # the lower(email) unique index.
        await db.rollback()
        raise HTTPException(status_code=400, detail="Email already registered") from None
    await db.refresh(user)

    return _session_response(user)


@router.get("/me/")
async def me(request: Request, db: AsyncSession = Depends(get_async_db)):
    user_id = await session_user_id(request, db)
    if user_id is None:
        raise HTTPException(status_code=401, detail="Not authenticated")
    user = (await db.execute(select(User).where(User.id == user_id))).scalar_one()
    return JSONResponse({"id": str(user.id), "email": user.email})


@router.post("/logout/")
async def logout():
    resp = JSONResponse({"message": "Logged out"})
    resp.set_cookie("access_token", "", httponly=True, samesite="lax", max_age=0)
    return resp


@router.post("/forgot-password/", status_code=202, response_model=MessageResponse)
async def forgot_password(
    payload: ForgotPasswordRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_async_db),
) -> MessageResponse:
    # Same response whether or not the account exists; the email goes out
    # after the response so send latency can't reveal it either.
    to_send = await auth_service.request_password_reset(db, payload.email)
    if to_send is not None:
        background_tasks.add_task(auth_service.send_reset_email, *to_send)
    return MessageResponse(message="If an account exists for that email, a reset link has been sent.")


@router.post("/reset-password/", response_model=MessageResponse)
async def reset_password(
    payload: ResetPasswordRequest, db: AsyncSession = Depends(get_async_db)
) -> MessageResponse:
    await auth_service.reset_password(db, payload.token, payload.new_password)
    return MessageResponse(message="Password updated. You can now log in.")
