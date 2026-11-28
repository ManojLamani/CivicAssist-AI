from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.database import Base


class Role(Base):
    __tablename__ = "roles"
    __table_args__ = (
        CheckConstraint(
            "name IN ('citizen', 'administrator', 'department_operator')",
            name="ck_roles_name",
        ),
    )

    name: Mapped[str] = mapped_column(String(32), primary_key=True)


class User(Base):
    __tablename__ = "users"
    __table_args__ = (
        CheckConstraint("email = lower(btrim(email)) AND email <> ''", name="ck_users_email"),
        CheckConstraint("btrim(full_name) <> ''", name="ck_users_full_name"),
        CheckConstraint("password_hash <> ''", name="ck_users_password_hash"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    email: Mapped[str] = mapped_column(String(320), unique=True)
    full_name: Mapped[str] = mapped_column(String(160))
    password_hash: Mapped[str] = mapped_column(String(255))
    role_name: Mapped[str] = mapped_column(
        ForeignKey("roles.name"), server_default="citizen", index=True
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class Department(Base):
    __tablename__ = "departments"
    __table_args__ = (
        UniqueConstraint("city", "name", name="uq_departments_city_name"),
        CheckConstraint("btrim(name) <> ''", name="ck_departments_name"),
        CheckConstraint("btrim(city) <> ''", name="ck_departments_city"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(160))
    city: Mapped[str] = mapped_column(String(100))
    is_active: Mapped[bool] = mapped_column(Boolean, server_default="true")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class DepartmentOperator(Base):
    __tablename__ = "department_operators"

    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), primary_key=True
    )
    department_id: Mapped[UUID] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE"), primary_key=True, index=True
    )


class LoginSession(Base):
    __tablename__ = "login_sessions"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class RefreshToken(Base):
    __tablename__ = "refresh_tokens"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    session_id: Mapped[UUID] = mapped_column(
        ForeignKey("login_sessions.id", ondelete="CASCADE"), index=True
    )
    used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
