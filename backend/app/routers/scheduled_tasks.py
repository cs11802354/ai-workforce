import uuid

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import ScheduledTask
from app.schemas import ScheduledTaskOut

router = APIRouter()


@router.get("/conversations/{conversation_id}/scheduled-tasks", response_model=list[ScheduledTaskOut])
def list_scheduled_tasks(conversation_id: uuid.UUID, db: Session = Depends(get_db)):
    return (
        db.query(ScheduledTask)
        .filter(ScheduledTask.conversation_id == conversation_id)
        .order_by(ScheduledTask.created_at.desc())
        .all()
    )
