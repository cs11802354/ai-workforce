"""Read-only view of executions.

Runs are now written by the conversation turn handler, which awaits the workflow
and therefore knows the outcome immediately — so unlike the old implementation
there is no lazy "reconcile against Temporal on read" step, and a run can never
sit at `running` forever just because nobody fetched it.
"""

import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db import get_db
from app.models import Run
from app.schemas import RunOut

router = APIRouter()


@router.get("/runs", response_model=list[RunOut])
def list_runs(db: Session = Depends(get_db)):
    return db.query(Run).order_by(Run.created_at.desc()).limit(200).all()


@router.get("/runs/{run_id}", response_model=RunOut)
def get_run(run_id: uuid.UUID, db: Session = Depends(get_db)):
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(404, "Run not found")
    return run


@router.get("/agents/{agent_id}/runs", response_model=list[RunOut])
def list_runs_for_agent(agent_id: uuid.UUID, db: Session = Depends(get_db)):
    return (
        db.query(Run)
        .filter(Run.agent_id == agent_id)
        .order_by(Run.created_at.desc())
        .all()
    )
