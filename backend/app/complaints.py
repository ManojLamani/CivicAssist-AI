from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.auth import Database, get_current_user
from app.complaint_status import record_status
from app.models import Complaint, ComplaintCategory, ComplaintStatusHistory, User

router = APIRouter(prefix="/api/v1/complaints", tags=["complaints"])


class ComplaintInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    submission_id: UUID
    title: str = Field(min_length=5, max_length=160)
    description: str = Field(min_length=10, max_length=5000)
    category: ComplaintCategory
    location: str = Field(min_length=5, max_length=500)


class ComplaintOutput(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    title: str
    description: str
    category: ComplaintCategory
    location: str
    status: str
    created_at: datetime


class ComplaintSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: UUID
    title: str
    category: ComplaintCategory
    status: str
    created_at: datetime


class StatusEvent(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    from_status: str | None
    to_status: str
    note: str
    created_at: datetime


class ComplaintDetail(ComplaintOutput):
    history: list[StatusEvent]


def complaint_detail(session: Database, complaint: Complaint):
    history = session.scalars(
        select(ComplaintStatusHistory)
        .where(ComplaintStatusHistory.complaint_id == complaint.id)
        .order_by(ComplaintStatusHistory.id)
    ).all()
    return {**ComplaintOutput.model_validate(complaint).model_dump(), "history": history}


class ComplaintPage(BaseModel):
    items: list[ComplaintSummary]
    total: int
    limit: int
    offset: int


def require_citizen(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role_name != "citizen":
        raise HTTPException(status_code=403, detail="Only citizens can access these complaints")
    return user


Citizen = Annotated[User, Depends(require_citizen)]


@router.get("", response_model=ComplaintPage)
def list_complaints(
    session: Database,
    response: Response,
    user: Citizen,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
):
    response.headers["Cache-Control"] = "no-store"
    owned = Complaint.user_id == user.id
    total = session.scalar(select(func.count()).select_from(Complaint).where(owned))
    items = session.scalars(
        select(Complaint)
        .where(owned)
        .order_by(Complaint.created_at.desc(), Complaint.id.desc())
        .limit(limit)
        .offset(offset)
    ).all()
    return {"items": items, "total": total, "limit": limit, "offset": offset}


@router.get("/{complaint_id}", response_model=ComplaintDetail)
def get_complaint(complaint_id: UUID, session: Database, response: Response, user: Citizen):
    response.headers["Cache-Control"] = "no-store"
    complaint = session.scalar(
        select(Complaint).where(Complaint.id == complaint_id, Complaint.user_id == user.id)
    )
    if complaint is None:
        raise HTTPException(status_code=404, detail="Complaint not found")
    return complaint_detail(session, complaint)


@router.post("", status_code=201, response_model=ComplaintOutput)
def submit_complaint(
    data: ComplaintInput,
    session: Database,
    response: Response,
    user: Citizen,
):
    response.headers["Cache-Control"] = "no-store"
    complaint = Complaint(user_id=user.id, **data.model_dump())
    session.add(complaint)
    try:
        session.flush()
        record_status(session, complaint, user.id, None, "Complaint submitted.")
        session.commit()
    except IntegrityError:
        session.rollback()
        existing = session.scalar(
            select(Complaint).where(
                Complaint.user_id == user.id, Complaint.submission_id == data.submission_id
            )
        )
        if existing is None:
            raise
        if any(getattr(existing, key) != value for key, value in data.model_dump().items()):
            raise HTTPException(
                status_code=409, detail="Submission ID already used for another report"
            ) from None
        response.status_code = 200
        return existing
    session.refresh(complaint)
    return complaint
