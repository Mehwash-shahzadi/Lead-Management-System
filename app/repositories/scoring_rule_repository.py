import logging
from typing import List

from sqlalchemy import select, func

from app.models.scoring_rule import LeadScoringRule
from app.repositories.base import BaseRepository

logger = logging.getLogger(__name__)


class ScoringRuleRepository(BaseRepository):
    """Encapsulates queries against the ``lead_scoring_rules`` table."""

    async def get_active_rules(self) -> List[LeadScoringRule]:
        """Return all scoring rules ordered by rule_name."""
        result = await self._db.execute(
            select(LeadScoringRule).order_by(LeadScoringRule.rule_name)
        )
        return list(result.scalars().all())

    async def seed_if_empty(self) -> None:
        """Insert default scoring rules when the table is empty.

        Uses a row-count check so this is idempotent — calling it on a
        table that already has rules is a cheap no-op.

        The canonical rule definitions live in
        ``app.core.default_scoring_rules.DEFAULT_SCORING_RULES``.
        """
        from app.core.default_scoring_rules import DEFAULT_SCORING_RULES

        count_result = await self._db.execute(
            select(func.count()).select_from(LeadScoringRule)
        )
        if count_result.scalar():
            return  # rules already present

        logger.info("lead_scoring_rules table is empty — seeding defaults")
        for rule_data in DEFAULT_SCORING_RULES:
            self._db.add(LeadScoringRule(**rule_data))
        await self._db.flush()
        logger.info("Seeded %d default scoring rules", len(DEFAULT_SCORING_RULES))
