from uuid import UUID

from fastapi import HTTPException
from sqlalchemy.orm import Session

from app.models import Complaint, ComplaintStatus, ComplaintStatusHistory

TRANSITIONS = {
    ComplaintStatus.SUBMITTED: (ComplaintStatus.ACKNOWLEDGED,),
    ComplaintStatus.ACKNOWLEDGED: (ComplaintStatus.IN_PROGRESS,),
    ComplaintStatus.IN_PROGRESS: (ComplaintStatus.RESOLVED,),
    ComplaintStatus.RESOLVED: (ComplaintStatus.IN_PROGRESS, ComplaintStatus.CLOSED),
    ComplaintStatus.CLOSED: (),
}


def record_status(
    session: Session, complaint: Complaint, actor_id: UUID, previous: str | None, note: str
):
    session.add(
        ComplaintStatusHistory(
            complaint_id=complaint.id,
            actor_id=actor_id,
            from_status=previous,
            to_status=complaint.status,
            note=note,
            **({"created_at": complaint.created_at} if previous is None else {}),
        )
    )


def change_status(
    session: Session,
    complaint_id: UUID,
    actor_id: UUID,
    expected: ComplaintStatus,
    target: ComplaintStatus,
    note: str,
) -> Complaint:
    complaint = session.get(Complaint, complaint_id, with_for_update=True, populate_existing=True)
    if complaint is None:
        raise HTTPException(status_code=404, detail="Complaint not found")
    if complaint.status != expected or target not in TRANSITIONS[ComplaintStatus(complaint.status)]:
        raise HTTPException(
            status_code=409, detail="Status changed or transition not allowed; refresh and review"
        )
    previous = complaint.status
    complaint.status = target
    record_status(session, complaint, actor_id, previous, note)
    session.commit()
    session.refresh(complaint)
    return complaint
