from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, Response
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, select

from app.auth import Database, get_current_user
from app.complaint_status import TRANSITIONS, change_status
from app.complaints import ComplaintDetail, ComplaintPage, complaint_detail
from app.models import Complaint, ComplaintStatus, User

router = APIRouter(prefix="/api/v1/admin/complaints", tags=["administration"])


def require_admin(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.role_name != "administrator":
        raise HTTPException(status_code=403, detail="Administrator access required")
    return user


Administrator = Annotated[User, Depends(require_admin)]


class StatusUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    expected_status: ComplaintStatus
    status: ComplaintStatus
    note: str = Field(min_length=1, max_length=1000)


class AdminComplaintDetail(ComplaintDetail):
    allowed_statuses: list[ComplaintStatus]


def admin_detail(session: Database, complaint: Complaint):
    return {
        **complaint_detail(session, complaint),
        "allowed_statuses": TRANSITIONS[ComplaintStatus(complaint.status)],
    }


@router.get("", response_model=ComplaintPage)
def list_complaints(
    session: Database,
    response: Response,
    user: Administrator,
    limit: Annotated[int, Query(ge=1, le=50)] = 20,
    offset: Annotated[int, Query(ge=0, le=100000)] = 0,
):
    response.headers["Cache-Control"] = "no-store"
    return {
        "items": session.scalars(
            select(Complaint)
            .order_by(Complaint.created_at.desc(), Complaint.id.desc())
            .limit(limit)
            .offset(offset)
        ).all(),
        "total": session.scalar(select(func.count()).select_from(Complaint)),
        "limit": limit,
        "offset": offset,
    }


@router.get("/{complaint_id}", response_model=AdminComplaintDetail)
def get_complaint(complaint_id: UUID, session: Database, response: Response, user: Administrator):
    response.headers["Cache-Control"] = "no-store"
    complaint = session.get(Complaint, complaint_id)
    if complaint is None:
        raise HTTPException(status_code=404, detail="Complaint not found")
    return admin_detail(session, complaint)


@router.patch("/{complaint_id}/status", response_model=AdminComplaintDetail)
def update_status(
    complaint_id: UUID,
    data: StatusUpdate,
    session: Database,
    response: Response,
    user: Administrator,
):
    response.headers["Cache-Control"] = "no-store"
    complaint = change_status(
        session, complaint_id, user.id, data.expected_status, data.status, data.note
    )
    return admin_detail(session, complaint)
