import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from temporalio.client import WithStartWorkflowOperation
from temporalio.common import WorkflowIDConflictPolicy

from app.config import settings
from app.db import get_db
from app.models import Agent, Conversation, Message, Run
from app.schemas import (
    ConversationCreate,
    ConversationDetail,
    ConversationOut,
    SendMessage,
    TurnOut,
)
from app.temporal_client import get_temporal_client

router = APIRouter()


def _agent_snapshot(agent: Agent) -> dict:
    """Frozen copy of the agent config handed to the workflow, so editing an
    agent mid-conversation doesn't retroactively change an in-flight turn."""
    return {
        "name": agent.name,
        "role": agent.role,
        "provider": agent.provider,
        "model": agent.model,
        "skills": agent.skills or [],
        "tools": agent.tools or [],
    }


@router.get("/conversations", response_model=list[ConversationOut])
def list_conversations(db: Session = Depends(get_db)):
    return db.query(Conversation).order_by(Conversation.last_message_at.desc()).all()


@router.post("/conversations", response_model=ConversationOut, status_code=201)
def create_conversation(payload: ConversationCreate, db: Session = Depends(get_db)):
    agent = db.get(Agent, payload.agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")

    conversation = Conversation(
        agent_id=agent.id,
        title=payload.title or "New chat",
        temporal_workflow_id="",  # set below, once we have the id
    )
    db.add(conversation)
    db.flush()
    conversation.temporal_workflow_id = f"conv-{conversation.id}"
    db.commit()
    db.refresh(conversation)
    return conversation


@router.get("/conversations/{conversation_id}", response_model=ConversationDetail)
def get_conversation(conversation_id: uuid.UUID, db: Session = Depends(get_db)):
    conversation = db.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(404, "Conversation not found")
    return conversation


@router.delete("/conversations/{conversation_id}", status_code=204)
async def delete_conversation(conversation_id: uuid.UUID, db: Session = Depends(get_db)):
    conversation = db.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(404, "Conversation not found")

    # Best effort: the workflow may already have idled out.
    try:
        client = await get_temporal_client()
        handle = client.get_workflow_handle(conversation.temporal_workflow_id)
        await handle.terminate("conversation deleted")
    except Exception:
        pass

    db.delete(conversation)
    db.commit()


@router.post("/conversations/{conversation_id}/messages", response_model=TurnOut)
async def send_message(
    conversation_id: uuid.UUID,
    payload: SendMessage,
    db: Session = Depends(get_db),
):
    """One turn of the conversation.

    Update-with-Start does start-if-needed plus run-the-turn in a single call, so
    a conversation whose workflow idled out simply revives under the same
    workflow_id rather than needing a separate start.
    """
    conversation = db.get(Conversation, conversation_id)
    if not conversation:
        raise HTTPException(404, "Conversation not found")
    agent = db.get(Agent, conversation.agent_id)
    if not agent:
        raise HTTPException(404, "Agent not found")

    next_seq = (
        db.query(Message).filter(Message.conversation_id == conversation.id).count()
    )

    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=payload.content,
        seq=next_seq,
    )
    db.add(user_message)

    run = Run(
        agent_id=agent.id,
        conversation_id=conversation.id,
        input_message=payload.content,
        status="running",
        temporal_workflow_id=conversation.temporal_workflow_id,
        temporal_run_id="",
    )
    db.add(run)
    db.commit()
    db.refresh(user_message)
    db.refresh(run)

    client = await get_temporal_client()
    start_op = WithStartWorkflowOperation(
        "AgentConversationWorkflow",
        args=[_agent_snapshot(agent), []],
        id=conversation.temporal_workflow_id,
        task_queue=settings.temporal_task_queue,
        id_conflict_policy=WorkflowIDConflictPolicy.USE_EXISTING,
    )

    try:
        result = await client.execute_update_with_start_workflow(
            "send_message",
            payload.content,
            start_workflow_operation=start_op,
        )
    except Exception as exc:
        run.status = "failed"
        run.completed_at = datetime.now(timezone.utc)
        # Drop the user turn so the transcript matches what the client shows
        # after a failure (it clears the bubble and restores the draft). The run
        # row stays — a failed execution still belongs in the log.
        db.delete(user_message)
        db.commit()
        # A failed update wraps the real activity error in `cause`; without
        # unwrapping it the UI only ever sees "Workflow update failed".
        detail = str(getattr(exc, "cause", None) or exc)
        raise HTTPException(502, f"Agent turn failed: {detail}") from exc

    handle = await start_op.workflow_handle()
    run.temporal_run_id = handle.result_run_id or ""

    seq = next_seq + 1
    tool_messages: list[Message] = []
    for call in result.get("tool_calls", []):
        tool_message = Message(
            conversation_id=conversation.id,
            role="tool",
            content=call.get("output", ""),
            tool_name=call.get("name"),
            seq=seq,
        )
        db.add(tool_message)
        tool_messages.append(tool_message)
        seq += 1

    assistant_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=result.get("text") or "",
        seq=seq,
    )
    db.add(assistant_message)

    # We awaited the turn, so we know the outcome now — no need for a later poll
    # to reconcile this run's status.
    run.status = "completed"
    run.output_text = result.get("text") or ""
    run.completed_at = datetime.now(timezone.utc)

    conversation.last_message_at = datetime.now(timezone.utc)
    if conversation.title == "New chat":
        conversation.title = payload.content[:60].strip() or "New chat"

    db.commit()
    db.refresh(assistant_message)
    for message in tool_messages:
        db.refresh(message)

    return TurnOut(
        user_message=user_message,
        assistant_message=assistant_message,
        tool_messages=tool_messages,
        conversation_title=conversation.title,
    )
