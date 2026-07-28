"""conversations, messages, and the skills/tools split

Renames agents.description -> agents.role and agents.tools -> agents.skills so
existing agents survive, then adds a fresh agents.tools for the (currently
disabled) finance tool catalogue.

Revision ID: 0002
Revises: 0001
Create Date: 2026-07-28

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0002"
down_revision: Union[str, None] = "0001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # --- agents: rename in place so seeded rows keep their data ---
    op.alter_column("agents", "description", new_column_name="role")
    op.alter_column("agents", "tools", new_column_name="skills")
    op.add_column(
        "agents",
        sa.Column("tools", sa.JSON(), nullable=False, server_default="[]"),
    )

    # name / role / model are mandatory going forward; backfill blanks first.
    op.execute("UPDATE agents SET role = 'No role described' WHERE role IS NULL OR role = ''")
    op.execute("UPDATE agents SET name = 'Untitled agent' WHERE name IS NULL OR name = ''")
    op.execute("UPDATE agents SET model = 'claude-opus-5' WHERE model IS NULL OR model = ''")
    op.alter_column("agents", "role", nullable=False)
    op.alter_column("agents", "name", nullable=False)
    op.alter_column("agents", "model", nullable=False)

    op.create_table(
        "conversations",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "agent_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("agents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(300), nullable=False, server_default="New chat"),
        sa.Column("temporal_workflow_id", sa.String(200), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("last_message_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_conversations_agent_id", "conversations", ["agent_id"])
    op.create_index("ix_conversations_last_message_at", "conversations", ["last_message_at"])

    op.create_table(
        "messages",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("role", sa.String(20), nullable=False),
        sa.Column("content", sa.Text(), nullable=False, server_default=""),
        sa.Column("tool_name", sa.String(100), nullable=True),
        sa.Column("tool_use_id", sa.String(100), nullable=True),
        sa.Column("seq", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
    )
    op.create_index("ix_messages_conversation_id", "messages", ["conversation_id"])

    op.add_column(
        "runs",
        sa.Column(
            "conversation_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("conversations.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("runs", "conversation_id")
    op.drop_index("ix_messages_conversation_id", table_name="messages")
    op.drop_table("messages")
    op.drop_index("ix_conversations_last_message_at", table_name="conversations")
    op.drop_index("ix_conversations_agent_id", table_name="conversations")
    op.drop_table("conversations")
    op.drop_column("agents", "tools")
    op.alter_column("agents", "skills", new_column_name="tools")
    op.alter_column("agents", "role", new_column_name="description")
