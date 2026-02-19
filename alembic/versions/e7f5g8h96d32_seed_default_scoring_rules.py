"""seed default scoring rules

Revision ID: e7f5g8h96d32
Revises: d6e4f7g85c21
Create Date: 2026-02-17 14:00:00.000000

Inserts the canonical set of scoring rules into ``lead_scoring_rules``
when the table is empty.  Uses INSERT … WHERE NOT EXISTS so the
migration is fully idempotent.

The rule values are derived from ``app.core.default_scoring_rules``.
Do NOT edit values here directly — update DEFAULT_SCORING_RULES in
that module, then regenerate this migration.
"""

from typing import Sequence, Union

import json
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "e7f5g8h96d32"
down_revision: Union[str, None] = "d6e4f7g85c21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# ---------------------------------------------------------------------------
# WARNING: These values are derived from DEFAULT_SCORING_RULES in
# app/core/default_scoring_rules.py.  Do not edit here directly.
# Add new rules to that module, then regenerate this migration.
# ---------------------------------------------------------------------------

# Import at migration-generation time so values stay in sync.
from app.core.default_scoring_rules import DEFAULT_SCORING_RULES  # noqa: E402


def upgrade() -> None:
    for rule in DEFAULT_SCORING_RULES:
        rule_name = rule["rule_name"].replace("'", "''")
        score_adj = rule["score_adjustment"]
        condition_json = json.dumps(rule["condition"]).replace("'", "''")

        op.execute(
            f"""
            INSERT INTO lead_scoring_rules (rule_name, score_adjustment, condition)
            SELECT '{rule_name}', {score_adj}, '{condition_json}'::jsonb
            WHERE NOT EXISTS (
                SELECT 1 FROM lead_scoring_rules
                WHERE rule_name = '{rule_name}'
            );
            """
        )


def downgrade() -> None:
    # Remove only the rules we seeded (by name)
    for rule in DEFAULT_SCORING_RULES:
        rule_name = rule["rule_name"].replace("'", "''")
        op.execute(f"DELETE FROM lead_scoring_rules WHERE rule_name = '{rule_name}';")
