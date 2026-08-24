import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class AgentCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    role: str = Field(min_length=1)
    provider: str = "anthropic"
    model: str = Field(min_length=1)
    skills: list[str] = []
    tools: list[str] = []


class AgentUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    role: str | None = Field(default=None, min_length=1)
    provider: str | None = None
    model: str | None = Field(default=None, min_length=1)
    skills: list[str] | None = None
    tools: list[str] | None = None


class AgentOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    name: str
    role: str
    provider: str
    model: str
    skills: list[str]
    tools: list[str]
    knowledge_file_name: str | None
    created_at: datetime


class MessageOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    role: str
    content: str
    tool_name: str | None
    seq: int
    created_at: datetime


class ConversationCreate(BaseModel):
    agent_id: uuid.UUID
    title: str | None = None


class ConversationOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent_id: uuid.UUID
    title: str
    created_at: datetime
    last_message_at: datetime


class ConversationDetail(ConversationOut):
    messages: list[MessageOut] = []


class SendMessage(BaseModel):
    content: str = Field(min_length=1)


class TurnOut(BaseModel):
    """What the caller gets back from posting a message: the persisted user turn,
    the assistant reply, and any tool calls made along the way."""

    user_message: MessageOut
    assistant_message: MessageOut
    tool_messages: list[MessageOut] = []
    conversation_title: str


class RunOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    agent_id: uuid.UUID
    conversation_id: uuid.UUID | None
    input_message: str
    status: str
    output_text: str | None
    created_at: datetime
    completed_at: datetime | None


class ScheduledTaskCreate(BaseModel):
    conversation_id: uuid.UUID
    agent_id: uuid.UUID
    task_type: str = Field(min_length=1, max_length=50)
    temporal_schedule_id: str = Field(min_length=1, max_length=200)
    params: dict = {}


class ScheduledTaskOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    conversation_id: uuid.UUID
    agent_id: uuid.UUID
    task_type: str
    temporal_schedule_id: str
    params: dict
    status: str
    created_at: datetime


class CatalogItem(BaseModel):
    id: str
    name: str
    description: str


class ToolItem(CatalogItem):
    enabled: bool
