"""The consensus core: group claims, classify agreement, verify sources.

Everything in this module is a pure function of its arguments. No network, no
clock, no randomness. The normalizer's grouping arrives as data that somebody
else fetched. That is what lets the eval replay a recorded run offline and get
identical results, and what lets this logic run inside a Temporal workflow,
where non-determinism corrupts replay.

Why grouping is not done here with embeddings
---------------------------------------------
The first version of this module clustered claims by cosine similarity over
sentence embeddings. It was measured against `eval/fixtures/cases.json` and it
does not work — there is no threshold that separates claims that belong together
from claims that do not:

    variant                          weakest true pair   strongest false pair
    cosine @256 dims                        0.686               0.777
    cosine @1536 dims                       0.640               0.765
    numeral-masked cosine @256              0.701               0.806

The failure is structural, not a tuning problem. Embeddings measure topical
relatedness, so "Q4 revenue was $48.2M" and "Q4 operating margin was 8.4%" score
high while a genuine paraphrase with different vocabulary scores low. Masking the
numerals makes it worse, because the numerals were the only thing separating
those two attributes. Grouping claims by meaning is a judgment task; it is done
by a model in `synthesize.py` and the result is validated here.

The one invariant that matters
------------------------------
No claim is ever dropped. A claim the normalizer forgot to mention becomes its
own single-source cluster. A minority claim that the rest of the panel missed is
the most valuable thing in the report, and silently losing one to a malformed
grouping would defeat the point of running a panel at all.
"""

from __future__ import annotations

import re

from .schemas import (
    CitationStatus,
    Claim,
    ClaimCluster,
    Evidence,
    ModelFailure,
    ModelResponse,
    Stance,
    TrustStatus,
    Verdict,
)

# A conflict on a claim nobody is confident about is noise, not a disagreement
# worth putting in front of a reader.
CONFLICT_CONFIDENCE_FLOOR = 0.35

_PUNCT = re.compile(r"[^\w\s]")
_WS = re.compile(r"\s+")


def normalize_text(text: str) -> str:
    return _WS.sub(" ", _PUNCT.sub(" ", text.lower())).strip()


# --------------------------------------------------------------------------
# Building clusters from the normalizer's grouping
# --------------------------------------------------------------------------


def build_clusters(
    responses: list[ModelResponse],
    grouping: list[dict],
) -> list[ClaimCluster]:
    """Materialize the normalizer's output into clusters.

    `grouping` is the validated normalizer payload:

        [{"canonical": "...", "members": [{"claim_id": "...",
                                           "stance": "supports"}, ...]}, ...]

    Unknown claim ids are ignored, a claim listed twice keeps its first
    placement, and any claim the normalizer omitted is recovered into its own
    cluster. Those three rules mean a sloppy normalizer degrades the report's
    resolution but never its completeness.
    """
    owner: dict[str, str] = {}  # claim id -> model
    claims: dict[str, Claim] = {}
    for response in responses:
        for claim in response.claims:
            owner[claim.id] = response.model
            claims[claim.id] = claim

    clusters: list[ClaimCluster] = []
    placed: set[str] = set()

    for group in grouping:
        cluster = ClaimCluster(id=f"cl{len(clusters):02d}", canonical_text="")
        for member in group.get("members") or []:
            claim_id = member.get("claim_id")
            if claim_id not in owner or claim_id in placed:
                continue
            model = owner[claim_id]
            if model in cluster.member_claims:
                # One model contributing twice to one cluster is a restatement,
                # not corroboration. Keep it out so vote counts stay honest.
                continue
            cluster.member_claims[model] = claim_id
            cluster.stances[model] = _coerce_stance(member.get("stance"))
            cluster.evidence.extend(claims[claim_id].evidence)
            placed.add(claim_id)
        if not cluster.member_claims:
            continue
        cluster.canonical_text = (group.get("canonical") or "").strip() or _longest(
            cluster, claims
        )
        cluster.confidence = _mean_confidence(cluster, claims)
        clusters.append(cluster)

    # Recover anything the normalizer left out.
    for claim_id in sorted(set(owner) - placed):
        model = owner[claim_id]
        clusters.append(
            ClaimCluster(
                id=f"cl{len(clusters):02d}",
                canonical_text=claims[claim_id].text,
                stances={model: Stance.SUPPORTS},
                member_claims={model: claim_id},
                evidence=list(claims[claim_id].evidence),
                confidence=claims[claim_id].confidence,
            )
        )

    # Models that never addressed a claim are recorded explicitly. "Nobody else
    # mentioned this" is the difference between a corroborated fact and one
    # model's unchallenged assertion, and the reader needs to see which it is.
    for cluster in clusters:
        for response in responses:
            cluster.stances.setdefault(response.model, Stance.UNADDRESSED)

    return clusters


