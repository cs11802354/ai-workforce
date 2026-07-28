import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from temporalio.client import WorkflowExecutionStatus

from app.config import settings
from app.db import get_db
from app.models import Agent, Run
from app.schemas import RunCreate, RunOut
from app.temporal_client import get_temporal_client

router = APIRouter()


@router.post("/runs", response_model=RunOut, status_code=201)
async def start_run(payload: RunCreate, db: Session = Depends(get_db)):
    agent = db.get(Agent, payload.agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")

    workflow_id = f"agent-run-{uuid.uuid4()}"
    agent_snapshot = {
        "name": agent.name,
        "description": agent.description,
        "provider": agent.provider,
        "model": agent.model,
        "tools": agent.tools,
    }

    client = await get_temporal_client()
    handle = await client.start_workflow(
        "AgentRunWorkflow",
        args=[agent_snapshot, payload.input],
        id=workflow_id,
        task_queue=settings.temporal_task_queue,
    )

    run = Run(
        agent_id=agent.id,
        input_message=payload.input,
        status="running",
        temporal_workflow_id=handle.id,
        temporal_run_id=handle.result_run_id,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    return run


@router.get("/runs/{run_id}", response_model=RunOut)
async def get_run(run_id: uuid.UUID, db: Session = Depends(get_db)):
    run = db.get(Run, run_id)
    if not run:
        raise HTTPException(404, "Run not found")

    if run.status == "running":
        client = await get_temporal_client()
        handle = client.get_workflow_handle(run.temporal_workflow_id)
        desc = await handle.describe()

        if desc.status == WorkflowExecutionStatus.COMPLETED:
            run.output_text = await handle.result()
            run.status = "completed"
            run.completed_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(run)
        elif desc.status in (
            WorkflowExecutionStatus.FAILED,
            WorkflowExecutionStatus.TIMED_OUT,
            WorkflowExecutionStatus.TERMINATED,
            WorkflowExecutionStatus.CANCELED,
        ):
            run.status = "failed"
            run.completed_at = datetime.now(timezone.utc)
            db.commit()
            db.refresh(run)

    return run


@router.get("/agents/{agent_id}/runs", response_model=list[RunOut])
def list_runs_for_agent(agent_id: uuid.UUID, db: Session = Depends(get_db)):
    return db.query(Run).filter(Run.agent_id == agent_id).order_by(Run.created_at.desc()).all()


@router.get("/runs", response_model=list[RunOut])
def list_runs(db: Session = Depends(get_db)):
    return db.query(Run).order_by(Run.created_at.desc()).limit(50).all()
