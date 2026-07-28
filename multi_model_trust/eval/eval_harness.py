"""Eval harness for disagreement detection and citation correctness.

    python -m multi_model_trust.eval.eval_harness             # replay, offline
    python -m multi_model_trust.eval.eval_harness --record    # re-record live
    python -m multi_model_trust.eval.eval_harness --mutate ignore-rejects

Record and replay
-----------------
The pipeline's grouping stage is a model call, so a naive harness would be
non-deterministic, slow, and would bill a card on every CI run. Instead the
normalizer's output for each fixture case is recorded once to
`fixtures/normalizer_tape.json` and replayed thereafter. The default run makes
no network calls at all, and two runs on the same commit produce identical
numbers.

What that does and does not measure: replay exercises grouping-consumption,
stance aggregation, verdict logic, citation verification, and trust status —
every deterministic decision the pipeline makes. It does not re-measure the
normalizer's own judgment; `--record` does that, and any drift shows up as a
changed tape plus changed scores.

Metrics
-------
- **Clustering F1** — pairwise: for every pair of claims in a case, did we put
  them in the same group, and should we have?
- **Conflict F1** — the headline number. Pairwise over (rejecting claim,
  opposing claim) pairs, so a conflict found inside a slightly wrong cluster
  still counts, and a conflict invented where none exists is punished.
- **Verdict accuracy** — per gold cluster, is it labelled unanimous / majority /
  conditional / conflict / single_source correctly? Clustering F1 is pairwise
  and therefore cannot see this: promoting a majority to unanimous changes no
  pair at all.
- **Claim retention** — what fraction of input claims survive into the report?
  Gated at 100%. Pairwise F1 is blind to a dropped single-claim cluster, because
  a cluster of one contributes no pairs; this metric exists to catch exactly
  that, and it guards the invariant that no minority claim is ever lost.
- **Citation accuracy** — per claim, does the verified/unsupported/broken/
  unverified label match ground truth? Pure string logic, so the gate is 100%.
- **Trust-status accuracy** — exact match on the headline badge.
"""

from __future__ import annotations

import argparse
import asyncio
import itertools
import json
import sys
from pathlib import Path

# Allow `python multi_model_trust/eval/eval_harness.py` as well as `-m`.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from multi_model_trust import consensus  # noqa: E402
from multi_model_trust.schemas import (  # noqa: E402
    CitationStatus,
    ModelFailure,
    ModelResponse,
    Stance,
    TrustStatus,
    Verdict,
)

FIXTURES = Path(__file__).parent / "fixtures"
TAPE = FIXTURES / "normalizer_tape.json"

# Gates. A run below any of these exits non-zero.
GATES = {
    "cluster_f1": 0.85,
    "conflict_f1": 0.80,
    "verdict_accuracy": 0.90,
    "claim_retention": 1.00,
    "citation_accuracy": 1.00,
    "trust_accuracy": 0.85,
}


# --------------------------------------------------------------------------
# Mutations — deliberate regressions, to prove the harness has teeth
# --------------------------------------------------------------------------
#
# Each corresponds to a plausible one-line change in consensus.py. A test suite
# that only ever passes tells you nothing about whether it would catch a
# regression, so the harness ships with the regressions.

def _mutate_ignore_rejects(clusters):
    """As if `_verdict` stopped checking `rejecting_models` — every stance reads
    as support. Conflicts become invisible."""
    for cluster in clusters:
        for model, stance in cluster.stances.items():
            if stance == Stance.REJECTS:
                cluster.stances[model] = Stance.SUPPORTS
    return clusters


def _mutate_drop_orphans(clusters):
    """As if `build_clusters` skipped its recovery loop — claims only one model
    made are silently lost, which is the failure mode the whole panel exists to
    prevent."""
    return [c for c in clusters if len(c.member_claims) > 1]


def _mutate_cluster_unanimity(clusters):
    """As if unanimity were measured against the models that raised a claim
    rather than the whole panel — two models agreeing while a third stays
    silent gets promoted to 'unanimous'."""
    for cluster in clusters:
        if cluster.verdict == Verdict.MAJORITY:
            cluster.verdict = Verdict.UNANIMOUS
    return clusters


MUTATIONS = {
    "ignore-rejects": ("post_stance", _mutate_ignore_rejects),
    "drop-orphans": ("post_cluster", _mutate_drop_orphans),
    "cluster-unanimity": ("post_classify", _mutate_cluster_unanimity),
}


# --------------------------------------------------------------------------
# Running one case
# --------------------------------------------------------------------------


def load_cases() -> list[dict]:
    return json.loads((FIXTURES / "cases.json").read_text())


def load_corpus() -> dict[str, str]:
    return json.loads((FIXTURES / "corpus.json").read_text())


