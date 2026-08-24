import asyncio
import os

from temporalio.client import Client
from temporalio.worker import Worker

from activities import execute_tool_activity, invoke_model_activity
from digest_activities import (
    fetch_articles_activity,
    send_digest_email_activity,
    summarize_digest_activity,
)
from digest_workflow import DailyDigestWorkflow
from workflows import AgentConversationWorkflow

from multi_model_trust.workflow import TRUST_ACTIVITIES, TrustPanelWorkflow

TEMPORAL_HOST = os.environ.get("TEMPORAL_HOST", "localhost:7233")
TASK_QUEUE = os.environ.get("TEMPORAL_TASK_QUEUE", "agent-tasks")


async def main():
    client = await Client.connect(TEMPORAL_HOST)
    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[AgentConversationWorkflow, TrustPanelWorkflow, DailyDigestWorkflow],
        activities=[
            invoke_model_activity,
            execute_tool_activity,
            fetch_articles_activity,
            summarize_digest_activity,
            send_digest_email_activity,
            *TRUST_ACTIVITIES,
        ],
    )
    print(f"Worker started, connected to {TEMPORAL_HOST}, task queue '{TASK_QUEUE}'")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
