from datetime import datetime
from enum import StrEnum
from uuid import UUID, uuid4

from sqlalchemy import (
    BigInteger,
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Identity,
    String,
    Text,
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


class ComplaintCategory(StrEnum):
    ROADS = "roads"
    GARBAGE = "garbage"
    WATER_SUPPLY = "water_supply"
    DRAINAGE = "drainage"
    STREETLIGHTS = "streetlights"
    PUBLIC_INFRASTRUCTURE = "public_infrastructure"
    SANITATION = "sanitation"
    OTHER = "other"


class ComplaintStatus(StrEnum):
    SUBMITTED = "submitted"
    ACKNOWLEDGED = "acknowledged"
    IN_PROGRESS = "in_progress"
    RESOLVED = "resolved"
    CLOSED = "closed"


class Complaint(Base):
    __tablename__ = "complaints"
    __table_args__ = (
        UniqueConstraint("user_id", "submission_id", name="uq_complaints_user_submission"),
        CheckConstraint("char_length(btrim(title)) >= 5", name="ck_complaints_title"),
        CheckConstraint(
            "char_length(btrim(description)) BETWEEN 10 AND 5000", name="ck_complaints_description"
        ),
        CheckConstraint("char_length(btrim(location)) >= 5", name="ck_complaints_location"),
        CheckConstraint(
            "category IN ('roads', 'garbage', 'water_supply', 'drainage', "
            "'streetlights', 'public_infrastructure', 'sanitation', 'other')",
            name="ck_complaints_category",
        ),
        CheckConstraint(
            "status IN ('submitted', 'acknowledged', 'in_progress', 'resolved', 'closed')",
            name="ck_complaints_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    submission_id: Mapped[UUID] = mapped_column()
    title: Mapped[str] = mapped_column(String(160))
    description: Mapped[str] = mapped_column(Text)
    category: Mapped[str] = mapped_column(String(32))
    location: Mapped[str] = mapped_column(String(500))
    status: Mapped[str] = mapped_column(String(32), server_default="submitted")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class ComplaintStatusHistory(Base):
    __tablename__ = "complaint_status_history"
    __table_args__ = (
        CheckConstraint(
            "to_status IN ('submitted', 'acknowledged', 'in_progress', 'resolved', 'closed')",
            name="ck_status_history_to_status",
        ),
        CheckConstraint(
            "from_status IN ('submitted', 'acknowledged', 'in_progress', 'resolved', 'closed')",
            name="ck_status_history_from_status",
        ),
        CheckConstraint("char_length(btrim(note)) >= 1", name="ck_status_history_note"),
    )

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    complaint_id: Mapped[UUID] = mapped_column(
        ForeignKey("complaints.id", ondelete="CASCADE"), index=True
    )
    actor_id: Mapped[UUID] = mapped_column(ForeignKey("users.id"))
    from_status: Mapped[str | None] = mapped_column(String(32))
    to_status: Mapped[str] = mapped_column(String(32))
    note: Mapped[str] = mapped_column(String(1000))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.clock_timestamp()
    )
