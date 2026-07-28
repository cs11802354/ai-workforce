"""HTTP surface for the trust pipeline.

Deliberately has no import from the host application: it builds its own Temporal
client from the environment and defines its own request models. The directory
can be lifted into another FastAPI app by including this router, and the only
coupling left is the task queue name.

The query route is synchronous — it starts the workflow and waits. A panel of
two or three models plus normalization and synthesis takes tens of seconds, and
the honest options are to wait or to build a job-polling protocol. For a page
whose entire job is showing one considered answer, waiting is the right trade,
and Temporal is holding the durable state either way.
"""

from __future__ import annotations

import json
import os
import uuid
from pathlib import Path

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from temporalio.client import Client

TASK_QUEUE = os.environ.get("TEMPORAL_TASK_QUEUE", "agent-tasks")
TEMPORAL_HOST = os.environ.get("TEMPORAL_HOST", "localhost:7233")

router = APIRouter(prefix="/trust", tags=["trust"])

_client: Client | None = None


async def get_client() -> Client:
    global _client
    if _client is None:
        _client = await Client.connect(TEMPORAL_HOST)
    return _client


class TrustQuery(BaseModel):
    query: str = Field(min_length=3, max_length=2000)
    # Optional corpus of source_id -> text. When present, every citation is
    # checked against it and the report can say "verified" rather than
    # "the model asserted this".
    corpus: dict[str, str] = Field(default_factory=dict)
    tier: str | None = None


def _demo_corpus() -> dict[str, str]:
    path = Path(__file__).parent / "eval" / "fixtures" / "corpus.json"
    try:
        return json.loads(path.read_text())
    except (OSError, ValueError):
        return {}


# Presets for the UI. Each is chosen to exercise a different path: a clean
# lookup, a question the corpus cannot answer, and one with no corpus at all
# where citations can only ever be model assertions.
EXAMPLES = [
    {
        "label": "Sourced lookup",
        "query": "What was Northwind Robotics' Q4 revenue, and did operating margin improve?",
        "use_corpus": True,
        "note": "Answerable from the corpus. Expect agreement with verified citations.",
    },
    {
        "label": "Beyond the sources",
        "query": "How did the logistics division perform in Q4 compared with the rest of the business?",
        "use_corpus": True,
        "note": "The corpus explicitly does not disclose this. Watch for models filling the gap.",
    },
    {
        "label": "No corpus",
        "query": "Is a company with three consecutive quarters of negative free cash flow a going-concern risk?",
        "use_corpus": False,
        "note": "Nothing to verify against, so every citation is labelled unverified.",
    },
]


@router.get("/examples")
def examples() -> dict:
    return {"examples": EXAMPLES, "corpus": _demo_corpus()}


@router.post("/query")
async def run_query(payload: TrustQuery) -> dict:
    try:
        client = await get_client()
    except Exception as exc:
        raise HTTPException(503, f"Temporal is unreachable: {str(exc)[:200]}") from exc

    try:
        return await client.execute_workflow(
            "TrustPanelWorkflow",
            {
                "query": payload.query,
                "corpus": payload.corpus,
                "tier": payload.tier,
            },
            id=f"trust-{uuid.uuid4()}",
            task_queue=TASK_QUEUE,
        )
    except Exception as exc:
        raise HTTPException(502, _unwrap(exc)) from exc


def _unwrap(exc: BaseException) -> str:
    """Temporal wraps the real error a few layers down inside ActivityError and
    ApplicationError. Surfacing the outermost one just tells the user "Activity
    task failed", which helps nobody debug a missing API key."""
    seen, current = [], exc
    for _ in range(6):
        text = str(current).strip()
        if text and text not in seen:
            seen.append(text)
        cause = getattr(current, "cause", None) or current.__cause__
        if cause is None:
            break
        current = cause
    return " <- ".join(seen)[:500] or "workflow failed"
