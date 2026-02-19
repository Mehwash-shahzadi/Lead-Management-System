import logging
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
from uuid import UUID

from app.repositories.activity_repository import ActivityRepository
from app.repositories.lead_repository import LeadRepository
from app.repositories.scoring_rule_repository import ScoringRuleRepository

logger = logging.getLogger(__name__)

# Neutral fallback score used when the DB is genuinely unreachable
_NEUTRAL_FALLBACK_SCORE = 50


class LeadScoringEngine:
    """Calculate and update lead scores based on business rules.

    Rules are loaded from the ``lead_scoring_rules`` table when a
    ``ScoringRuleRepository`` is provided.  Each rule has a JSONB
    ``condition`` and an integer ``score_adjustment``.

    Supported condition types (matched by ``condition.type``):
        - ``budget_min``   lead's budget_max must be > condition.threshold
        - ``source``       lead's source_type must == condition.value
        - ``nationality``  lead's nationality must match condition.value(s)
        - ``property_type``  lead must have a property_type set
        - ``preferred_areas``  lead must have preferred_areas set
        - ``referral``     source_details must include referrer_agent_id

    When multiple ``budget_min`` rules exist they are evaluated
    highest-threshold-first and only the **first** match applies (tiered).
    """

    def __init__(
        self,
        scoring_rule_repo: Optional[ScoringRuleRepository] = None,
        activity_repo: Optional[ActivityRepository] = None,
    ) -> None:
        self._rule_repo = scoring_rule_repo
        self._activity_repo = activity_repo
        self._rules_seeded = False

    async def _ensure_rules_seeded(self) -> None:
        """Seed default scoring rules into the DB if the table is empty.

        Called once per engine lifetime.  The actual rule definitions
        live in ``app.core.default_scoring_rules.DEFAULT_SCORING_RULES``.
        """
        if self._rules_seeded or self._rule_repo is None:
            return
        try:
            await self._rule_repo.seed_if_empty()
            self._rules_seeded = True
        except Exception:
            logger.warning("Failed to seed scoring rules into DB")

    async def calculate_lead_score(
        self,
        lead_data: Dict[str, Any],
        source_details: Dict[str, Any],
    ) -> int:
        """Score a lead based on budget, source, nationality, etc.

        All scoring is driven exclusively by rules stored in the
        ``lead_scoring_rules`` database table.  If the DB is
        unreachable a neutral fallback score is returned.
        """
        await self._ensure_rules_seeded()

        db_rules: List = []
        if self._rule_repo is not None:
            try:
                db_rules = await self._rule_repo.get_active_rules()
            except Exception:
                logger.warning("Failed to read scoring rules from DB")

        if db_rules:
            score = self._score_from_db_rules(lead_data, source_details, db_rules)
        else:
            return await self._apply_default_scoring()

        # Response time to initial contact (ThinkRealty Assessment Task 3.1)
        lead_id = lead_data.get("lead_id")
        lead_created_at = lead_data.get("created_at")
        response_bonus = await self._calculate_response_time_bonus(
            lead_id=lead_id,
            lead_created_at=lead_created_at,
            db_rules=db_rules,
        )
        score += response_bonus

        # Final clamp — must be the LAST operation
        return min(100, max(0, score))

    def _score_from_db_rules(
        self,
        lead_data: Dict[str, Any],
        source_details: Dict[str, Any],
        rules: List,
    ) -> int:
        """Apply scoring rules loaded from the database."""
        score = 0
        budget_max = lead_data.get("budget_max")
        source_type = source_details.get("source_type", "").lower()
        nationality = (lead_data.get("nationality") or "").lower()

        # Separate budget rules (tiered – highest threshold first)
        budget_rules = sorted(
            [r for r in rules if (r.condition or {}).get("type") == "budget_min"],
            key=lambda r: r.condition.get("threshold", 0),
            reverse=True,
        )
        budget_applied = False

        for rule in budget_rules:
            threshold = rule.condition.get("threshold", 0)
            if budget_max and float(budget_max) > threshold and not budget_applied:
                score += rule.score_adjustment
                budget_applied = True

        # Non-budget rules
        for rule in rules:
            cond = rule.condition or {}
            ctype = cond.get("type")

            if ctype == "budget_min":
                continue  # already handled above

            if ctype == "source":
                expected = cond.get("value", "").lower()
                if source_type == expected:
                    score += rule.score_adjustment

            elif ctype == "nationality":
                values = cond.get("values", [])
                if any(v.lower() in nationality for v in values):
                    score += rule.score_adjustment

            elif ctype == "property_type":
                if lead_data.get("property_type"):
                    score += rule.score_adjustment

            elif ctype == "preferred_areas":
                if lead_data.get("preferred_areas"):
                    score += rule.score_adjustment

            elif ctype == "referral":
                if source_details.get("referrer_agent_id"):
                    score += rule.score_adjustment
        return score

    async def _calculate_response_time_bonus(
        self,
        lead_id: Optional[UUID],
        lead_created_at: Optional[datetime],
        db_rules: Optional[List] = None,
    ) -> int:
        if lead_id is None or self._activity_repo is None:
            return 0

        first_contact = await self._activity_repo.find_first_contact_activity(
            lead_id=lead_id
        )

        if first_contact is None:
            # No contact yet — check how long ago lead was created
            if lead_created_at is None:
                return 0
            hours_elapsed = (
                datetime.now(timezone.utc) - lead_created_at
            ).total_seconds() / 3600
            return -10 if hours_elapsed > 72 else 0

        if lead_created_at is None:
            return 0

        response_hours = (
            first_contact.activity_at - lead_created_at
        ).total_seconds() / 3600

        # Use DB rules if available
        if db_rules:
            return self._calc_response_time_adjustment(response_hours, db_rules)

        # Fallback tiers
        if response_hours <= 1:
            return 15
        elif response_hours <= 4:
            return 10
        elif response_hours <= 24:
            return 5
        elif response_hours <= 72:
            return 0
        else:
            return -10

    async def _apply_default_scoring(self) -> int:
        """Return a neutral score when the lead_scoring_rules table is unreachable."""
        logger.warning("lead_scoring_rules table unreachable, using neutral score")
        return _NEUTRAL_FALLBACK_SCORE

    async def update_lead_score(
        self,
        lead_id: UUID,
        activity_data: Dict[str, Any],
        lead_repo: LeadRepository,
        last_activity_at: Optional[datetime] = None,
    ) -> int:
        await self._ensure_rules_seeded()

        current_score = await lead_repo.get_score(lead_id)

        # ----- Load activity-related rules from DB --------------------
        db_rules: List = []
        if self._rule_repo is not None:
            try:
                db_rules = await self._rule_repo.get_active_rules()
            except Exception:
                logger.warning("Failed to read scoring rules from DB")

        adjustment = 0
        activity_type = activity_data.get("type")
        outcome = activity_data.get("outcome")

        # Apply activity rules from DB
        for rule in db_rules:
            cond = rule.condition or {}
            ctype = cond.get("type")

            if ctype == "activity_outcome" and outcome == cond.get("value"):
                adjustment += rule.score_adjustment
            elif ctype == "activity_type" and activity_type == cond.get("value"):
                adjustment += rule.score_adjustment
            elif ctype == "inactivity_days":
                threshold = cond.get("threshold", 7)
                if last_activity_at is not None:
                    days_since = (datetime.now(timezone.utc) - last_activity_at).days
                    if days_since >= threshold:
                        adjustment += rule.score_adjustment

        if not db_rules:
            if outcome == "positive":
                adjustment += 5
            if activity_type == "viewing":
                adjustment += 10
            if activity_type == "offer_made":
                adjustment += 20
            if last_activity_at is not None:
                days_since_last = (datetime.now(timezone.utc) - last_activity_at).days
                if days_since_last >= 7:
                    adjustment -= 10

        if self._activity_repo is not None:
            activity_count = await self._activity_repo.get_activity_count(lead_id)
        else:
            activity_count = 0

        if activity_count == 1:
            lead = await lead_repo.get_by_id(lead_id)
            if lead and lead.created_at:
                first_activity_at = (
                    await self._activity_repo.get_first_activity_at(lead_id)
                    if self._activity_repo is not None
                    else None
                )

                if first_activity_at:
                    response_hours = (
                        first_activity_at - lead.created_at
                    ).total_seconds() / 3600

                    # Apply response-time rules from DB
                    response_adj = self._calc_response_time_adjustment(
                        response_hours, db_rules
                    )
                    adjustment += response_adj

        new_score = min(100, max(0, current_score + adjustment))
        await lead_repo.update_score(lead_id, new_score)

        return new_score

    @staticmethod
    def _calc_response_time_adjustment(response_hours: float, db_rules: List) -> int:
        rt_rules = sorted(
            [r for r in db_rules if (r.condition or {}).get("type") == "response_time"],
            key=lambda r: r.condition.get("max_hours", float("inf")),
        )

        if rt_rules:
            for rule in rt_rules:
                cond = rule.condition
                max_h = cond.get("max_hours")
                min_h = cond.get("min_hours")
                if max_h is not None and response_hours <= max_h:
                    return rule.score_adjustment
                if min_h is not None and response_hours > min_h:
                    return rule.score_adjustment
            return 0

        # Fallback if DB unreachable
        if response_hours <= 1:
            return 15
        elif response_hours <= 4:
            return 10
        elif response_hours <= 24:
            return 5
        elif response_hours <= 72:
            return 0
        else:
            return -10
