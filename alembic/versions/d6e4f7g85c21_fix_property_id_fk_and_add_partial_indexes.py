"""fix property_id FK and add partial indexes

Revision ID: d6e4f7g85c21
Revises: c5d3e6f94b20
Create Date: 2026-02-17 10:00:00.000000

"""

from typing import Sequence, Union

from alembic import op
from sqlalchemy import text

# revision identifiers, used by Alembic.
revision: str = "d6e4f7g85c21"
down_revision: Union[str, None] = "c5d3e6f94b20"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ---------------------------------------------------------------
    # Fix #4: Remove incorrect FK on conversion_history.property_id
    # The column referenced leads.lead_id which is semantically wrong;
    # property_id should be an unchecked UUID (external property system).
    # ---------------------------------------------------------------
    op.drop_constraint(
        "fk_lch_property_id",
        "lead_conversion_history",
        type_="foreignkey",
    )

    # ---------------------------------------------------------------
    # Fix #5: Add partial / conditional indexes for common query
    # patterns on active leads and pending tasks.
    # ---------------------------------------------------------------

    # Partial index on active leads (status NOT IN 'converted','lost')
    # Used heavily by dashboard, assignment, and analytics queries.
    op.create_index(
        "ix_leads_active_status",
        "leads",
        ["status"],
        postgresql_where=text("status NOT IN ('converted', 'lost')"),
    )

    # Partial index on pending follow-up tasks
    op.create_index(
        "ix_follow_up_tasks_pending",
        "follow_up_tasks",
        ["agent_id", "due_date"],
        postgresql_where=text("status = 'pending'"),
    )

    # Partial index on high-score leads not yet converted (analytics 4.2)
    op.create_index(
        "ix_leads_high_score_not_converted",
        "leads",
        ["score"],
        postgresql_where=text("score > 80 AND status != 'converted'"),
    )


def downgrade() -> None:
    op.drop_index("ix_leads_high_score_not_converted", table_name="leads")
    op.drop_index("ix_follow_up_tasks_pending", table_name="follow_up_tasks")
    op.drop_index("ix_leads_active_status", table_name="leads")

    # Re-add the (incorrect) FK for rollback consistency
    op.create_foreign_key(
        "fk_lch_property_id",
        "lead_conversion_history",
        "leads",
        ["property_id"],
        ["lead_id"],
    )
