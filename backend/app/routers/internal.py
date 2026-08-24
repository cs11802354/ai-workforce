"""Worker-to-backend calls. Not part of the public API surface the frontend
uses — gated by InternalAuthDep instead of the app-password AuthDep, and
included in main.py without the router-level AuthDep other routers get."""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.auth import InternalAuthDep
from app.db import get_db
from app.models import ScheduledTask
from app.schemas import ScheduledTaskCreate, ScheduledTaskOut

router = APIRouter()


@router.post(
    "/internal/scheduled-tasks",
    response_model=ScheduledTaskOut,
    status_code=201,
    dependencies=[InternalAuthDep],
)
def upsert_scheduled_task(payload: ScheduledTaskCreate, db: Session = Depends(get_db)):
    """Create, or update in place if the same Temporal schedule was already
    recorded — the tool call that created a schedule can be re-run (e.g. the
    user changes the digest time), which updates the existing Temporal
    Schedule rather than creating a new one, so this mirrors that instead of
    accumulating duplicate rows."""
    existing = (
        db.query(ScheduledTask)
        .filter(ScheduledTask.temporal_schedule_id == payload.temporal_schedule_id)
        .first()
    )
    if existing:
        existing.params = payload.params
        existing.task_type = payload.task_type
        existing.agent_id = payload.agent_id
        existing.status = "active"
        db.commit()
        db.refresh(existing)
        return existing

    task = ScheduledTask(**payload.model_dump())
    db.add(task)
    db.commit()
    db.refresh(task)
    return task
