"""add missing indexes for property_id and source_type queries

Revision ID: j12k13l14m15n16
Revises: i11j12k13l14m15
Create Date: 2026-02-18 14:00:00.000000

This migration adds two indexes that were missing for common query patterns:
  - ix_property_interests_property_id on lead_property_interests.property_id
    (used by find_suggestions GROUP BY property_id)
  - ix_lead_sources_source_type on lead_sources.source_type
    (used by analytics queries filtering by source_type)
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "j12k13l14m15n16"
down_revision: Union[str, None] = "i11j12k13l14m15"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "ix_property_interests_property_id",
        "lead_property_interests",
        ["property_id"],
    )
    op.create_index(
        "ix_lead_sources_source_type",
        "lead_sources",
        ["source_type"],
    )


def downgrade() -> None:
    op.drop_index("ix_lead_sources_source_type", table_name="lead_sources")
    op.drop_index(
        "ix_property_interests_property_id", table_name="lead_property_interests"
    )
