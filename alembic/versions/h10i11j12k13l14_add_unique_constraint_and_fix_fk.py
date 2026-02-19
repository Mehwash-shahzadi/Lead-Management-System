"""add unique constraint on property interests and fix agent_id FK

Revision ID: h10i11j12k13l14
Revises: g9h10i11j12k13
Create Date: 2026-02-18 10:00:00.000000

This migration:
  UPGRADE:
    1. Adds UNIQUE(lead_id, property_id) on ``lead_property_interests``
       to prevent duplicate interest records for the same lead+property.
    2. Drops and re-creates the ``agent_id`` FK on
       ``lead_conversion_history`` with ``ondelete='SET NULL'`` so that
       deleting an agent does not orphan conversion records.

  DOWNGRADE:
    1. Drops the UNIQUE constraint.
    2. Reverts the FK to plain (no ondelete action).
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "h10i11j12k13l14"
down_revision: Union[str, None] = "g9h10i11j12k13"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Unique constraint on lead_property_interests
    op.create_unique_constraint(
        "uq_lead_property_interest",
        "lead_property_interests",
        ["lead_id", "property_id"],
    )

    # 2. Fix agent_id FK on lead_conversion_history
    op.drop_constraint(
        "lead_conversion_history_agent_id_fkey",
        "lead_conversion_history",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "lead_conversion_history_agent_id_fkey",
        "lead_conversion_history",
        "agents",
        ["agent_id"],
        ["agent_id"],
        ondelete="SET NULL",
    )


def downgrade() -> None:
    # Revert FK to plain (no ondelete)
    op.drop_constraint(
        "lead_conversion_history_agent_id_fkey",
        "lead_conversion_history",
        type_="foreignkey",
    )
    op.create_foreign_key(
        "lead_conversion_history_agent_id_fkey",
        "lead_conversion_history",
        "agents",
        ["agent_id"],
        ["agent_id"],
    )

    # Drop unique constraint
    op.drop_constraint(
        "uq_lead_property_interest",
        "lead_property_interests",
        type_="unique",
    )
