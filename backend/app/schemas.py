import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AgentCreate(BaseModel):
    name: str
    description: str = ""
    provider: str = "anthropic"
    model: str = "claude-sonnet-5"
    tools: list[str] = []


class AgentUpdate(BaseModel):
    name: str | None = None
    description: str | None = None
    provider: str | None = None
    model: str | None = None
    tools: list[str] | None = None


class AgentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    description: str
    provider: str
    model: str
    tools: list[str]
    knowledge_file_name: str | None
    created_at: datetime


class RunCreate(BaseModel):
    agent_id: uuid.UUID
    input: str


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent_id: uuid.UUID
    input_message: str
    status: str
    output_text: str | None
    created_at: datetime
    completed_at: datetime | None


class ToolOut(BaseModel):
    id: str
    name: str
    description: str
