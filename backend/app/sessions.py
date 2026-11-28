import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import LoginSession, RefreshToken
from app.security import unauthorized

SESSION_LIFETIME = timedelta(days=7)


def hash_refresh_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def issue_refresh_token(session: Session, login_session: LoginSession) -> str:
    token = secrets.token_urlsafe(48)
    session.add(RefreshToken(token_hash=hash_refresh_token(token), session_id=login_session.id))
    return token


def start_session(session: Session, user_id: UUID) -> tuple[LoginSession, str]:
    login_session = LoginSession(user_id=user_id, expires_at=datetime.now(UTC) + SESSION_LIFETIME)
    session.add(login_session)
    session.flush()
    token = issue_refresh_token(session, login_session)
    session.commit()
    return login_session, token


def lock_session(session: Session, token: str) -> LoginSession | None:
    session_id = session.scalar(
        select(RefreshToken.session_id).where(RefreshToken.token_hash == hash_refresh_token(token))
    )
    if session_id is None:
        return None
    # Serialize refresh and logout for this login, including concurrent refresh attempts.
    return session.scalar(
        select(LoginSession).where(LoginSession.id == session_id).with_for_update()
    )


def rotate_session(session: Session, token: str) -> tuple[LoginSession, str]:
    login_session = lock_session(session, token)
    now = datetime.now(UTC)
    if login_session is None or login_session.revoked_at or login_session.expires_at <= now:
        raise unauthorized()
    # Read after acquiring the session lock so a waiting request sees the previous rotation.
    stored_token = session.get(RefreshToken, hash_refresh_token(token), populate_existing=True)
    if stored_token.used_at is not None:
        login_session.revoked_at = now
        session.commit()  # Persist replay revocation even though this request returns HTTP 401.
        raise unauthorized()
    stored_token.used_at = now
    new_token = issue_refresh_token(session, login_session)
    session.commit()
    return login_session, new_token


def revoke_session(session: Session, token: str) -> None:
    login_session = lock_session(session, token)
    if login_session is not None and login_session.revoked_at is None:
        login_session.revoked_at = datetime.now(UTC)
        session.commit()
