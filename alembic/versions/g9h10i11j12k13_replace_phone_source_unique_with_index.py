"""replace phone+source_type UNIQUE constraint with composite index

Revision ID: g9h10i11j12k13
Revises: f8g9h10i11j12
Create Date: 2026-02-17 16:00:00.000000

The assessment spec requires duplicate lead detection within a 24-hour
window, NOT a permanent UNIQUE(phone, source_type) constraint.  A lead
from Bayut in January should be re-capturable in March as a fresh lead.

This migration:
  UPGRADE:
    1. Drops the hard UNIQUE constraint ``uq_phone_source``.
    2. Creates a composite index ``idx_leads_phone_source_created`` on
       (phone, source_type, created_at DESC) for efficient 24-hour
       duplicate lookups at the application level.

  DOWNGRADE:
    1. Drops the composite index.
    2. Re-creates the original UNIQUE constraint.

See ThinkRealty Backend Assessment — Error Handling § Duplicate Lead
Detection and Schema Business Rules.
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "g9h10i11j12k13"
down_revision: Union[str, None] = "f8g9h10i11j12"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Drop the permanent UNIQUE constraint — the business rule only
    #    blocks duplicates within a 24-hour window, enforced at the
    #    application level.
    op.drop_constraint("uq_phone_source", "leads", type_="unique")

    # 2. Create a composite index for fast duplicate-detection queries:
    #    SELECT … WHERE phone = :phone AND source_type = :source_type
    #                  AND created_at >= NOW() - INTERVAL '24 hours'
    op.create_index(
        "idx_leads_phone_source_created",
        "leads",
        ["phone", "source_type", "created_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_leads_phone_source_created", table_name="leads")
    op.create_unique_constraint("uq_phone_source", "leads", ["phone", "source_type"])
