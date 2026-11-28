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
from app.models import User
from app.security import (
    TOKEN_LIFETIME,
    create_access_token,
    decode_access_token,
    dummy_hash,
    password_hash,
    unauthorized,
)

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
    token_type: str = "bearer"
    expires_in: int = int(TOKEN_LIFETIME.total_seconds())


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
    response.headers["Cache-Control"] = "no-store"
    response.headers["Pragma"] = "no-cache"
    user = session.scalar(select(User).where(User.email == str(data.email)))
    try:
        valid = password_hash.verify(
            data.password.get_secret_value(), user.password_hash if user else dummy_hash
        )
    except (UnknownHashError, HashVerificationError):
        valid = False
    if not user or not valid:
        raise unauthorized()
    return TokenOutput(access_token=create_access_token(user.id, settings))


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    session: Database,
    settings: Configuration,
) -> User:
    if credentials is None:
        raise unauthorized()
    user = session.get(User, decode_access_token(credentials.credentials, settings))
    if user is None:
        raise unauthorized()
    return user


@router.get("/me", response_model=UserOutput)
def me(user: Annotated[User, Depends(get_current_user)]):
    return user
