from temporalio import activity


def _build_system_prompt(agent_snapshot: dict) -> str:
    lines = [
        f"You are '{agent_snapshot['name']}'.",
        agent_snapshot.get("description") or "No further role description was provided.",
    ]
    tools = agent_snapshot.get("tools") or []
    if tools:
        lines.append(
            "You have been configured with these tools (not actually wired up in this "
            f"demo, just mentioned for context): {', '.join(tools)}."
        )
    return "\n\n".join(lines)


@activity.defn
async def invoke_agent_activity(agent_snapshot: dict, input_message: str) -> str:
    provider = agent_snapshot.get("provider", "anthropic")
    model = agent_snapshot.get("model", "claude-sonnet-5")
    system_prompt = _build_system_prompt(agent_snapshot)

    if provider == "openai":
        return await _call_openai(model, system_prompt, input_message)
    return await _call_anthropic(model, system_prompt, input_message)


async def _call_anthropic(model: str, system_prompt: str, input_message: str) -> str:
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic()
    response = await client.messages.create(
        model=model,
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": input_message}],
    )
    return "".join(block.text for block in response.content if block.type == "text")


async def _call_openai(model: str, system_prompt: str, input_message: str) -> str:
    from openai import AsyncOpenAI

    client = AsyncOpenAI()
    response = await client.chat.completions.create(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": input_message},
        ],
    )
    return response.choices[0].message.content or ""
