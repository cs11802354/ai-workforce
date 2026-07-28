"""Query classification and panel selection.

Deliberately deterministic — keywords and counts, no model call. Three reasons:
the router runs on every query and an extra LLM round trip before any real work
is latency nobody sees value from; a deterministic router is directly unit
testable, so the eval can assert panel composition; and a router that picks the
panel is the one component whose failure silently degrades everything
downstream, which is a bad place for non-determinism.

Panel composition follows one rule: **never fill a panel from a single
provider** when two are available. Two OpenAI models share training data,
tokenizer, and RLHF lineage, so they fail in correlated ways — they will agree
with each other on a hallucination, and agreement is exactly the signal this
system reports. Cross-provider disagreement is the thing worth measuring.
"""

from __future__ import annotations

import os
import re

from .schemas import PanelMember, RouteDecision

# --------------------------------------------------------------------------
# Model registry
# --------------------------------------------------------------------------

# Two tiers. `economy` is the default and is what the deployed demo runs on:
# panel width matters far more than per-model capability for detecting
# disagreement, and three cheap models surface more real conflict per dollar
# than one expensive one. Set TRUST_PANEL_TIER=standard for the stronger panel.
TIERS: dict[str, dict[str, list[str]]] = {
    "economy": {
        "anthropic": ["claude-haiku-4-5"],
        "openai": ["gpt-5-mini"],
    },
    "standard": {
        "anthropic": ["claude-sonnet-5", "claude-opus-5"],
        "openai": ["gpt-5"],
    },
}

DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "finance": (
        "revenue", "earnings", "ebitda", "margin", "valuation", "stock", "equity",
        "portfolio", "yield", "dividend", "cash flow", "guidance", "quarter",
        "fiscal", "acquisition", "ipo", "balance sheet",
    ),
    "legal": (
        "contract", "clause", "liability", "compliance", "regulation", "statute",
        "gdpr", "indemnity", "jurisdiction", "litigation", "patent",
    ),
    "medical": (
        "dose", "dosage", "symptom", "diagnosis", "treatment", "clinical",
        "patient", "trial", "efficacy", "contraindication",
    ),
    "technical": (
        "latency", "throughput", "kubernetes", "database", "algorithm", "api",
        "deployment", "architecture", "concurrency", "schema",
    ),
}

# Live-data markers. A query about "the current price" cannot be answered from
# weights alone, and the report should say so rather than let three models
# confidently agree on a stale number.
TOOL_MARKERS = (
    "current", "today", "latest", "right now", "real-time", "realtime",
    "this week", "this month", "live", "as of now", "up to date",
)

COMPLEXITY_MARKERS = (
    "compare", "versus", " vs ", "trade-off", "tradeoff", "why", "how would",
    "implications", "forecast", "predict", "should we", "risk", "assess",
    "evaluate", "recommend",
)


def classify(query: str) -> dict:
    """Return the routing object: domain, complexity, requires_tools."""
    lowered = f" {query.lower().strip()} "

    domain = "general"
    best_hits = 0
    for name, keywords in DOMAIN_KEYWORDS.items():
        hits = sum(1 for kw in keywords if kw in lowered)
        # Ties resolve to the earlier domain in the dict, which keeps the result
        # stable across runs; dict order is insertion order in Python 3.7+.
        if hits > best_hits:
            domain, best_hits = name, hits

    words = len(re.findall(r"\w+", query))
    signals = sum(1 for m in COMPLEXITY_MARKERS if m in lowered)
    questions = query.count("?")

    if signals >= 2 or words > 40 or questions > 1:
        complexity = "high"
    elif signals == 1 or words > 15:
        complexity = "medium"
    else:
        complexity = "low"

    return {
        "domain": domain,
        "complexity": complexity,
        "requires_tools": any(m in lowered for m in TOOL_MARKERS),
    }


def available_providers() -> list[str]:
    """Providers we actually hold a key for, in a fixed order.

    Checked at call time rather than import time so the worker picks up a key
    added to the environment without a rebuild.
    """
    providers = []
    if os.environ.get("ANTHROPIC_API_KEY"):
        providers.append("anthropic")
    if os.environ.get("OPENAI_API_KEY"):
        providers.append("openai")
    return providers


def select_panel(classification: dict, tier: str | None = None) -> list[PanelMember]:
    """Pick the panel from the classification.

    Width is driven by complexity: two models for a simple factual lookup, three
    when the question is contestable enough that a tie-break carries meaning. A
    third model on "what was Q4 revenue" mostly buys a third identical answer.
    """
    tier = tier or os.environ.get("TRUST_PANEL_TIER", "economy")
    catalogue = TIERS.get(tier, TIERS["economy"])
    providers = available_providers()

    if not providers:
        return []

    target = 3 if classification["complexity"] == "high" else 2

    # Round-robin across providers first, so a two-model panel is always
    # cross-provider when we hold both keys.
    members: list[PanelMember] = []
    depth = 0
    while len(members) < target:
        added = False
        for provider in providers:
            models = catalogue.get(provider, [])
            if depth < len(models) and len(members) < target:
                members.append(
                    PanelMember(model=models[depth], provider=provider, role="generalist")
                )
                added = True
        if not added:
            break  # catalogue exhausted; a narrower panel is reported as-is
        depth += 1

    # In a specialist domain the last seat gets a domain brief instead of the
    # generalist one. Same model, different instructions — a cheap way to make
    # the panel argue from more than one starting point, which is where useful
    # disagreement comes from.
    if members and classification["domain"] != "general":
        members[-1] = members[-1].model_copy(update={"role": classification["domain"]})

    return members


def route(query: str, tier: str | None = None) -> RouteDecision:
    classification = classify(query)
    panel = select_panel(classification, tier)
    return RouteDecision(
        domain=classification["domain"],
        complexity=classification["complexity"],
        requires_tools=classification["requires_tools"],
        panel=panel,
        rationale=_rationale(classification, panel),
    )


def _rationale(classification: dict, panel: list[PanelMember]) -> str:
    if not panel:
        return "No provider API key is configured, so no panel could be assembled."
    providers = sorted({m.provider for m in panel})
    bits = [
        f"{classification['domain']} query at {classification['complexity']} complexity",
        f"{len(panel)} models across {len(providers)} provider{'s' if len(providers) > 1 else ''}",
    ]
    if classification["requires_tools"]:
        bits.append("asks for live data no model can verify from weights")
    return "; ".join(bits) + "."