def _coerce_stance(raw) -> Stance:
    try:
        return Stance(str(raw).strip().lower())
    except ValueError:
        # An unrecognised stance means the normalizer went off-script. Treat it
        # as support: the claim was made, and we would rather show it than lose
        # it to a typo.
        return Stance.SUPPORTS


def _longest(cluster: ClaimCluster, claims: dict[str, Claim]) -> str:
    texts = [claims[cid].text for cid in cluster.member_claims.values()]
    return max(texts, key=len) if texts else ""


def _mean_confidence(cluster: ClaimCluster, claims: dict[str, Claim]) -> float:
    scores = [claims[cid].confidence for cid in cluster.member_claims.values()]
    return round(sum(scores) / len(scores), 3) if scores else 0.0


def fallback_grouping(responses: list[ModelResponse]) -> list[dict]:
    """Grouping to use when the normalizer call fails outright.

    Exact match on normalized text — it will only catch models that phrased a
    claim identically, which is rare. That is the point: it is honest about
    finding little rather than inventing agreement, and the report ends up
    showing lots of single-source claims, which correctly reads as low trust.
    """
    buckets: dict[str, list[dict]] = {}
    for response in responses:
        for claim in response.claims:
            buckets.setdefault(normalize_text(claim.text), []).append(
                {"claim_id": claim.id, "stance": Stance.SUPPORTS.value}
            )
    return [
        {"canonical": key, "members": members}
        for key, members in sorted(buckets.items())
    ]


def apply_stances(
    clusters: list[ClaimCluster], judged: dict[str, dict[str, Stance]]
) -> list[ClaimCluster]:
    """Overlay cross-examiner rulings onto the normalizer's stances.

    `judged` maps cluster id -> {model: stance}. Anything the cross-examiner did
    not rule on keeps the stance it already had, so a partial or failed
    cross-examination degrades to the normalizer's view rather than losing the
    cluster. A model that never made a claim in this cluster cannot be given a
    stance in it — that would let the judge invent votes.
    """
    for cluster in clusters:
        for model, stance in judged.get(cluster.id, {}).items():
            if model in cluster.member_claims:
                cluster.stances[model] = stance
    return clusters


# --------------------------------------------------------------------------
# Verdicts
# --------------------------------------------------------------------------


def classify(clusters: list[ClaimCluster], responding_models: int) -> list[ClaimCluster]:
    """`responding_models` is the number of panel members that returned usable
    output — not the number that happened to raise this particular claim.
    Unanimity has to be measured against the whole panel, or two models agreeing
    while a third stays silent reads as "unanimous", which is exactly the quiet
    overstatement this pipeline exists to prevent."""
    for cluster in clusters:
        cluster.verdict = _verdict(cluster, responding_models)
    return clusters


def _verdict(cluster: ClaimCluster, responding_models: int) -> Verdict:
    supports = cluster.supporting_models
    rejects = cluster.rejecting_models
    conditional = [m for m, s in cluster.stances.items() if s == Stance.CONDITIONAL]

    if rejects and cluster.confidence >= CONFLICT_CONFIDENCE_FLOOR:
        return Verdict.MATERIAL_CONFLICT
    if rejects:
        # A contradiction neither model stands behind. Real, but not a headline.
        return Verdict.CONDITIONAL
    if conditional:
        return Verdict.CONDITIONAL
    if len(supports) <= 1:
        return Verdict.SINGLE_SOURCE
    if len(supports) >= responding_models:
        return Verdict.UNANIMOUS
    return Verdict.MAJORITY


