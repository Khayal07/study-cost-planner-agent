"""Auth endpoints: register, login, current user, profile update."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.schemas import (
    AuthResponse,
    LoginRequest,
    ProfileUpdate,
    RegisterRequest,
    UserOut,
)
from app.core.security import (
    create_access_token,
    get_current_user,
    hash_password,
    verify_password,
)
from app.data.db import get_session
from app.data.models import User

router = APIRouter(prefix="/auth", tags=["auth"])


def _to_out(user: User) -> UserOut:
    return UserOut(
        id=user.id, email=user.email, nationality=user.nationality,
        gpa=float(user.gpa) if user.gpa is not None else None,
        language_test=user.language_test,
    )


@router.post("/register", response_model=AuthResponse)
def register(req: RegisterRequest, session: Session = Depends(get_session)) -> AuthResponse:
    email = req.email.strip().lower()
    if session.scalar(select(User).where(User.email == email)) is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Email already registered")
    user = User(email=email, password_hash=hash_password(req.password))
    session.add(user)
    session.commit()
    session.refresh(user)
    return AuthResponse(token=create_access_token(user.id), user=_to_out(user))


@router.post("/login", response_model=AuthResponse)
def login(req: LoginRequest, session: Session = Depends(get_session)) -> AuthResponse:
    email = req.email.strip().lower()
    user = session.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(req.password, user.password_hash):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    return AuthResponse(token=create_access_token(user.id), user=_to_out(user))


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> UserOut:
    return _to_out(user)


@router.put("/me/profile", response_model=UserOut)
def update_profile(
    req: ProfileUpdate,
    user: User = Depends(get_current_user),
    session: Session = Depends(get_session),
) -> UserOut:
    user.nationality = req.nationality
    user.gpa = req.gpa
    user.language_test = req.language_test
    session.commit()
    session.refresh(user)
    return _to_out(user)
