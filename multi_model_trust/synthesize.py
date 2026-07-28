"""The three model-driven stages: normalize, cross-examine, synthesize.

Each function here is a thin, well-typed wrapper over one LLM call, and each
returns plain data. The pipeline logic that consumes them lives in
`consensus.py` and stays pure. That separation is what makes the eval able to
replay recorded outputs of these three calls and exercise the rest of the system
without a network.

Why the normalizer is a model and not a distance function: grouping claims by
meaning is a judgment task. See the measurement write-up at the top of
`consensus.py` — cosine similarity over sentence embeddings was tried first and
does not separate this problem at any threshold.
"""

from __future__ import annotations

import json
import os

from .panel import complete
from .schemas import (
    ClaimCluster,
    ModelFailure,
    ModelResponse,
    Stance,
    TrustStatus,
    extract_json,
)

# Cross-examination is capped rather than run to convergence. Each round is a
# model call on the critical path of a user-facing request, and in practice a
# conflict that survives two passes is a real disagreement rather than a
# wording artefact — more rounds buy latency, not resolution.
MAX_CROSS_EXAMINE = 3


def judge_model() -> tuple[str, str]:
    """(provider, model) for the normalizer, cross-examiner, and synthesizer.

    Defaults to the cheap tier: these calls are structural bookkeeping over text
    the panel already produced, not the reasoning the panel was hired for.
    """
    override = os.environ.get("TRUST_JUDGE_MODEL")
    if override and ":" in override:
        provider, _, model = override.partition(":")
        return provider, model
    if os.environ.get("ANTHROPIC_API_KEY"):
        return "anthropic", "claude-haiku-4-5"
    return "openai", "gpt-5-mini"


# --------------------------------------------------------------------------
# Stage 1 — normalize claims into groups, with a stance per model
# --------------------------------------------------------------------------

_NORMALIZE_SYSTEM = """You compare claims made independently by different models about the same question.

Group claims that make the SAME assertion about the SAME thing, then mark each
member's stance toward the group's canonical statement.

Stances:
- supports    : asserts the canonical statement
- rejects     : asserts something that cannot be true at the same time
- conditional : agrees only under a caveat the others do not state

Grouping rules that matter:
- Two claims that assert DIFFERENT VALUES for the same quantity belong in the
  SAME group, with one marked "rejects". "Revenue was $48M" and "revenue was
  $42M" are a disagreement about one fact, not two unrelated facts.
- Two claims about DIFFERENT attributes belong in DIFFERENT groups, even when
  they share wording. Revenue, margin, and headcount are three groups.
- A claim only one model made is a group of one. Never drop it.
- Never put two claims from the same model in one group.

Reply with a single JSON object and nothing else:

{"clusters": [{"canonical": "<neutral statement of the shared claim>",
               "members": [{"claim_id": "<id>", "stance": "supports"}]}]}

Every claim id given to you must appear exactly once."""


async def normalize_claims(responses: list[ModelResponse]) -> list[dict]:
    """Group claims across models and assign stances. Returns the raw grouping.

    Raises ValueError if the model's output is unusable — the caller falls back
    to `consensus.fallback_grouping`, which finds less but invents nothing.
    """
    payload = json.dumps(
        [
            {"model": r.model, "claims": [{"id": c.id, "text": c.text} for c in r.claims]}
            for r in responses
        ],
        indent=1,
    )
    provider, model = judge_model()
    raw = await complete(provider, model, _NORMALIZE_SYSTEM, f"Claims:\n{payload}")

    parsed = extract_json(raw)
    clusters = parsed.get("clusters")
    if not isinstance(clusters, list) or not clusters:
        raise ValueError("normalizer returned no clusters")
    return [c for c in clusters if isinstance(c, dict)]


# --------------------------------------------------------------------------
# Stage 2 — cross-examine the conflicts
# --------------------------------------------------------------------------

_CROSS_EXAMINE_SYSTEM = """Two or more models disagree about one claim. Decide what the evidence supports.

You are not casting a tie-break vote. Check each side against the quoted
evidence and the corpus. If the evidence settles it, correct the stances. If it
does not, say so — an unresolved conflict reported honestly is a better outcome
than a confident wrong resolution.

Reply with a single JSON object and nothing else:

{"resolved": true|false,
 "finding": "<one sentence on what the evidence shows>",
 "stances": {"<model name>": "supports"|"rejects"|"conditional"}}

Only name models that already made a claim here. If "resolved" is false, return
the stances unchanged."""


