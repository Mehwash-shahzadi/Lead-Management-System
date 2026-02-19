"""add budget_min lt budget_max check constraint

Revision ID: f8g9h10i11j12
Revises: e7f8g9h10i11
Create Date: 2026-02-17 10:05:00.000000

"""

from alembic import op

# revision identifiers, used by Alembic.
revision = "f8g9h10i11j12"
down_revision = "e7f8g9h10i11"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_check_constraint(
        "ck_budget_min_lt_max",
        "leads",
        "budget_min IS NULL OR budget_max IS NULL OR budget_min < budget_max",
    )


def downgrade() -> None:
    op.drop_constraint("ck_budget_min_lt_max", "leads", type_="check")
