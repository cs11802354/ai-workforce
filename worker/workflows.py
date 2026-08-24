import asyncio
from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from activities import execute_tool_activity, invoke_model_activity

# Stop a model that keeps reaching for tools from spinning the workflow forever.
MAX_TOOL_ITERATIONS = 5
# How long a conversation workflow lingers with no traffic before exiting. The
# next message starts it again under the same workflow_id (new run_id).
IDLE_TIMEOUT = timedelta(minutes=30)
# Roll over to a fresh run before the event history gets unwieldy.
CONTINUE_AS_NEW_AFTER = 200


@workflow.defn(name="AgentConversationWorkflow")
class AgentConversationWorkflow:
    """One long-lived workflow per conversation.

    conversation_id -> a stable workflow_id. Each user message arrives as an
    Update, so the caller gets the assistant's reply back from the same call that
    delivered the message. Between turns the workflow just waits; it exits after
    IDLE_TIMEOUT and is revived by the next Update-with-Start.
    """

    def __init__(self) -> None:
        self._messages: list[dict] = []
        self._agent: dict = {}
        self._conversation_id = ""
        self._busy = False
        self._ready = False

    @workflow.run
    async def run(
        self, agent: dict, history: list[dict] | None = None, conversation_id: str = ""
    ) -> list[dict]:
        self._agent = agent
        self._messages = list(history or [])
        self._conversation_id = conversation_id
        self._ready = True

        while True:
            try:
                await workflow.wait_condition(
                    lambda: len(self._messages) >= CONTINUE_AS_NEW_AFTER and not self._busy,
                    timeout=IDLE_TIMEOUT,
                )
            except asyncio.TimeoutError:
                # Nobody spoke for a while. Don't exit out from under an
                # in-flight turn — loop and wait again if one is running.
                if self._busy:
                    continue
                return self._messages

            workflow.continue_as_new(args=[self._agent, self._messages, self._conversation_id])

    @workflow.update(name="send_message")
    async def send_message(self, text: str) -> dict:
        """Run one turn: trigger -> master-task LLM -> tools -> rendered reply."""
        # An update can be delivered before the main workflow method body has
        # run — Update-with-Start does exactly that — so the agent snapshot may
        # not be assigned yet. Without this guard the first turn of every new
        # conversation ships an empty agent dict to the model activity.
        await workflow.wait_condition(lambda: self._ready)
        self._busy = True
        try:
            return await self._run_turn(text)
        finally:
            self._busy = False

    async def _run_turn(self, text: str) -> dict:
        self._messages.append({"role": "user", "content": text})

        tool_trace: list[dict] = []
        final_text = ""
        hit_limit = True

        for _ in range(MAX_TOOL_ITERATIONS):
            result = await workflow.execute_activity(
                invoke_model_activity,
                args=[self._agent, self._messages],
                start_to_close_timeout=timedelta(minutes=5),
                retry_policy=RetryPolicy(maximum_attempts=3),
            )

            if result["assistant_message"]:
                self._messages.append(result["assistant_message"])

            final_text = result["text"]

            if result["stop_reason"] == "refusal":
                return {"text": final_text, "tool_calls": tool_trace, "refused": True}

            calls = result["tool_calls"]
            if not calls:
                hit_limit = False
                break

            # Execute every requested tool, then hand all results back at once —
            # Anthropic rejects the follow-up if any tool_use id lacks a result.
            results = []
            for call in calls:
                output = await workflow.execute_activity(
                    execute_tool_activity,
                    args=[
                        call["name"],
                        call["input"],
                        self._conversation_id,
                        self._agent.get("id", ""),
                    ],
                    start_to_close_timeout=timedelta(minutes=2),
                    retry_policy=RetryPolicy(maximum_attempts=2),
                )
                results.append((call, output))
                tool_trace.append(
                    {"name": call["name"], "input": call["input"], "output": output}
                )

            self._messages.extend(self._tool_result_messages(results))

        if hit_limit and not final_text:
            final_text = (
                "I reached the tool-call limit for this turn without arriving at "
                "an answer. Try narrowing the question."
            )

        return {"text": final_text, "tool_calls": tool_trace, "refused": False}

    def _tool_result_messages(self, results: list[tuple[dict, str]]) -> list[dict]:
        """Provider-native tool results. Pure dict work, so it stays deterministic
        and is safe to do inside the workflow."""
        if self._agent.get("provider") == "openai":
            # OpenAI wants one message per call.
            return [
                {"role": "tool", "tool_call_id": call["id"], "content": output}
                for call, output in results
            ]
        # Anthropic wants every result in a single user message.
        return [
            {
                "role": "user",
                "content": [
                    {"type": "tool_result", "tool_use_id": call["id"], "content": output}
                    for call, output in results
                ],
            }
        ]

    @workflow.query
    def message_count(self) -> int:
        return len(self._messages)
