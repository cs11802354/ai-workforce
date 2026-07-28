"""Wire contracts for the trust pipeline.

Every boundary in this system is a place a model can hand back something
malformed, so every boundary has a schema. Nothing reaches the UI that has not
been through `TrustReport.model_validate` — that is the "validate the structured
output before display" requirement, and it is enforced here rather than by
convention.

A note on `parse_model_response`: a model asked for JSON will sometimes wrap it
in prose or a fenced block, and will occasionally emit a claim missing a field.
We salvage what parses and record what did not, because a panel that silently
drops a model is worse than one that reports it as degraded.
"""

from __future__ import annotations

import json
import re
from enum import Enum

from pydantic import BaseModel, Field, ValidationError, field_validator

# --------------------------------------------------------------------------
# What one panel model returns
# --------------------------------------------------------------------------


class Evidence(BaseModel):
    """Support for a single claim.

    `source_id` points into the corpus supplied with the query. It is optional
    because open-ended questions have no corpus — in that case the citation is
    the model's own assertion and is labelled `unverified` downstream rather
    than being passed off as sourced.
    """

    source_id: str | None = None
    quote: str = ""
    url: str | None = None


class Claim(BaseModel):
    id: str
    text: str
    confidence: float = 0.5
    evidence: list[Evidence] = Field(default_factory=list)

    @field_validator("confidence")
    @classmethod
    def _clamp(cls, v: float) -> float:
        # Models routinely emit 0-100 when asked for 0-1, and occasionally
        # something out of range entirely. Clamp rather than reject: a bad
        # confidence number is not worth discarding an otherwise good claim.
        if v > 1.0:
            v = v / 100.0
        return max(0.0, min(1.0, v))


class ModelResponse(BaseModel):
    """One panel member's structured answer."""

    model: str
    answer: str
    claims: list[Claim] = Field(default_factory=list)
    assumptions: list[str] = Field(default_factory=list)
    unknowns: list[str] = Field(default_factory=list)
    latency_ms: int = 0


class ModelFailure(BaseModel):
    """A panel member that did not return usable output.

    Kept in the report rather than swallowed: an answer built from two of three
    models is a different thing from an answer built from three, and the user
    is entitled to know which they are looking at.
    """

    model: str
    reason: str
    stage: str = "invoke"  # invoke | parse | validate


# --------------------------------------------------------------------------
# What the consensus stage produces
# --------------------------------------------------------------------------


class Stance(str, Enum):
    SUPPORTS = "supports"
    REJECTS = "rejects"
    CONDITIONAL = "conditional"
    UNADDRESSED = "unaddressed"


class Verdict(str, Enum):
    UNANIMOUS = "unanimous"          # every responding model supports it
    MAJORITY = "majority"            # supported by most, not contradicted
    CONDITIONAL = "conditional"      # agreement that depends on stated caveats
    MATERIAL_CONFLICT = "conflict"   # at least one model rejects it
    SINGLE_SOURCE = "single_source"  # only one model raised it at all


class CitationStatus(str, Enum):
    VERIFIED = "verified"        # cited span exists and contains the claim
    UNSUPPORTED = "unsupported"  # cited span exists but does not support it
    BROKEN = "broken"            # cited a source_id that is not in the corpus
    UNVERIFIED = "unverified"    # no corpus to check against


class ClaimCluster(BaseModel):
    """One semantic claim, as asserted by one or more panel members."""

    id: str
    canonical_text: str
    stances: dict[str, Stance] = Field(default_factory=dict)  # model -> stance
    member_claims: dict[str, str] = Field(default_factory=dict)  # model -> claim id
    evidence: list[Evidence] = Field(default_factory=list)
    # Best status across this cluster's citations — what the UI badges.
    citation_status: CitationStatus = CitationStatus.UNVERIFIED
    # How many of its citations did NOT check out. Tracked separately because
    # the best-of view hides them, and a fabricated citation sitting next to a
    # good one is the exact thing a reader needs told.
    disputed_citations: int = 0
    confidence: float = 0.0
    verdict: Verdict = Verdict.SINGLE_SOURCE

    @property
    def supporting_models(self) -> list[str]:
        return sorted(m for m, s in self.stances.items() if s == Stance.SUPPORTS)

    @property
    def rejecting_models(self) -> list[str]:
        return sorted(m for m, s in self.stances.items() if s == Stance.REJECTS)


class TrustStatus(str, Enum):
    HIGH = "high"            # unanimous and evidence verified
    MIXED = "mixed"          # agreement, but unverified or only a majority
    CONTESTED = "contested"  # a material conflict survived cross-examination
    DEGRADED = "degraded"    # too few models answered to make the call


# --------------------------------------------------------------------------
# What the UI renders
# --------------------------------------------------------------------------


class PanelMember(BaseModel):
    model: str
    provider: str
    role: str = "generalist"


class RouteDecision(BaseModel):
    domain: str
    complexity: str
    requires_tools: bool
    panel: list[PanelMember]
    rationale: str


class TrustReport(BaseModel):
    """The single object the UI renders. Six sections, matching the six
    questions a reader actually has about a multi-model answer."""

    query: str
    route: RouteDecision
    recommended_answer: str
    trust_status: TrustStatus
    agreements: list[ClaimCluster] = Field(default_factory=list)
    disagreements: list[ClaimCluster] = Field(default_factory=list)
    # Raised by exactly one model and contradicted by nobody. Neither agreement
    # nor conflict — often the most useful thing in the report, and the thing a
    # naive majority vote would discard.
    unconfirmed: list[ClaimCluster] = Field(default_factory=list)
    evidence: list[ClaimCluster] = Field(default_factory=list)
    uncertainties: list[str] = Field(default_factory=list)
    failures: list[ModelFailure] = Field(default_factory=list)
    cross_examined: int = 0
    elapsed_ms: int = 0


# --------------------------------------------------------------------------
# Tolerant parsing of model output
# --------------------------------------------------------------------------

_FENCE = re.compile(r"```(?:json)?\s*(.*?)```", re.DOTALL)


def extract_json(raw: str) -> dict:
    """Pull a JSON object out of a model response.

    Tries the whole string, then a fenced block, then the outermost braces.
    Raises ValueError if none of those yield an object.
    """
    for candidate in _candidates(raw):
        try:
            parsed = json.loads(candidate)
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise ValueError("no JSON object found in model output")


def _candidates(raw: str):
    raw = raw.strip()
    yield raw
    fenced = _FENCE.search(raw)
    if fenced:
        yield fenced.group(1).strip()
    start, end = raw.find("{"), raw.rfind("}")
    if start != -1 and end > start:
        yield raw[start : end + 1]


def parse_model_response(model: str, raw: str, latency_ms: int = 0) -> ModelResponse:
    """Validate one model's output, raising ValueError with a usable message.

    The caller turns that into a `ModelFailure` so the panel degrades by one
    member instead of failing whole.
    """
    try:
        payload = extract_json(raw)
    except ValueError as exc:
        raise ValueError(f"unparseable output: {exc}") from exc

    payload["model"] = model
    payload["latency_ms"] = latency_ms

    # Give claims stable ids if the model omitted them, so downstream stages can
    # always address a specific claim.
    for i, claim in enumerate(payload.get("claims") or []):
        if isinstance(claim, dict) and not claim.get("id"):
            claim["id"] = f"{model}-c{i}"

    try:
        return ModelResponse.model_validate(payload)
    except ValidationError as exc:
        raise ValueError(f"schema mismatch: {exc.error_count()} error(s)") from exc
