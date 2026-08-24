"""Adapter for the schedule_task tool.

Creates/updates a Temporal Schedule for a recurring task, then records it
against the conversation that created it via a backend-internal endpoint.
Only 'daily_digest' is supported — this is deliberately not a generic task
scheduler yet.
"""

from __future__ import annotations

import os

import httpx
from temporalio.client import (
    Client,
    Schedule,
    ScheduleActionStartWorkflow,
    ScheduleSpec,
    ScheduleUpdate,
)

from digest_workflow import DailyDigestWorkflow

TEMPORAL_HOST = os.environ.get("TEMPORAL_HOST", "localhost:7233")
TASK_QUEUE = os.environ.get("TEMPORAL_TASK_QUEUE", "agent-tasks")
BACKEND_INTERNAL_URL = os.environ.get("BACKEND_INTERNAL_URL", "http://backend:8000")
INTERNAL_API_KEY = os.environ.get("INTERNAL_API_KEY", "")

SUPPORTED_TASK_TYPES = {"daily_digest"}


async def create_scheduled_task(params: dict, conversation_id: str, agent_id: str) -> str:
    task_type = params.get("task_type", "daily_digest")
    if task_type not in SUPPORTED_TASK_TYPES:
        return f"Unsupported task type {task_type!r}. Only 'daily_digest' is supported right now."

    if not conversation_id or not agent_id:
        return "Could not schedule: missing conversation/agent context."

    recipient = params.get("recipient_email")
    if not recipient:
        return "recipient_email is required to schedule a digest."

    time_str = params.get("time", "08:00")
    try:
        hour_str, minute_str = time_str.split(":")
        hour, minute = int(hour_str), int(minute_str)
        if not (0 <= hour < 24 and 0 <= minute < 60):
            raise ValueError
    except ValueError:
        return f"Invalid time {time_str!r} — expected 24h HH:MM, e.g. '08:00'."

    timezone_name = params.get("timezone", "Asia/Kolkata")
    topics = params.get("topics") or None
    cron = f"{minute} {hour} * * *"

    # One schedule per conversation — a second call from the same conversation
    # updates it (e.g. "change my digest time to 7am") instead of creating a
    # duplicate.
    schedule_id = f"digest-{conversation_id}"

    schedule = Schedule(
        action=ScheduleActionStartWorkflow(
            DailyDigestWorkflow.run,
            args=[topics, recipient],
            id=f"{schedule_id}-run",
            task_queue=TASK_QUEUE,
        ),
        spec=ScheduleSpec(cron_expressions=[cron], time_zone_name=timezone_name),
    )

    client = await Client.connect(TEMPORAL_HOST)
    handle = client.get_schedule_handle(schedule_id)
    try:
        await handle.describe()
        await handle.update(lambda _: ScheduleUpdate(schedule=schedule))
    except Exception:
        await client.create_schedule(schedule_id, schedule)

    task_params = {
        "time": time_str,
        "timezone": timezone_name,
        "topics": topics,
        "recipient_email": recipient,
    }
    if BACKEND_INTERNAL_URL and INTERNAL_API_KEY:
        async with httpx.AsyncClient(timeout=10.0) as http:
            resp = await http.post(
                f"{BACKEND_INTERNAL_URL.rstrip('/')}/internal/scheduled-tasks",
                json={
                    "conversation_id": conversation_id,
                    "agent_id": agent_id,
                    "task_type": task_type,
                    "temporal_schedule_id": schedule_id,
                    "params": task_params,
                },
                headers={"X-Internal-Key": INTERNAL_API_KEY},
            )
            resp.raise_for_status()

    return f"Scheduled a daily digest at {time_str} {timezone_name} for {recipient}."
