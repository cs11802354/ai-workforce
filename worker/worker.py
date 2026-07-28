import asyncio
import os

from temporalio.client import Client
from temporalio.worker import Worker

from activities import invoke_agent_activity
from workflows import AgentRunWorkflow

TEMPORAL_HOST = os.environ.get("TEMPORAL_HOST", "localhost:7233")
TASK_QUEUE = os.environ.get("TEMPORAL_TASK_QUEUE", "agent-tasks")


async def main():
    client = await Client.connect(TEMPORAL_HOST)
    worker = Worker(
        client,
        task_queue=TASK_QUEUE,
        workflows=[AgentRunWorkflow],
        activities=[invoke_agent_activity],
    )
    print(f"Worker started, connected to {TEMPORAL_HOST}, task queue '{TASK_QUEUE}'")
    await worker.run()


if __name__ == "__main__":
    asyncio.run(main())
