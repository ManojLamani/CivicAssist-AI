from datetime import UTC, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pwdlib.exceptions import HashVerificationError, UnknownHashError
from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import AuthSettings, get_auth_settings
from app.database import get_session
from app.models import LoginSession, User
from app.security import (
    TOKEN_LIFETIME,
    create_access_token,
    decode_access_token,
    dummy_hash,
    password_hash,
    unauthorized,
)
from app.sessions import revoke_session, rotate_session, start_session

router = APIRouter(prefix="/api/v1/auth", tags=["authentication"])
Database = Annotated[Session, Depends(get_session)]
Configuration = Annotated[AuthSettings, Depends(get_auth_settings)]
bearer = HTTPBearer(auto_error=False)


class LoginInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr = Field(max_length=320)
    password: SecretStr = Field(min_length=1, max_length=128)

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email(cls, value):
        return value.strip().lower() if isinstance(value, str) else value


class RegisterInput(LoginInput):
    password: SecretStr = Field(min_length=12, max_length=128)
    full_name: str = Field(min_length=1, max_length=160)

    @field_validator("full_name", mode="before")
    @classmethod
    def trim_name(cls, value):
        return value.strip() if isinstance(value, str) else value


class UserOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    email: str
    full_name: str
    role_name: str


class TokenOutput(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int = int(TOKEN_LIFETIME.total_seconds())


class RefreshInput(BaseModel):
    model_config = ConfigDict(extra="forbid")
    refresh_token: SecretStr = Field(min_length=1, max_length=128)


def token_response(
    login_session: LoginSession, refresh_token: str, settings: AuthSettings, response: Response
) -> TokenOutput:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    return TokenOutput(
        access_token=create_access_token(login_session.user_id, login_session.id, settings),
        refresh_token=refresh_token,
    )


@router.post("/register", status_code=201, response_model=UserOutput)
def register(data: RegisterInput, session: Database):
    user = User(
        email=str(data.email),
        full_name=data.full_name,
        password_hash=password_hash.hash(data.password.get_secret_value()),
        role_name="citizen",
    )
    session.add(user)
    try:
        session.commit()
    except IntegrityError as exc:
        session.rollback()
        if getattr(exc.orig, "sqlstate", None) == "23505":
            raise HTTPException(status_code=409, detail="Email already registered") from None
        raise
    session.refresh(user)
    return user


@router.post("/login", response_model=TokenOutput)
def login(data: LoginInput, session: Database, settings: Configuration, response: Response):
    user = session.scalar(select(User).where(User.email == str(data.email)))
    try:
        valid = password_hash.verify(
            data.password.get_secret_value(), user.password_hash if user else dummy_hash
        )
    except (UnknownHashError, HashVerificationError):
        valid = False
    if not user or not valid:
        raise unauthorized()
    login_session, refresh_token = start_session(session, user.id)
    return token_response(login_session, refresh_token, settings, response)


@router.post("/refresh", response_model=TokenOutput)
def refresh(data: RefreshInput, session: Database, settings: Configuration, response: Response):
    login_session, refresh_token = rotate_session(session, data.refresh_token.get_secret_value())
    return token_response(login_session, refresh_token, settings, response)


@router.post("/logout", status_code=204)
def logout(data: RefreshInput, session: Database):
    revoke_session(session, data.refresh_token.get_secret_value())
    return Response(status_code=204)


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    session: Database,
    settings: Configuration,
) -> User:
    if credentials is None:
        raise unauthorized()
    user_id, session_id = decode_access_token(credentials.credentials, settings)
    login_session = session.get(LoginSession, session_id)
    if (
        login_session is None
        or login_session.user_id != user_id
        or login_session.revoked_at
        or login_session.expires_at <= datetime.now(UTC)
    ):
        raise unauthorized()
    user = session.get(User, user_id)
    if user is None:
        raise unauthorized()
    return user


@router.get("/me", response_model=UserOutput)
def me(user: Annotated[User, Depends(get_current_user)]):
    return user
