"""scheduled tasks

Recurring background tasks created by a tool call mid-conversation (e.g.
schedule_task -> a Temporal Schedule). temporal_schedule_id is not a DB-level
unique constraint because the worker upserts by that id — a second call for
the same conversation is meant to update the row, not conflict with it.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-25

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0003"
down_revision: Union[str, None] = "0002"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "scheduled_tasks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("task_type", sa.String(50), nullable=False),
        sa.Column("temporal_schedule_id", sa.String(200), nullable=False),
        sa.Column("params", sa.JSON(), nullable=False, server_default="{}"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_scheduled_tasks_conversation_id", "scheduled_tasks", ["conversation_id"])
    op.create_index(
        "ix_scheduled_tasks_temporal_schedule_id", "scheduled_tasks", ["temporal_schedule_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_scheduled_tasks_temporal_schedule_id", table_name="scheduled_tasks")
    op.drop_index("ix_scheduled_tasks_conversation_id", table_name="scheduled_tasks")
    op.drop_table("scheduled_tasks")
