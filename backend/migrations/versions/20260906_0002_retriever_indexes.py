"""Add indexes used by Retriever filters.

Revision ID: 20260906_0002
Revises: 20260905_0001
"""

from collections.abc import Sequence

from alembic import op

revision: str = "20260906_0002"
down_revision: str | None = "20260905_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.execute("CREATE INDEX ix_startups_sector_lower ON startups (lower(sector))")
    op.execute("CREATE INDEX ix_startups_stage_lower ON startups (lower(stage))")
    op.execute("CREATE INDEX ix_startups_location_lower ON startups (lower(location))")
    op.create_index("ix_startups_team_size", "startups", ["team_size"])


def downgrade() -> None:
    op.drop_index("ix_startups_team_size", table_name="startups")
    op.drop_index("ix_startups_location_lower", table_name="startups")
    op.drop_index("ix_startups_stage_lower", table_name="startups")
    op.drop_index("ix_startups_sector_lower", table_name="startups")
