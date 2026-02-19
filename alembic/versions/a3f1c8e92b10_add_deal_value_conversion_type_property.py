"""add deal_value, conversion_type, property_id to lead_conversion_history

Revision ID: a3f1c8e92b10
Revises: 924be657aed4
Create Date: 2026-02-16 12:00:00.000000

"""

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = "a3f1c8e92b10"
down_revision = "924be657aed4"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # FIX: Add missing columns that analytics.py queries reference
    op.add_column(
        "lead_conversion_history",
        sa.Column("deal_value", sa.Numeric(precision=15, scale=2), nullable=True),
    )
    op.add_column(
        "lead_conversion_history",
        sa.Column("conversion_type", sa.String(length=20), nullable=True),
    )
    op.add_column(
        "lead_conversion_history",
        sa.Column("property_id", sa.UUID(), nullable=True),
    )
    op.create_foreign_key(
        "fk_lch_property_id",
        "lead_conversion_history",
        "leads",
        ["property_id"],
        ["lead_id"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "fk_lch_property_id", "lead_conversion_history", type_="foreignkey"
    )
    op.drop_column("lead_conversion_history", "property_id")
    op.drop_column("lead_conversion_history", "conversion_type")
    op.drop_column("lead_conversion_history", "deal_value")
