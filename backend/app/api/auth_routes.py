from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .utils import get_user_id_from_request, _hash_password, _verify_password
from app.database import get_db, User
from app.auth import create_access_token
from app.config import settings

router = APIRouter()


class RegisterRequest(BaseModel):
    email: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


@router.post("/login/")
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email).first()
    if not user:
        raise HTTPException(status_code=401, detail="Invalid credentials")

    if not _verify_password(user.password, payload.password):
        raise HTTPException(status_code=401, detail="Invalid credentials")

    token = create_access_token({"sub": str(user.id), "email": user.email})
    resp = JSONResponse({"id": str(user.id), "email": user.email, "access_token": token})
    max_age = int(settings.jwt_access_token_expire_minutes) * 60
    resp.set_cookie("access_token", token, httponly=True, samesite="lax", max_age=max_age)
    return resp


@router.post("/register/")
def register(payload: RegisterRequest, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    hashed = _hash_password(payload.password)

    user = User(email=payload.email, password=hashed)
    db.add(user)
    try:
        db.commit()
        db.refresh(user)
    except Exception as exc:
        db.rollback()
        raise HTTPException(status_code=500, detail=str(exc))

    token = create_access_token({"sub": str(user.id), "email": user.email})
    resp = JSONResponse({"id": str(user.id), "email": user.email, "access_token": token})
    max_age = int(settings.jwt_access_token_expire_minutes) * 60
    resp.set_cookie("access_token", token, httponly=True, samesite="lax", max_age=max_age)
    return resp


@router.get("/me/")
def me(request: Request, db: Session = Depends(get_db)):
    user_id = get_user_id_from_request(request)
    if not user_id:
        raise HTTPException(status_code=401, detail="Not authenticated")

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    return JSONResponse({"id": str(user.id), "email": user.email})


@router.post("/logout/")
def logout():
    resp = JSONResponse({"message": "Logged out"})
    resp.set_cookie("access_token", "", httponly=True, samesite="lax", max_age=0)
    return resp