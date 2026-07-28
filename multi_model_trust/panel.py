"""Panel invocation: ask one model for a structured, cited answer.

Each panel member is called independently with the same query and the same
corpus. They never see each other's output — the whole value of the panel comes
from the answers being independent, and showing model B what model A said would
turn disagreement into anchoring.

Failure handling is the load-bearing part of this module. A panel member can
fail by timing out, by returning prose where JSON was asked for, or by returning
JSON that does not fit the schema. All three become a `ModelFailure` that
travels with the report rather than an exception that sinks the query. An answer
built from two of three models is a legitimate answer; it is just not the same
answer as one built from three, and the reader is told which they have.
"""

from __future__ import annotations

import asyncio
import json
import os
import time

from .schemas import ModelFailure, ModelResponse, PanelMember, parse_model_response

MAX_TOKENS = 4000
TIMEOUT_SECONDS = 90

# Role briefs. Same model, different starting position — a cheap way to make a
# panel argue from more than one angle, which is where useful disagreement comes
# from. A panel that only ever agrees is not measuring anything.
ROLE_BRIEFS = {
    "generalist": "Answer directly and stay within what the evidence supports.",
    "finance": (
        "You are a buy-side analyst. Separate reported figures from your own "
        "inference, and treat guidance as a claim by management, not as fact."
    ),
    "legal": (
        "You are a commercial lawyer. Flag where an answer depends on "
        "jurisdiction or on contract terms you have not been shown."
    ),
    "medical": (
        "You are a clinical reviewer. Distinguish population-level evidence "
        "from individual recommendation, and never present one as the other."
    ),
    "technical": (
        "You are a staff engineer. Distinguish what the specification "
        "guarantees from what a typical implementation happens to do."
    ),
}

_SCHEMA_BRIEF = """Reply with a single JSON object and nothing else:

{
  "answer": "<two sentences at most>",
  "claims": [
    {
      "id": "<short unique id, e.g. k1>",
      "text": "<one self-contained factual assertion>",
      "confidence": <0.0-1.0>,
      "evidence": [{"source_id": "<corpus id or null>", "quote": "<verbatim span>"}]
    }
  ],
  "assumptions": ["<assumption you had to make>"],
  "unknowns": ["<what you could not determine>"]
}

Rules:
- Each claim must stand alone. Do not write "it grew 12%" — write what grew.
- Split compound statements into separate claims.
- confidence is your own calibrated belief, not a rhetorical flourish.
- Do not invent a source_id. If the corpus does not support a claim, use null.
- Quote spans verbatim from the corpus. A paraphrase in "quote" is a failure.
- Listing something in "unknowns" is a better answer than guessing."""


def build_prompt(query: str, corpus: dict[str, str], role: str) -> tuple[str, str]:
    """Return (system, user). The corpus goes in the user turn so it is clearly
    data rather than instruction — it comes from the caller and must not be able
    to redirect the model's behaviour."""
    brief = ROLE_BRIEFS.get(role, ROLE_BRIEFS["generalist"])
    system = f"{brief}\n\n{_SCHEMA_BRIEF}"

    if corpus:
        sources = "\n".join(f"[{sid}] {text}" for sid, text in sorted(corpus.items()))
        user = (
            f"Sources:\n{sources}\n\n"
            f"Question: {query}\n\n"
            "Cite only from the sources above. If they do not answer the "
            "question, say so in unknowns rather than filling the gap."
        )
    else:
        user = (
            f"Question: {query}\n\n"
            "No corpus was supplied, so set every source_id to null and put "
            "your grounds in the quote field."
        )
    return system, user


# --------------------------------------------------------------------------
# Provider calls
# --------------------------------------------------------------------------


