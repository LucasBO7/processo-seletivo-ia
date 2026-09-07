"""Add versioned NVIDIA knowledge ingestion metadata.

Revision ID: 20260907_0003
Revises: 20260906_0002
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20260907_0003"
down_revision: str | None = "20260906_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("knowledge_documents", sa.Column("source_key", sa.String(120)))
    op.add_column("knowledge_documents", sa.Column("technology", sa.String(80)))
    op.add_column(
        "knowledge_documents",
        sa.Column("revision", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column("pipeline_version", sa.String(40), nullable=False, server_default="legacy-v1"),
    )
    op.add_column(
        "knowledge_documents",
        sa.Column(
            "ingested_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.execute("UPDATE knowledge_documents SET source_key = 'legacy-' || id::text")
    op.execute("UPDATE knowledge_documents SET technology = 'unknown'")
    op.alter_column("knowledge_documents", "source_key", nullable=False)
    op.alter_column("knowledge_documents", "technology", nullable=False)
    op.execute(
        "ALTER TABLE knowledge_documents "
        "DROP CONSTRAINT IF EXISTS knowledge_documents_content_hash_key"
    )
    op.create_unique_constraint(
        "uq_knowledge_documents_source_key", "knowledge_documents", ["source_key"]
    )
    op.create_index("ix_knowledge_documents_source_key", "knowledge_documents", ["source_key"])
    op.create_index("ix_knowledge_documents_technology", "knowledge_documents", ["technology"])
    op.create_index("ix_knowledge_documents_content_hash", "knowledge_documents", ["content_hash"])


def downgrade() -> None:
    op.drop_index("ix_knowledge_documents_content_hash", table_name="knowledge_documents")
    op.drop_index("ix_knowledge_documents_technology", table_name="knowledge_documents")
    op.drop_index("ix_knowledge_documents_source_key", table_name="knowledge_documents")
    op.drop_constraint("uq_knowledge_documents_source_key", "knowledge_documents", type_="unique")
    # The former global hash uniqueness cannot be restored without discarding
    # valid documents from distinct sources that share content.
    op.drop_column("knowledge_documents", "ingested_at")
    op.drop_column("knowledge_documents", "pipeline_version")
    op.drop_column("knowledge_documents", "revision")
    op.drop_column("knowledge_documents", "technology")
    op.drop_column("knowledge_documents", "source_key")
