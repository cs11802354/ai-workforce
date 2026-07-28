from datetime import timedelta

from temporalio import workflow

with workflow.unsafe.imports_passed_through():
    from activities import invoke_agent_activity


@workflow.defn(name="AgentRunWorkflow")
class AgentRunWorkflow:
    @workflow.run
    async def run(self, agent_snapshot: dict, input_message: str) -> str:
        return await workflow.execute_activity(
            invoke_agent_activity,
            args=[agent_snapshot, input_message],
            start_to_close_timeout=timedelta(minutes=2),
        )
