"""initial tables

Revision ID: 0001
Revises:
Create Date: 2026-07-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "agents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=False, server_default=""),
        sa.Column("provider", sa.String(50), nullable=False, server_default="anthropic"),
        sa.Column("model", sa.String(200), nullable=False, server_default="claude-sonnet-5"),
        sa.Column("tools", sa.JSON(), nullable=False, server_default="[]"),
        sa.Column("knowledge_file_name", sa.String(500), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )

    op.create_table(
        "runs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("input_message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="running"),
        sa.Column("output_text", sa.Text(), nullable=True),
        sa.Column("temporal_workflow_id", sa.String(200), nullable=False),
        sa.Column("temporal_run_id", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_index("ix_runs_agent_id", "runs", ["agent_id"])


def downgrade() -> None:
    op.drop_index("ix_runs_agent_id", table_name="runs")
    op.drop_table("runs")
    op.drop_table("agents")