def split(
    clusters: list[ClaimCluster],
) -> tuple[list[ClaimCluster], list[ClaimCluster], list[ClaimCluster]]:
    """Partition into (agreements, disagreements, unconfirmed).

    Unconfirmed is its own bucket rather than part of disagreements. A claim one
    model raised and nobody contradicted is not a conflict — nobody else looked
    at it. Filing the two together makes the report describe disputes that never
    happened, and it buries the genuinely useful case: the minority observation
    the rest of the panel missed.

    Nor can it go in agreements, which would present a single unchallenged
    assertion as corroborated. It is a third thing, and it is shown as one.
    """
    agree = [c for c in clusters if c.verdict in (Verdict.UNANIMOUS, Verdict.MAJORITY)]
    disagree = [
        c for c in clusters if c.verdict in (Verdict.MATERIAL_CONFLICT, Verdict.CONDITIONAL)
    ]
    unconfirmed = [c for c in clusters if c.verdict == Verdict.SINGLE_SOURCE]

    agree.sort(key=lambda c: (-c.confidence, c.id))
    disagree.sort(key=lambda c: (c.verdict != Verdict.MATERIAL_CONFLICT, -c.confidence, c.id))
    unconfirmed.sort(key=lambda c: (-c.confidence, c.id))
    return agree, disagree, unconfirmed


# --------------------------------------------------------------------------
# Citations
# --------------------------------------------------------------------------


def check_evidence(evidence: Evidence, corpus: dict[str, str]) -> CitationStatus:
    """Verify one citation against the supplied corpus.

    "Verified" means the quoted span appears verbatim in the cited source — a
    check on whether the citation is *real*, not on whether it entails the
    claim. Entailment needs a model; this needs a string search, and it catches
    the common failure, which is a confident citation of something that was
    never written.
    """
    if not corpus:
        return CitationStatus.UNVERIFIED
    if not evidence.source_id or evidence.source_id not in corpus:
        return CitationStatus.BROKEN
    if not evidence.quote.strip():
        return CitationStatus.UNSUPPORTED
    haystack = normalize_text(corpus[evidence.source_id])
    return (
        CitationStatus.VERIFIED
        if normalize_text(evidence.quote) in haystack
        else CitationStatus.UNSUPPORTED
    )


_CITATION_RANK = {
    CitationStatus.VERIFIED: 3,
    CitationStatus.UNSUPPORTED: 2,
    CitationStatus.BROKEN: 1,
    CitationStatus.UNVERIFIED: 0,
}


def verify_citations(clusters: list[ClaimCluster], corpus: dict[str, str]) -> list[ClaimCluster]:
    """Record both the best citation and the count of failed ones.

    The best-of view is right for the badge — one good source is enough to
    consider a claim sourced. But best-of alone hides a fabricated citation
    sitting next to a real one, which is how a report containing a hallucinated
    source ends up looking fully verified. So the failures are counted too, and
    `trust_status` reads that count.
    """
    for cluster in clusters:
        statuses = [check_evidence(e, corpus) for e in cluster.evidence]
        cluster.citation_status = (
            max(statuses, key=lambda s: _CITATION_RANK[s])
            if statuses
            else CitationStatus.UNVERIFIED
        )
        cluster.disputed_citations = sum(
            1 for s in statuses if s in (CitationStatus.BROKEN, CitationStatus.UNSUPPORTED)
        )
    return clusters


# --------------------------------------------------------------------------
# Headline trust status
# --------------------------------------------------------------------------


def trust_status(
    clusters: list[ClaimCluster],
    failures: list[ModelFailure],
    panel_size: int,
) -> TrustStatus:
    responded = panel_size - len(failures)
    if responded < 2:
        # One model is not a consensus. What it said may well be right, but this
        # pipeline cannot vouch for it, and should not pretend otherwise.
        return TrustStatus.DEGRADED
    if any(c.verdict == Verdict.MATERIAL_CONFLICT for c in clusters):
        return TrustStatus.CONTESTED

    # A citation that did not check out anywhere in the report caps trust,
    # even when the claim it was attached to is otherwise unanimous. A panel
    # that agrees while one member cites a source that does not exist has told
    # you something important about itself.
    if any(c.disputed_citations for c in clusters):
        return TrustStatus.MIXED

    # Likewise a claim only one model raised. It may be the most valuable thing
    # in the report, but nothing corroborates it, and the badge covers the whole
    # report rather than only its agreed portion.
    if any(c.verdict == Verdict.SINGLE_SOURCE for c in clusters):
        return TrustStatus.MIXED

    corroborated = [c for c in clusters if len(c.member_claims) > 1]
    if not corroborated:
        return TrustStatus.MIXED

    all_unanimous = all(c.verdict == Verdict.UNANIMOUS for c in corroborated)
    all_sourced = all(c.citation_status == CitationStatus.VERIFIED for c in corroborated)
    if all_unanimous and all_sourced and not failures:
        return TrustStatus.HIGH
    return TrustStatus.MIXED
