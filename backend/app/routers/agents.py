import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile
from sqlalchemy.orm import Session

from app.config import settings
from app.db import get_db
from app.models import Agent
from app.schemas import AgentCreate, AgentOut, AgentUpdate, ToolOut
from app.tools_catalog import TOOLS

router = APIRouter()


@router.get("/tools", response_model=list[ToolOut])
def list_tools():
    return TOOLS


@router.get("/agents", response_model=list[AgentOut])
def list_agents(db: Session = Depends(get_db)):
    return db.query(Agent).order_by(Agent.created_at.desc()).all()


@router.post("/agents", response_model=AgentOut, status_code=201)
def create_agent(payload: AgentCreate, db: Session = Depends(get_db)):
    agent = Agent(**payload.model_dump())
    db.add(agent)
    db.commit()
    db.refresh(agent)
    return agent


@router.get("/agents/{agent_id}", response_model=AgentOut)
def get_agent(agent_id: uuid.UUID, db: Session = Depends(get_db)):
    agent = db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    return agent


@router.patch("/agents/{agent_id}", response_model=AgentOut)
def update_agent(agent_id: uuid.UUID, payload: AgentUpdate, db: Session = Depends(get_db)):
    agent = db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(agent, field, value)
    db.commit()
    db.refresh(agent)
    return agent


@router.delete("/agents/{agent_id}", status_code=204)
def delete_agent(agent_id: uuid.UUID, db: Session = Depends(get_db)):
    agent = db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")
    db.delete(agent)
    db.commit()


@router.post("/agents/{agent_id}/knowledge-file", response_model=AgentOut)
async def upload_knowledge_file(agent_id: uuid.UUID, file: UploadFile, db: Session = Depends(get_db)):
    agent = db.get(Agent, agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")

    os.makedirs(settings.knowledge_dir, exist_ok=True)
    stored_name = f"{agent_id}_{file.filename}"
    dest_path = os.path.join(settings.knowledge_dir, stored_name)
    with open(dest_path, "wb") as f:
        f.write(await file.read())

    agent.knowledge_file_name = file.filename
    db.commit()
    db.refresh(agent)
    return agent