async def cross_examine(
    query: str, cluster: ClaimCluster, corpus: dict[str, str]
) -> tuple[dict[str, Stance], str]:
    """Re-adjudicate one conflicting cluster. Returns (stances, finding).

    Any failure returns no stance changes, leaving the cluster in conflict. That
    is the safe direction: an unresolved conflict is shown to the user, whereas
    a wrongly resolved one disappears from the report.
    """
    positions = "\n".join(
        f"- {model} claims: {claim_id}" for model, claim_id in sorted(cluster.member_claims.items())
    )
    evidence = "\n".join(
        f"- [{e.source_id or 'no source'}] \"{e.quote}\"" for e in cluster.evidence
    ) or "- none offered"
    sources = (
        "\n".join(f"[{sid}] {text}" for sid, text in sorted(corpus.items()))
        if corpus
        else "none supplied"
    )
    stances = "\n".join(f"- {m}: {s.value}" for m, s in sorted(cluster.stances.items()) if m in cluster.member_claims)

    user = (
        f"Question: {query}\n\n"
        f"Disputed claim: {cluster.canonical_text}\n\n"
        f"Current stances:\n{stances}\n\n"
        f"Positions:\n{positions}\n\n"
        f"Evidence offered:\n{evidence}\n\n"
        f"Corpus:\n{sources}"
    )

    provider, model = judge_model()
    try:
        raw = await complete(provider, model, _CROSS_EXAMINE_SYSTEM, user)
        parsed = extract_json(raw)
    except Exception as exc:
        return {}, f"cross-examination failed: {str(exc)[:120]}"

    if not parsed.get("resolved"):
        return {}, str(parsed.get("finding") or "evidence does not settle this")

    updated: dict[str, Stance] = {}
    for model_name, stance in (parsed.get("stances") or {}).items():
        if model_name not in cluster.member_claims:
            continue  # the judge does not get to invent votes
        try:
            updated[model_name] = Stance(str(stance).strip().lower())
        except ValueError:
            continue
    return updated, str(parsed.get("finding") or "")


# --------------------------------------------------------------------------
# Stage 3 — write the answer
# --------------------------------------------------------------------------

_SYNTHESIZE_SYSTEM = """Write the answer a reader should act on, given what a panel of models agreed and disagreed about.

Rules:
- Lead with the answer. First sentence, no preamble.
- Three sentences at most.
- If models CONTRADICTED each other, say what is disputed in the answer itself.
  Do not bury it — the reader is about to see the disagreement listed below.
- UNCONFIRMED is not disputed. Those claims were raised by one model and
  contradicted by nobody, because nobody else addressed them. Never describe
  them as a disagreement, and never state them as established fact. If one is
  worth mentioning at all, attribute it: "one model also reports ...".
- Do not add facts. You may only use what the panel supplied.
- Do not describe the process. The reader can see the panel; they want the answer.

Reply with plain text, no JSON, no markdown headings."""


async def synthesize_answer(
    query: str,
    agreements: list[ClaimCluster],
    disagreements: list[ClaimCluster],
    unconfirmed: list[ClaimCluster],
    status: TrustStatus,
    failures: list[ModelFailure],
) -> str:
    agreed = "\n".join(
        f"- {c.canonical_text} (backed by {len(c.supporting_models)} models,"
        f" citation {c.citation_status.value})"
        for c in agreements
    ) or "- nothing was corroborated by more than one model"

    disputed = "\n".join(
        f"- {c.canonical_text} [{c.verdict.value}]"
        + (f" — {', '.join(c.rejecting_models)} disagree" if c.rejecting_models else "")
        for c in disagreements
    ) or "- nothing was contradicted"

    lone = "\n".join(
        f"- {c.canonical_text} (only {', '.join(c.supporting_models)} raised this)"
        for c in unconfirmed
    ) or "- nothing"

    note = (
        f"\n{len(failures)} panel model(s) failed to answer."
        if failures
        else ""
    )

    user = (
        f"Question: {query}\n\n"
        f"Trust status: {status.value}\n\n"
        f"Agreed:\n{agreed}\n\n"
        f"Contradicted:\n{disputed}\n\n"
        f"Unconfirmed (one model only, nobody disagreed):\n{lone}{note}"
    )

    provider, model = judge_model()
    try:
        text = await complete(provider, model, _SYNTHESIZE_SYSTEM, user)
    except Exception as exc:
        return _fallback_answer(agreements, disagreements, status, exc)
    return text.strip() or _fallback_answer(agreements, disagreements, status, None)


def _fallback_answer(
    agreements: list[ClaimCluster],
    disagreements: list[ClaimCluster],
    status: TrustStatus,
    exc: Exception | None,
) -> str:
    """If the synthesizer call fails we still have the matrix, which is the part
    that took real work. Render it plainly rather than returning an error page —
    a terse answer beats no answer."""
    lead = agreements[0].canonical_text if agreements else "The panel did not corroborate any claim."
    conflicts = [c for c in disagreements if c.rejecting_models]
    tail = (
        f" The panel disagreed on {len(conflicts)} point(s), including: "
        f"{conflicts[0].canonical_text}"
        if conflicts
        else ""
    )
    reason = f" (summary unavailable: {str(exc)[:80]})" if exc else ""
    return f"{lead}{tail} Trust status: {status.value}.{reason}"
