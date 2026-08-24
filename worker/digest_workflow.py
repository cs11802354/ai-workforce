from datetime import timedelta

from temporalio import workflow
from temporalio.common import RetryPolicy

with workflow.unsafe.imports_passed_through():
    from digest_activities import (
        fetch_articles_activity,
        send_digest_email_activity,
        summarize_digest_activity,
    )


@workflow.defn(name="DailyDigestWorkflow")
class DailyDigestWorkflow:
    """One run per schedule trigger: fetch candidate articles, have the model
    curate/summarize a ~30-minute digest, email it. No retry loop across the
    whole thing — each activity has its own retry policy, and a failed run
    just waits for tomorrow's trigger rather than being redone same-day."""

    @workflow.run
    async def run(self, topics: list[str] | None = None, recipient_email: str | None = None) -> str:
        articles = await workflow.execute_activity(
            fetch_articles_activity,
            topics,
            start_to_close_timeout=timedelta(minutes=2),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )

        if not articles:
            return "no_articles"

        html = await workflow.execute_activity(
            summarize_digest_activity,
            args=[articles, topics],
            start_to_close_timeout=timedelta(minutes=3),
            retry_policy=RetryPolicy(maximum_attempts=2),
        )

        return await workflow.execute_activity(
            send_digest_email_activity,
            args=[html, recipient_email],
            start_to_close_timeout=timedelta(minutes=1),
            retry_policy=RetryPolicy(maximum_attempts=3),
        )
