"""Temporal orchestration of the trust pipeline.

The split follows the one rule Temporal imposes: anything that touches the
network, the clock, or the environment is an activity; everything else runs in
the workflow and must be deterministic on replay.

That maps unusually cleanly onto this pipeline. Every model call is an activity.
Every consensus decision — grouping into clusters, assigning verdicts, verifying
citations, computing the trust badge — is a pure function from `consensus.py`
running inside the workflow. So the reasoning is replayable and auditable in the
Temporal UI: you can open any past run and watch the panel disagree.

What Temporal earns here, beyond consistency with the rest of the platform:

- **Genuine parallel fan-out.** Panel members are separate activities started
  together; the wall clock is the slowest model, not their sum.
- **Partial failure that stays partial.** One model timing out retries on its
  own schedule and, if it stays down, becomes a `ModelFailure` in the report
  rather than an exception that sinks the query.
- **A visible audit trail.** "Show where they agree and disagree" is a claim
  about a process; the event history is the evidence for it.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta

from temporalio import activity, workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from multi_model_trust import consensus, router
    from multi_model_trust.panel import invoke_member
    from multi_model_trust.schemas import (
        ModelFailure,
        ModelResponse,
        PanelMember,
        RouteDecision,
        Stance,
        TrustReport,
    )
    from multi_model_trust.synthesize import (
        MAX_CROSS_EXAMINE,
        cross_examine,
        normalize_claims,
        synthesize_answer,
    )

# A panel member gets one retry. Model calls fail for two reasons: a transient
# network blip, which a retry fixes, and a bad key or an exhausted quota, which
# it does not. Retrying harder just spends money slowly on the second case.
PANEL_RETRY = RetryPolicy(maximum_attempts=2, initial_interval=timedelta(seconds=2))
JUDGE_RETRY = RetryPolicy(maximum_attempts=2, initial_interval=timedelta(seconds=1))

PANEL_TIMEOUT = timedelta(seconds=120)
JUDGE_TIMEOUT = timedelta(seconds=90)


# --------------------------------------------------------------------------
# Activities — everything that touches the outside world
# --------------------------------------------------------------------------
#
# Activities exchange plain dicts. Temporal's default converter handles JSON,
# and keeping pydantic models off the wire means a schema change cannot break
# the deserialization of a run that is already in flight.


@activity.defn(name="trust_route")
async def trust_route_activity(payload: dict) -> dict:
    # Routing is deterministic logic, but it reads API keys and the tier out of
    # the environment, and environment reads are not replay-safe. So it lives
    # here rather than in the workflow body.
    return router.route(payload["query"], payload.get("tier")).model_dump()


@activity.defn(name="trust_invoke_member")
async def trust_invoke_member_activity(payload: dict) -> dict:
    member = PanelMember.model_validate(payload["member"])
    response, failure = await invoke_member(member, payload["query"], payload["corpus"])
    return {
        "response": response.model_dump() if response else None,
        "failure": failure.model_dump() if failure else None,
    }


@activity.defn(name="trust_normalize")
async def trust_normalize_activity(payload: dict) -> list[dict]:
    responses = [ModelResponse.model_validate(r) for r in payload["responses"]]
    return await normalize_claims(responses)


@activity.defn(name="trust_cross_examine")
async def trust_cross_examine_activity(payload: dict) -> dict:
    from multi_model_trust.schemas import ClaimCluster

    cluster = ClaimCluster.model_validate(payload["cluster"])
    stances, finding = await cross_examine(payload["query"], cluster, payload["corpus"])
    return {
        "cluster_id": cluster.id,
        "stances": {m: s.value for m, s in stances.items()},
        "finding": finding,
    }


@activity.defn(name="trust_synthesize")
async def trust_synthesize_activity(payload: dict) -> str:
    from multi_model_trust.schemas import ClaimCluster, TrustStatus

    return await synthesize_answer(
        payload["query"],
        [ClaimCluster.model_validate(c) for c in payload["agreements"]],
        [ClaimCluster.model_validate(c) for c in payload["disagreements"]],
        [ClaimCluster.model_validate(c) for c in payload["unconfirmed"]],
        TrustStatus(payload["status"]),
        [ModelFailure.model_validate(f) for f in payload["failures"]],
    )


TRUST_ACTIVITIES = [
    trust_route_activity,
    trust_invoke_member_activity,
    trust_normalize_activity,
    trust_cross_examine_activity,
    trust_synthesize_activity,
]


# --------------------------------------------------------------------------
# The workflow
# --------------------------------------------------------------------------


@workflow.defn(name="TrustPanelWorkflow")
class TrustPanelWorkflow:
    """One run per query. Short-lived — this is a pipeline, not a conversation."""

    @workflow.run
    async def run(self, request: dict) -> dict:
        query: str = request["query"]
        corpus: dict[str, str] = request.get("corpus") or {}
        started = workflow.now()

        route = RouteDecision.model_validate(
            await workflow.execute_activity(
                trust_route_activity,
                {"query": query, "tier": request.get("tier")},
                start_to_close_timeout=timedelta(seconds=15),
                retry_policy=JUDGE_RETRY,
            )
        )

        if not route.panel:
            return self._empty_report(query, route, started).model_dump(mode="json")

        responses, failures = await self._run_panel(route.panel, query, corpus)

        if not responses:
            report = self._empty_report(query, route, started)
            report.failures = failures
            report.recommended_answer = (
                "Every model in the panel failed to answer. No consensus can be "
                "reported."
            )
            return report.model_dump(mode="json")

        grouping = await self._normalize(responses)
        clusters = consensus.build_clusters(responses, grouping)
        clusters = consensus.classify(clusters, responding_models=len(responses))
        clusters = consensus.verify_citations(clusters, corpus)

        clusters, examined = await self._resolve_conflicts(
            query, clusters, corpus, len(responses)
        )

        status = consensus.trust_status(clusters, failures, panel_size=len(route.panel))
        agreements, disagreements, unconfirmed = consensus.split(clusters)

        answer = await workflow.execute_activity(
            trust_synthesize_activity,
            {
                "query": query,
                "agreements": [c.model_dump(mode="json") for c in agreements],
                "disagreements": [c.model_dump(mode="json") for c in disagreements],
                "unconfirmed": [c.model_dump(mode="json") for c in unconfirmed],
                "status": status.value,
                "failures": [f.model_dump() for f in failures],
            },
            start_to_close_timeout=JUDGE_TIMEOUT,
            retry_policy=JUDGE_RETRY,
        )

        report = TrustReport(
            query=query,
            route=route,
            recommended_answer=answer,
            trust_status=status,
            agreements=agreements,
            disagreements=disagreements,
            unconfirmed=unconfirmed,
            evidence=[c for c in clusters if c.evidence],
            uncertainties=self._uncertainties(responses, disagreements),
            failures=failures,
            cross_examined=examined,
            elapsed_ms=int((workflow.now() - started).total_seconds() * 1000),
        )
        return report.model_dump(mode="json")

    # ----------------------------------------------------------------------

    async def _run_panel(
        self, panel: list[PanelMember], query: str, corpus: dict
    ) -> tuple[list[ModelResponse], list[ModelFailure]]:
        """Fan out to every member at once. Each is its own activity, so a slow
        model delays only itself and a dead one retries on its own schedule."""
        handles = [
            workflow.execute_activity(
                trust_invoke_member_activity,
                {"member": member.model_dump(), "query": query, "corpus": corpus},
                start_to_close_timeout=PANEL_TIMEOUT,
                retry_policy=PANEL_RETRY,
            )
            for member in panel
        ]
        outcomes = await asyncio.gather(*handles, return_exceptions=True)

        responses: list[ModelResponse] = []
        failures: list[ModelFailure] = []
        for member, outcome in zip(panel, outcomes):
            if isinstance(outcome, BaseException):
                # Activity exhausted its retries. The panel narrows; the query
                # does not fail.
                failures.append(
                    ModelFailure(
                        model=member.model, reason=str(outcome)[:300], stage="invoke"
                    )
                )
                continue
            if outcome.get("response"):
                responses.append(ModelResponse.model_validate(outcome["response"]))
            if outcome.get("failure"):
                failures.append(ModelFailure.model_validate(outcome["failure"]))

        responses.sort(key=lambda r: r.model)
        failures.sort(key=lambda f: f.model)
        return responses, failures

    async def _normalize(self, responses: list[ModelResponse]) -> list[dict]:
        try:
            return await workflow.execute_activity(
                trust_normalize_activity,
                {"responses": [r.model_dump() for r in responses]},
                start_to_close_timeout=JUDGE_TIMEOUT,
                retry_policy=JUDGE_RETRY,
            )
        except Exception:
            # Degrade to exact-text grouping. It finds far less agreement, which
            # surfaces as a low-trust report — the honest outcome when the stage
            # that detects agreement is unavailable.
            return consensus.fallback_grouping(responses)

    async def _resolve_conflicts(
        self,
        query: str,
        clusters: list,
        corpus: dict,
        responding: int,
    ) -> tuple[list, int]:
        """Cross-examine material conflicts, capped at MAX_CROSS_EXAMINE.

        Only conflicts are examined, and only once each: this is on the critical
        path of a user-facing request, and a disagreement that survives evidence
        review is a finding, not a problem to grind away at.
        """
        from multi_model_trust.schemas import Verdict

        conflicts = [c for c in clusters if c.verdict == Verdict.MATERIAL_CONFLICT]
        if not conflicts:
            return clusters, 0

        targets = conflicts[:MAX_CROSS_EXAMINE]
        rulings = await asyncio.gather(
            *(
                workflow.execute_activity(
                    trust_cross_examine_activity,
                    {
                        "query": query,
                        "cluster": cluster.model_dump(mode="json"),
                        "corpus": corpus,
                    },
                    start_to_close_timeout=JUDGE_TIMEOUT,
                    retry_policy=JUDGE_RETRY,
                )
                for cluster in targets
            ),
            return_exceptions=True,
        )

        judged: dict[str, dict[str, Stance]] = {}
        for ruling in rulings:
            if isinstance(ruling, BaseException) or not ruling.get("stances"):
                # No ruling means the conflict stands. Safe direction: an
                # unresolved conflict is shown, a wrongly resolved one vanishes.
                continue
            judged[ruling["cluster_id"]] = {
                model: Stance(value) for model, value in ruling["stances"].items()
            }

        clusters = consensus.apply_stances(clusters, judged)
        clusters = consensus.classify(clusters, responding_models=responding)
        return clusters, len(targets)

    @staticmethod
    def _uncertainties(
        responses: list[ModelResponse], disagreements: list
    ) -> list[str]:
        """The follow-up list: what the panel said it could not determine, plus
        what it could not settle among itself."""
        seen: list[str] = []
        for response in responses:
            for item in response.unknowns + response.assumptions:
                text = item.strip()
                if text and text not in seen:
                    seen.append(text)
        for cluster in disagreements:
            if cluster.rejecting_models:
                text = f"Unresolved: {cluster.canonical_text}"
                if text not in seen:
                    seen.append(text)
        return seen[:10]

    @staticmethod
    def _empty_report(query: str, route: RouteDecision, started) -> TrustReport:
        from multi_model_trust.schemas import TrustStatus

        return TrustReport(
            query=query,
            route=route,
            recommended_answer=route.rationale,
            trust_status=TrustStatus.DEGRADED,
            elapsed_ms=int((workflow.now() - started).total_seconds() * 1000),
        )
