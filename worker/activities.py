"""Activities for the agent conversation workflow.

`invoke_model_activity` is one master-task LLM call. `execute_tool_activity` is
the tool dispatch — every finance adapter is currently a stub, but the call path
around it is real, so connecting a live terminal means editing one function here.
"""

from temporalio import activity

from catalog import SKILL_PROMPTS, TOOL_DISPLAY_NAMES, anthropic_tools, openai_tools

MAX_TOKENS = 16000


def build_system_prompt(agent: dict) -> str:
    """Fold the agent's role and its skills into the run-state context the model
    reasons from. Skills are prose, not callable — they inform which *tool* the
    model reaches for."""
    parts = [
        f"You are '{agent['name']}'.",
        agent.get("role") or "No further role description was provided.",
    ]

    skills = agent.get("skills") or []
    skill_lines = [SKILL_PROMPTS[s] for s in skills if s in SKILL_PROMPTS]
    if skill_lines:
        parts.append("Your capabilities:\n" + "\n".join(f"- {line}" for line in skill_lines))

    tools = agent.get("tools") or []
    if tools:
        names = ", ".join(TOOL_DISPLAY_NAMES.get(t, t) for t in tools)
        parts.append(
            f"You have access to these data tools: {names}. Call them when the "
            "question needs data you do not already have. If a tool reports that "
            "it is not connected, say so plainly rather than inventing a number."
        )

    return "\n\n".join(parts)


@activity.defn
async def invoke_model_activity(agent: dict, messages: list[dict]) -> dict:
    """One LLM call. Returns a normalized turn result:

        {stop_reason, text, tool_calls: [{id, name, input}], assistant_message}

    `assistant_message` is provider-native and gets appended to the conversation
    history verbatim so multi-turn context (including tool_use blocks) survives.
    """
    if agent.get("provider") == "openai":
        return await _call_openai(agent, messages)
    return await _call_anthropic(agent, messages)


async def _call_anthropic(agent: dict, messages: list[dict]) -> dict:
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic()
    kwargs: dict = {
        # No `thinking` param: the model list spans Opus 5 / Sonnet 5 (adaptive
        # on by default) and Haiku 4.5 (older budget_tokens style). Omitting it
        # lets each model use its own default instead of 400-ing on the wrong one.
        "model": agent.get("model", "claude-opus-5"),
        "max_tokens": MAX_TOKENS,
        "system": build_system_prompt(agent),
        "messages": messages,
    }
    tools = anthropic_tools(agent.get("tools") or [])
    if tools:
        kwargs["tools"] = tools

    response = await client.messages.create(**kwargs)

    # Guard before touching content — a refusal can carry an empty content list.
    if response.stop_reason == "refusal":
        return {
            "stop_reason": "refusal",
            "text": "This request was declined by the model's safety system.",
            "tool_calls": [],
            "assistant_message": None,
        }

    text = "".join(b.text for b in response.content if b.type == "text")
    tool_calls = [
        {"id": b.id, "name": b.name, "input": b.input}
        for b in response.content
        if b.type == "tool_use"
    ]

    return {
        "stop_reason": response.stop_reason,
        "text": text,
        "tool_calls": tool_calls,
        "assistant_message": {
            "role": "assistant",
            "content": [b.model_dump(exclude_none=True) for b in response.content],
        },
    }


async def _call_openai(agent: dict, messages: list[dict]) -> dict:
    from openai import AsyncOpenAI

    client = AsyncOpenAI()
    kwargs: dict = {
        "model": agent.get("model", "gpt-5"),
        "messages": [{"role": "system", "content": build_system_prompt(agent)}, *messages],
    }
    tools = openai_tools(agent.get("tools") or [])
    if tools:
        kwargs["tools"] = tools

    response = await client.chat.completions.create(**kwargs)
    msg = response.choices[0].message

    import json

    tool_calls = [
        {"id": tc.id, "name": tc.function.name, "input": json.loads(tc.function.arguments or "{}")}
        for tc in (msg.tool_calls or [])
    ]

    assistant_message: dict = {"role": "assistant", "content": msg.content or ""}
    if msg.tool_calls:
        assistant_message["tool_calls"] = [
            {
                "id": tc.id,
                "type": "function",
                "function": {"name": tc.function.name, "arguments": tc.function.arguments},
            }
            for tc in msg.tool_calls
        ]

    return {
        "stop_reason": "tool_use" if tool_calls else "end_turn",
        "text": msg.content or "",
        "tool_calls": tool_calls,
        "assistant_message": assistant_message,
    }


@activity.defn
async def execute_tool_activity(tool_name: str, tool_input: dict) -> str:
    """Dispatch a tool call.

    Every adapter is a stub today. The important part is that this runs as a real
    Temporal activity with its own retry and timeout policy — swapping a stub for
    a live API client is a local change with no workflow edit.
    """
    display = TOOL_DISPLAY_NAMES.get(tool_name, tool_name)
    query = tool_input.get("query", "")
    activity.logger.info("tool call: %s(%r)", tool_name, query)
    return (
        f"{display} is not connected in this demo environment, so no live data "
        f"was returned for: {query!r}. Tell the user the data source is not "
        f"connected yet rather than estimating a value."
    )