def run_case(case: dict, grouping: list[dict], mutate: str | None) -> dict:
    """Run the deterministic pipeline over one fixture case."""
    stage, mutation = MUTATIONS.get(mutate, (None, None))

    responses = [ModelResponse.model_validate(r) for r in case["responses"]]
    failures = [ModelFailure.model_validate(f) for f in case.get("failures", [])]
    corpus = case["corpus"] if "corpus" in case else load_corpus()

    clusters = consensus.build_clusters(responses, grouping)
    if stage == "post_cluster":
        clusters = mutation(clusters)
    if stage == "post_stance":
        clusters = mutation(clusters)

    clusters = consensus.classify(clusters, responding_models=len(responses))
    if stage == "post_classify":
        clusters = mutation(clusters)

    clusters = consensus.verify_citations(clusters, corpus)
    status = consensus.trust_status(clusters, failures, panel_size=len(case["panel"]))

    claim_status = {}
    for response in responses:
        for claim in response.claims:
            if claim.evidence:
                claim_status[claim.id] = consensus.check_evidence(claim.evidence[0], corpus)
            else:
                claim_status[claim.id] = CitationStatus.UNVERIFIED

    return {"clusters": clusters, "status": status, "citations": claim_status}


# --------------------------------------------------------------------------
# Scoring
# --------------------------------------------------------------------------


def _pairs(groups: list[list[str]]) -> set[frozenset[str]]:
    return {frozenset(p) for g in groups for p in itertools.combinations(sorted(g), 2)}


def _predicted_groups(clusters) -> list[list[str]]:
    return [sorted(c.member_claims.values()) for c in clusters]


def _gold_conflict_pairs(case: dict) -> set[frozenset[str]]:
    """A conflict is a pair: the claim taking the minority position, against
    each claim it contradicts."""
    rejects = set(case["expected"].get("rejects", []))
    pairs = set()
    for group in case["expected"].get("conflicts", []):
        for rejecting in rejects.intersection(group):
            for other in group:
                if other != rejecting:
                    pairs.add(frozenset({rejecting, other}))
    return pairs


def _predicted_conflict_pairs(clusters) -> set[frozenset[str]]:
    pairs = set()
    for cluster in clusters:
        if cluster.verdict != Verdict.MATERIAL_CONFLICT:
            continue
        rejecting = [cluster.member_claims[m] for m in cluster.rejecting_models]
        others = [
            claim_id
            for model, claim_id in cluster.member_claims.items()
            if model not in cluster.rejecting_models
        ]
        for r in rejecting:
            for o in others:
                pairs.add(frozenset({r, o}))
    return pairs


def prf(tp: int, fp: int, fn: int) -> tuple[float, float, float]:
    precision = tp / (tp + fp) if tp + fp else 1.0
    recall = tp / (tp + fn) if tp + fn else 1.0
    f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
    return precision, recall, f1


def score(cases: list[dict], results: list[dict]) -> dict:
    c_tp = c_fp = c_fn = 0     # clustering
    x_tp = x_fp = x_fn = 0     # conflicts
    cite_hit = cite_total = 0
    verdict_hit = verdict_total = 0
    kept = expected_claims = 0
    trust_hit = 0
    per_case = []

    for case, result in zip(cases, results):
        gold_pairs = _pairs(case["expected"]["clusters"])
        pred_pairs = _pairs(_predicted_groups(result["clusters"]))
        c_tp += len(gold_pairs & pred_pairs)
        c_fp += len(pred_pairs - gold_pairs)
        c_fn += len(gold_pairs - pred_pairs)

        gold_conf = _gold_conflict_pairs(case)
        pred_conf = _predicted_conflict_pairs(result["clusters"])
        x_tp += len(gold_conf & pred_conf)
        x_fp += len(pred_conf - gold_conf)
        x_fn += len(gold_conf - pred_conf)

        # Verdict accuracy: match each gold cluster to the predicted cluster with
        # the same members. A gold cluster with no counterpart is a miss, which
        # is how a dropped cluster gets punished here as well.
        by_members = {
            frozenset(c.member_claims.values()): c.verdict.value for c in result["clusters"]
        }
        case_verdict_ok = True
        for members, expected_verdict in zip(
            case["expected"]["clusters"], case["expected"]["verdicts"]
        ):
            verdict_total += 1
            if by_members.get(frozenset(members)) == expected_verdict:
                verdict_hit += 1
            else:
                case_verdict_ok = False

        # Claim retention: nothing the panel said may vanish from the report.
        submitted = {c["id"] for r in case["responses"] for c in r["claims"]}
        surviving = {cid for c in result["clusters"] for cid in c.member_claims.values()}
        expected_claims += len(submitted)
        kept += len(submitted & surviving)

        case_cite_ok = True
        for claim_id, expected in case["expected"]["citations"].items():
            cite_total += 1
            actual = result["citations"].get(claim_id)
            if actual is not None and actual.value == expected:
                cite_hit += 1
            else:
                case_cite_ok = False

        trust_ok = result["status"] == TrustStatus(case["expected"]["trust_status"])
        trust_hit += int(trust_ok)

        per_case.append(
            {
                "id": case["id"],
                "cluster_ok": gold_pairs == pred_pairs,
                "conflict_ok": gold_conf == pred_conf,
                "verdict_ok": case_verdict_ok,
                "kept_ok": submitted <= surviving,
                "citation_ok": case_cite_ok,
                "trust_ok": trust_ok,
                "trust_expected": case["expected"]["trust_status"],
                "trust_actual": result["status"].value,
            }
        )

    _, _, cluster_f1 = prf(c_tp, c_fp, c_fn)
    conflict_p, conflict_r, conflict_f1 = prf(x_tp, x_fp, x_fn)

    return {
        "cluster_f1": round(cluster_f1, 4),
        "conflict_precision": round(conflict_p, 4),
        "conflict_recall": round(conflict_r, 4),
        "conflict_f1": round(conflict_f1, 4),
        "conflict_counts": {"tp": x_tp, "fp": x_fp, "fn": x_fn},
        "verdict_accuracy": round(verdict_hit / verdict_total, 4) if verdict_total else 1.0,
        "claim_retention": round(kept / expected_claims, 4) if expected_claims else 1.0,
        "citation_accuracy": round(cite_hit / cite_total, 4) if cite_total else 1.0,
        "trust_accuracy": round(trust_hit / len(cases), 4),
        "per_case": per_case,
    }


