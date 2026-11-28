from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt
from fastapi import HTTPException
from pwdlib import PasswordHash

from app.config import AuthSettings

password_hash = PasswordHash.recommended()
dummy_hash = password_hash.hash("dummy-password-never-used-for-login")
TOKEN_LIFETIME = timedelta(minutes=15)


def unauthorized() -> HTTPException:
    return HTTPException(
        status_code=401, detail="Invalid credentials", headers={"WWW-Authenticate": "Bearer"}
    )


def create_access_token(user_id: UUID, settings: AuthSettings) -> str:
    now = datetime.now(UTC)
    return jwt.encode(
        {
            "sub": str(user_id),
            "iat": now,
            "exp": now + TOKEN_LIFETIME,
            "iss": "civicassist",
            "aud": "civicassist-api",
            "type": "access",
        },
        settings.jwt_secret.get_secret_value(),
        algorithm="HS256",
    )


def decode_access_token(token: str, settings: AuthSettings) -> UUID:
    try:
        claims = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=["HS256"],
            issuer="civicassist",
            audience="civicassist-api",
            options={"require": ["sub", "iat", "exp", "iss", "aud", "type"]},
        )
        if claims["type"] != "access":
            raise unauthorized()
        return UUID(claims["sub"])
    except (jwt.InvalidTokenError, ValueError, TypeError, AttributeError):
        raise unauthorized() from None
