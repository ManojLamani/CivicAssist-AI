from datetime import datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app.auth import Database, get_current_user
from app.models import Complaint, ComplaintCategory, User

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


@router.post("", status_code=201, response_model=ComplaintOutput)
def submit_complaint(
    data: ComplaintInput,
    session: Database,
    response: Response,
    user: Annotated[User, Depends(get_current_user)],
):
    if user.role_name != "citizen":
        raise HTTPException(status_code=403, detail="Only citizens can submit complaints")
    response.headers["Cache-Control"] = "no-store"
    complaint = Complaint(user_id=user.id, **data.model_dump())
    session.add(complaint)
    try:
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