async def _call_anthropic(model: str, system: str, user: str) -> str:
    from anthropic import AsyncAnthropic

    client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    # No `thinking` parameter: the tier catalogue spans models with adaptive
    # thinking and models on the older budget_tokens style, and passing the
    # wrong shape is a 400. Omitting it lets each model use its own default.
    message = await client.messages.create(
        model=model,
        max_tokens=MAX_TOKENS,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    if message.stop_reason == "refusal":
        raise ValueError("model declined to answer")
    return "".join(block.text for block in message.content if block.type == "text")


async def _call_openai(model: str, system: str, user: str) -> str:
    from openai import AsyncOpenAI

    client = AsyncOpenAI(api_key=os.environ["OPENAI_API_KEY"])
    # Temperature is left at the default: the reasoning models reject anything
    # else, and sampling noise is not the diversity this panel is after — the
    # diversity comes from using different models.
    completion = await client.chat.completions.create(
        model=model,
        max_completion_tokens=MAX_TOKENS,
        response_format={"type": "json_object"},
        messages=[
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    )
    return completion.choices[0].message.content or ""


_PROVIDERS = {"anthropic": _call_anthropic, "openai": _call_openai}


async def complete(provider: str, model: str, system: str, user: str) -> str:
    """One raw completion. Shared with `synthesize`, which drives the same two
    providers for the normalizer and the cross-examiner."""
    caller = _PROVIDERS.get(provider)
    if caller is None:
        raise ValueError(f"unknown provider {provider!r}")
    return await asyncio.wait_for(caller(model, system, user), timeout=TIMEOUT_SECONDS)


async def invoke_member(
    member: PanelMember, query: str, corpus: dict[str, str]
) -> tuple[ModelResponse | None, ModelFailure | None]:
    """Call one panel member. Returns exactly one of (response, failure)."""
    system, user = build_prompt(query, corpus, member.role)
    caller = _PROVIDERS.get(member.provider)
    if caller is None:
        return None, ModelFailure(
            model=member.model, reason=f"unknown provider {member.provider!r}", stage="invoke"
        )

    started = time.monotonic()
    try:
        raw = await asyncio.wait_for(
            caller(member.model, system, user), timeout=TIMEOUT_SECONDS
        )
    except asyncio.TimeoutError:
        return None, ModelFailure(
            model=member.model, reason=f"no response within {TIMEOUT_SECONDS}s", stage="invoke"
        )
    except Exception as exc:
        return None, ModelFailure(
            model=member.model, reason=_reason(exc), stage="invoke"
        )

    elapsed = int((time.monotonic() - started) * 1000)
    try:
        response = parse_model_response(member.model, raw, elapsed)
    except ValueError as exc:
        return None, ModelFailure(model=member.model, reason=str(exc), stage="parse")

    if not response.claims:
        # An answer with no claims cannot be cross-checked against anything, so
        # it cannot participate in consensus. Reporting it as a failure is more
        # honest than counting it as a silent agreement.
        return None, ModelFailure(
            model=member.model, reason="returned no claims", stage="validate"
        )
    return response, None


def _reason(exc: Exception) -> str:
    """Provider SDKs wrap the useful message a couple of layers down; an
    unhelpful 'APIStatusError' in the report helps nobody debug their key."""
    text = str(exc).strip() or exc.__class__.__name__
    return text[:300]


async def run_panel(
    panel: list[PanelMember], query: str, corpus: dict[str, str]
) -> tuple[list[ModelResponse], list[ModelFailure]]:
    """Fan out to every member concurrently and collect both outcomes."""
    results = await asyncio.gather(
        *(invoke_member(m, query, corpus) for m in panel), return_exceptions=True
    )

    responses: list[ModelResponse] = []
    failures: list[ModelFailure] = []
    for member, result in zip(panel, results):
        if isinstance(result, BaseException):
            failures.append(
                ModelFailure(model=member.model, reason=_reason(result), stage="invoke")
            )
            continue
        response, failure = result
        if response is not None:
            responses.append(response)
        if failure is not None:
            failures.append(failure)

    # Stable order regardless of which model happened to finish first, so two
    # runs over the same panel produce the same report.
    responses.sort(key=lambda r: r.model)
    failures.sort(key=lambda f: f.model)
    return responses, failures


def responses_as_payload(responses: list[ModelResponse]) -> str:
    """Compact rendering of the panel for the normalizer prompt."""
    return json.dumps(
        [
            {
                "model": r.model,
                "claims": [{"id": c.id, "text": c.text} for c in r.claims],
            }
            for r in responses
        ],
        indent=1,
    )