# --------------------------------------------------------------------------
# Tape
# --------------------------------------------------------------------------


async def record_tape(cases: list[dict]) -> dict[str, list[dict]]:
    """Re-run the live normalizer over every case and write a fresh tape."""
    from multi_model_trust.synthesize import normalize_claims

    tape: dict[str, list[dict]] = {}
    for case in cases:
        responses = [ModelResponse.model_validate(r) for r in case["responses"]]
        try:
            tape[case["id"]] = await normalize_claims(responses)
            print(f"  recorded {case['id']}")
        except Exception as exc:
            # A tape entry that failed to record falls back at replay time,
            # which is exactly what production does.
            print(f"  FAILED   {case['id']}: {str(exc)[:100]}")
            tape[case["id"]] = consensus.fallback_grouping(responses)
    return tape


def load_tape() -> dict[str, list[dict]]:
    if not TAPE.exists():
        sys.exit(
            f"No normalizer tape at {TAPE}.\n"
            "Record one with:  python -m multi_model_trust.eval.eval_harness --record"
        )
    return json.loads(TAPE.read_text())


# --------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--record", action="store_true", help="re-record the normalizer tape (live, costs money)")
    parser.add_argument("--mutate", choices=sorted(MUTATIONS), help="inject a known regression")
    parser.add_argument("--json", action="store_true", help="emit machine-readable results")
    args = parser.parse_args()

    cases = load_cases()

    if args.record:
        tape = asyncio.run(record_tape(cases))
        TAPE.write_text(json.dumps(tape, indent=2, sort_keys=True) + "\n")
        print(f"\nWrote {TAPE} ({len(tape)} cases)")
        return 0

    tape = load_tape()
    results = [run_case(c, tape.get(c["id"], []), args.mutate) for c in cases]
    report = score(cases, results)

    if args.json:
        print(json.dumps(report, indent=2))
    else:
        _print_report(report, args.mutate)

    failed = [name for name, floor in GATES.items() if report[name] < floor]
    if failed:
        print(f"\nFAIL — below gate: {', '.join(failed)}")
        return 1
    print("\nPASS — all gates met")
    return 0


def _print_report(report: dict, mutate: str | None) -> None:
    if mutate:
        print(f"!! mutation active: {mutate} — {MUTATIONS[mutate][1].__doc__.splitlines()[0]}\n")

    header = f"{'case':<38} {'clust':>6} {'confl':>7} {'verdict':>8} {'kept':>5} {'cite':>5} {'trust':>16}"
    print(header)
    print("-" * len(header))
    for row in report["per_case"]:
        trust = "ok" if row["trust_ok"] else f"{row['trust_actual']}!={row['trust_expected']}"
        print(
            f"{row['id']:<38} {_mark(row['cluster_ok']):>6} {_mark(row['conflict_ok']):>7}"
            f" {_mark(row['verdict_ok']):>8} {_mark(row['kept_ok']):>5}"
            f" {_mark(row['citation_ok']):>5} {trust:>16}"
        )

    counts = report["conflict_counts"]
    print("-" * len(header))
    print(f"clustering F1        {report['cluster_f1']:.3f}   (gate {GATES['cluster_f1']:.2f})")
    print(
        f"conflict  F1         {report['conflict_f1']:.3f}   (gate {GATES['conflict_f1']:.2f})"
        f"   P={report['conflict_precision']:.3f} R={report['conflict_recall']:.3f}"
        f"  tp={counts['tp']} fp={counts['fp']} fn={counts['fn']}"
    )
    print(f"verdict accuracy     {report['verdict_accuracy']:.3f}   (gate {GATES['verdict_accuracy']:.2f})")
    print(f"claim retention      {report['claim_retention']:.3f}   (gate {GATES['claim_retention']:.2f})")
    print(f"citation accuracy    {report['citation_accuracy']:.3f}   (gate {GATES['citation_accuracy']:.2f})")
    print(f"trust-status acc.    {report['trust_accuracy']:.3f}   (gate {GATES['trust_accuracy']:.2f})")


def _mark(ok: bool) -> str:
    return "ok" if ok else "FAIL"


if __name__ == "__main__":
    raise SystemExit(main())
