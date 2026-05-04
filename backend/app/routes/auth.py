from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy.orm import Session

from ..auth import (
    clear_session_cookie,
    ensure_csrf_cookie,
    get_current_user,
    get_optional_user,
    hash_password,
    set_session_cookie,
    verify_csrf,
    verify_password,
)
from ..db import get_db
from ..models import User
from ..schemas import AuthResponse, LoginRequest, SignupRequest, UserSummary


router = APIRouter(prefix="/api/auth", tags=["auth"])


@router.get("/me", response_model=AuthResponse)
def get_me(
    request: Request,
    response: Response,
    user: Optional[User] = Depends(get_optional_user),
) -> AuthResponse:
    ensure_csrf_cookie(request, response)
    return AuthResponse(user=UserSummary.from_model(user) if user else None)


@router.post("/signup", response_model=AuthResponse)
def signup(
    req: SignupRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    _csrf: str = Depends(verify_csrf),
) -> AuthResponse:
    email = req.email.lower().strip()
    existing = db.query(User).filter(User.email == email).first()
    if existing:
        raise HTTPException(status_code=409, detail="email already exists")

    user = User(email=email, password_hash=hash_password(req.password))
    db.add(user)
    db.commit()
    db.refresh(user)

    ensure_csrf_cookie(request, response)
    set_session_cookie(response, user.id)
    return AuthResponse(user=UserSummary.from_model(user))


@router.post("/login", response_model=AuthResponse)
def login(
    req: LoginRequest,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
    _csrf: str = Depends(verify_csrf),
) -> AuthResponse:
    email = req.email.lower().strip()
    user = db.query(User).filter(User.email == email).first()
    if not user or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=401, detail="invalid credentials")

    ensure_csrf_cookie(request, response)
    set_session_cookie(response, user.id)
    return AuthResponse(user=UserSummary.from_model(user))


@router.post("/logout", response_model=AuthResponse)
def logout(
    request: Request,
    response: Response,
    _user: User = Depends(get_current_user),
    _csrf: str = Depends(verify_csrf),
) -> AuthResponse:
    ensure_csrf_cookie(request, response)
    clear_session_cookie(response)
    return AuthResponse(user=None)
