"""One-time (or re-run-to-update) registration of the daily digest schedule.

Temporal Schedules aren't declared in code the way workflows/activities are —
they're objects created via the client against the server, so this is a
script you run, not something the worker does on startup. Safe to re-run:
it updates the existing schedule in place rather than erroring.

    python create_digest_schedule.py

Reads TEMPORAL_HOST / TEMPORAL_TASK_QUEUE from the environment, same as the
worker itself.
"""

import asyncio
import os

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
SCHEDULE_ID = "daily-digest"

# 8:00 AM IST daily.
CRON_EXPRESSION = "0 8 * * *"
TIME_ZONE = "Asia/Kolkata"


async def main():
    client = await Client.connect(TEMPORAL_HOST)
    schedule = Schedule(
        action=ScheduleActionStartWorkflow(
            DailyDigestWorkflow.run,
            id="daily-digest-run",
            task_queue=TASK_QUEUE,
        ),
        spec=ScheduleSpec(cron_expressions=[CRON_EXPRESSION], time_zone_name=TIME_ZONE),
    )

    handle = client.get_schedule_handle(SCHEDULE_ID)
    try:
        await handle.describe()
        exists = True
    except Exception:
        exists = False

    if exists:
        await handle.update(lambda _: ScheduleUpdate(schedule=schedule))
        print(f"Updated existing schedule '{SCHEDULE_ID}'.")
    else:
        await client.create_schedule(SCHEDULE_ID, schedule)
        print(f"Created schedule '{SCHEDULE_ID}': {CRON_EXPRESSION} {TIME_ZONE}, task queue '{TASK_QUEUE}'.")


if __name__ == "__main__":
    asyncio.run(main())
