"""fix constraint name collision and add conversion_history CHECK constraints

Revision ID: i11j12k13l14m15
Revises: h10i11j12k13l14
Create Date: 2026-02-18 12:00:00.000000

This migration:
  UPGRADE:
    1. Renames ``ck_source_type`` on ``lead_sources`` to
       ``ck_lead_source_source_type`` to avoid a schema-level name
       collision with the identically-named constraint on ``leads``.
    2. Adds three CHECK constraints to ``lead_conversion_history``:
       - ``ck_conversion_type`` (sale / rental / lost)
       - ``ck_conversion_status_from``  (valid LEAD_STATUSES values)
       - ``ck_conversion_status_to``    (valid LEAD_STATUSES values)

  DOWNGRADE:
    Reverses all changes (drops new constraints, restores old name).
"""

from typing import Sequence, Union

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "i11j12k13l14m15"
down_revision: Union[str, None] = "h10i11j12k13l14"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Valid lead statuses — keep in sync with app.core.constants.LEAD_STATUSES
_LEAD_STATUSES_IN = (
    "'contacted', 'converted', 'lost', 'negotiation', "
    "'new', 'qualified', 'viewing_scheduled'"
)


def upgrade() -> None:
    # 1. Constraint rename on lead_sources is already applied in the
    #    initial schema migration (ck_lead_source_source_type), so we
    #    skip the drop/recreate here.

    # 2. Add CHECK constraints to lead_conversion_history
    op.create_check_constraint(
        "ck_conversion_type",
        "lead_conversion_history",
        "conversion_type IN ('sale', 'rental', 'lost')",
    )
    op.create_check_constraint(
        "ck_conversion_status_from",
        "lead_conversion_history",
        f"status_from IN ({_LEAD_STATUSES_IN})",
    )
    op.create_check_constraint(
        "ck_conversion_status_to",
        "lead_conversion_history",
        f"status_to IN ({_LEAD_STATUSES_IN})",
    )


def downgrade() -> None:
    # Remove conversion_history CHECK constraints
    op.drop_constraint(
        "ck_conversion_status_to", "lead_conversion_history", type_="check"
    )
    op.drop_constraint(
        "ck_conversion_status_from", "lead_conversion_history", type_="check"
    )
    op.drop_constraint("ck_conversion_type", "lead_conversion_history", type_="check")

    # Constraint rename on lead_sources is handled by initial schema
    # migration — nothing to revert here.
