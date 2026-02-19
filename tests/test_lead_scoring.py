import pytest
from unittest.mock import AsyncMock, MagicMock

from app.services.lead_scoring import LeadScoringEngine
from app.core.default_scoring_rules import DEFAULT_SCORING_RULES


def _mock_rules_from_defaults():

    rules = []
    for rd in DEFAULT_SCORING_RULES:
        rule = MagicMock()
        rule.condition = rd["condition"]
        rule.score_adjustment = rd["score_adjustment"]
        rule.is_active = True
        rules.append(rule)
    return rules


def _mock_scoring_repo():
    """Create a mocked ScoringRuleRepository returning default rules."""
    repo = AsyncMock()
    repo.seed_if_empty = AsyncMock()
    repo.get_active_rules = AsyncMock(return_value=_mock_rules_from_defaults())
    return repo


@pytest.fixture
def engine() -> LeadScoringEngine:
    """Engine with no repos — hits neutral fallback for calculate_lead_score."""
    return LeadScoringEngine()


@pytest.fixture
def engine_with_rules() -> LeadScoringEngine:
    """Engine backed by mocked scoring rule repo (default rules loaded)."""
    return LeadScoringEngine(scoring_rule_repo=_mock_scoring_repo())


class TestCalculateLeadScore:
    """Verify initial scoring for newly captured leads."""

    @pytest.mark.asyncio
    async def test_high_budget_uae_bayut_lead(
        self, engine_with_rules: LeadScoringEngine
    ):
        """A premium UAE lead from Bayut should score very high."""
        lead_data = {
            "budget_max": 12_000_000,
            "nationality": "UAE",
            "property_type": "villa",
            "preferred_areas": ["Palm Jumeirah"],
        }
        source_details = {"source_type": "bayut"}

        score = await engine_with_rules.calculate_lead_score(lead_data, source_details)

        # budget(20) + bayut(90) + UAE(10) + property(5) + areas(5) = 130 → clamped 100
        assert score == 100

    @pytest.mark.asyncio
    async def test_low_budget_walk_in_lead(self, engine_with_rules: LeadScoringEngine):
        """A walk-in lead with a modest budget should score lower."""
        lead_data = {
            "budget_max": 500_000,
            "nationality": "India",
            "property_type": "apartment",
            "preferred_areas": ["JBR"],
        }
        source_details = {"source_type": "walk_in"}

        score = await engine_with_rules.calculate_lead_score(lead_data, source_details)

        # budget(5) + walk_in(70) + property(5) + areas(5) = 85
        assert score == 85

    @pytest.mark.asyncio
    async def test_gcc_nationality_bonus(self, engine_with_rules: LeadScoringEngine):
        """GCC nationals (non-UAE) receive a +5 bonus."""
        lead_data = {
            "budget_max": 1_000_000,
            "nationality": "Saudi Arabia",
        }
        source_details = {"source_type": "website"}

        score = await engine_with_rules.calculate_lead_score(lead_data, source_details)

        # budget(5) + website(80) + Saudi(5) = 90
        assert score == 90

    @pytest.mark.asyncio
    async def test_referral_bonus(self, engine_with_rules: LeadScoringEngine):
        """A referral with a referrer_agent_id gets +10."""
        lead_data = {
            "budget_max": 3_000_000,
            "nationality": "UK",
            "property_type": "townhouse",
            "preferred_areas": ["Dubai Hills"],
        }
        source_details = {
            "source_type": "referral",
            "referrer_agent_id": "some-uuid",
        }

        score = await engine_with_rules.calculate_lead_score(lead_data, source_details)

        # budget(10) + referral(95) + property(5) + areas(5) + referrer(10) = 125 → clamped 100
        assert score == 100

    @pytest.mark.asyncio
    async def test_score_never_negative(self, engine: LeadScoringEngine):
        """Score must be ≥ 0 even with minimal data."""
        lead_data = {}
        source_details = {}

        score = await engine.calculate_lead_score(lead_data, source_details)

        # fallback source score = 50, nothing else
        assert score == 50
        assert score >= 0

    @pytest.mark.asyncio
    async def test_score_clamped_at_100(self, engine_with_rules: LeadScoringEngine):
        """Score must never exceed 100."""
        lead_data = {
            "budget_max": 20_000_000,
            "nationality": "UAE",
            "property_type": "villa",
            "preferred_areas": ["Downtown"],
        }
        source_details = {
            "source_type": "referral",
            "referrer_agent_id": "uuid",
        }

        score = await engine_with_rules.calculate_lead_score(lead_data, source_details)
        assert score <= 100

    @pytest.mark.asyncio
    async def test_propertyfinder_case_insensitive(
        self, engine_with_rules: LeadScoringEngine
    ):
        """propertyFinder (camelCase) must resolve to 85, not the fallback 50."""
        lead_data = {"budget_max": 1_000_000}
        source_details = {"source_type": "propertyFinder"}

        score = await engine_with_rules.calculate_lead_score(lead_data, source_details)

        # budget(5) + propertyFinder(85) = 90
        assert score == 90


class TestUpdateLeadScore:
    """Verify score adjustments after activities."""

    @pytest.mark.asyncio
    async def test_positive_outcome_adds_5(self, engine: LeadScoringEngine):
        """A positive interaction should add +5."""
        from unittest.mock import AsyncMock

        mock_repo = AsyncMock()
        mock_repo.get_score = AsyncMock(return_value=50)
        mock_repo.update_score = AsyncMock()

        new_score = await engine.update_lead_score(
            lead_id="fake-uuid",
            activity_data={"type": "call", "outcome": "positive"},
            lead_repo=mock_repo,
        )

        assert new_score == 55
        mock_repo.update_score.assert_awaited_once_with("fake-uuid", 55)

    @pytest.mark.asyncio
    async def test_viewing_adds_10(self, engine: LeadScoringEngine):
        """A property viewing adds +10."""
        from unittest.mock import AsyncMock

        mock_repo = AsyncMock()
        mock_repo.get_score = AsyncMock(return_value=40)
        mock_repo.update_score = AsyncMock()

        new_score = await engine.update_lead_score(
            lead_id="fake-uuid",
            activity_data={"type": "viewing", "outcome": "neutral"},
            lead_repo=mock_repo,
        )

        assert new_score == 50

    @pytest.mark.asyncio
    async def test_offer_made_adds_20(self, engine: LeadScoringEngine):
        """An offer_made activity adds +20."""
        from unittest.mock import AsyncMock

        mock_repo = AsyncMock()
        mock_repo.get_score = AsyncMock(return_value=60)
        mock_repo.update_score = AsyncMock()

        new_score = await engine.update_lead_score(
            lead_id="fake-uuid",
            activity_data={"type": "offer_made", "outcome": "neutral"},
            lead_repo=mock_repo,
        )

        assert new_score == 80

    @pytest.mark.asyncio
    async def test_seven_day_inactivity_penalty(self, engine: LeadScoringEngine):
        """7+ days of inactivity should subtract 10 points."""
        from datetime import datetime, timedelta, timezone
        from unittest.mock import AsyncMock

        mock_repo = AsyncMock()
        mock_repo.get_score = AsyncMock(return_value=50)
        mock_repo.update_score = AsyncMock()

        old_activity = datetime.now(timezone.utc) - timedelta(days=8)

        new_score = await engine.update_lead_score(
            lead_id="fake-uuid",
            activity_data={"type": "call", "outcome": "negative"},
            lead_repo=mock_repo,
            last_activity_at=old_activity,
        )

        # no positive adjustments, -10 for inactivity
        assert new_score == 40

    @pytest.mark.asyncio
    async def test_score_does_not_go_below_zero(self, engine: LeadScoringEngine):
        """Score must be clamped at 0 after penalties."""
        from datetime import datetime, timedelta, timezone
        from unittest.mock import AsyncMock

        mock_repo = AsyncMock()
        mock_repo.get_score = AsyncMock(return_value=5)
        mock_repo.update_score = AsyncMock()

        old_activity = datetime.now(timezone.utc) - timedelta(days=10)

        new_score = await engine.update_lead_score(
            lead_id="fake-uuid",
            activity_data={"type": "call", "outcome": "negative"},
            lead_repo=mock_repo,
            last_activity_at=old_activity,
        )

        assert new_score == 0


class TestResponseTimeScoring:
    """Verify response-time bonus/penalty on first activity only."""

    @staticmethod
    def _build_mock_repo(
        current_score: int,
        activity_count: int,
        lead_created_at,
        first_activity_at=None,
    ):
        """Create a mock LeadRepository wired for response-time tests.

        ``activity_count`` controls whether the response-time logic
        fires (only when == 1).
        """
        from unittest.mock import AsyncMock, MagicMock

        mock_repo = AsyncMock()
        mock_repo.get_score = AsyncMock(return_value=current_score)
        mock_repo.update_score = AsyncMock()

        # lead_repo.get_by_id → lead with created_at
        mock_lead = MagicMock()
        mock_lead.created_at = lead_created_at
        mock_repo.get_by_id = AsyncMock(return_value=mock_lead)

        return mock_repo

    @staticmethod
    def _build_mock_activity_repo(activity_count: int, first_activity_at=None):
        """Create a mock ActivityRepository for response-time tests."""
        from unittest.mock import AsyncMock

        mock_activity_repo = AsyncMock()
        mock_activity_repo.get_activity_count = AsyncMock(return_value=activity_count)
        mock_activity_repo.get_first_activity_at = AsyncMock(
            return_value=first_activity_at
        )
        return mock_activity_repo

    @staticmethod
    def _make_engine_with_activity_repo(activity_repo):
        """Create a LeadScoringEngine with a mock activity repo."""
        return LeadScoringEngine(activity_repo=activity_repo)

    @pytest.mark.asyncio
    async def test_response_time_under_1_hour_adds_15_points(
        self, engine: LeadScoringEngine
    ):
        """Agent responded within 1 hour → +15."""
        from datetime import datetime, timedelta, timezone

        created = datetime(2026, 2, 17, 10, 0, tzinfo=timezone.utc)
        first_act = created + timedelta(minutes=30)  # 0.5 hours

        mock_activity_repo = self._build_mock_activity_repo(
            activity_count=1, first_activity_at=first_act
        )
        test_engine = self._make_engine_with_activity_repo(mock_activity_repo)
        mock_repo = self._build_mock_repo(
            current_score=50,
            activity_count=1,
            lead_created_at=created,
            first_activity_at=first_act,
        )

        score = await test_engine.update_lead_score(
            lead_id="fake-uuid",
            activity_data={"type": "call", "outcome": "neutral"},
            lead_repo=mock_repo,
        )

        # base 50 + 0 (neutral) + 15 (response ≤1h) = 65
        assert score == 65

    @pytest.mark.asyncio
    async def test_response_time_under_4_hours_adds_10_points(
        self, engine: LeadScoringEngine
    ):
        """Agent responded within 4 hours → +10."""
        from datetime import datetime, timedelta, timezone

        created = datetime(2026, 2, 17, 10, 0, tzinfo=timezone.utc)
        first_act = created + timedelta(hours=3)  # 3 hours

        mock_activity_repo = self._build_mock_activity_repo(
            activity_count=1, first_activity_at=first_act
        )
        test_engine = self._make_engine_with_activity_repo(mock_activity_repo)
        mock_repo = self._build_mock_repo(
            current_score=50,
            activity_count=1,
            lead_created_at=created,
            first_activity_at=first_act,
        )

        score = await test_engine.update_lead_score(
            lead_id="fake-uuid",
            activity_data={"type": "call", "outcome": "neutral"},
            lead_repo=mock_repo,
        )

        # base 50 + 0 + 10 (response ≤4h) = 60
        assert score == 60

    @pytest.mark.asyncio
    async def test_response_time_under_24_hours_adds_5_points(
        self, engine: LeadScoringEngine
    ):
        """Agent responded within 24 hours → +5."""
        from datetime import datetime, timedelta, timezone

        created = datetime(2026, 2, 17, 10, 0, tzinfo=timezone.utc)
        first_act = created + timedelta(hours=12)  # 12 hours

        mock_activity_repo = self._build_mock_activity_repo(
            activity_count=1, first_activity_at=first_act
        )
        test_engine = self._make_engine_with_activity_repo(mock_activity_repo)
        mock_repo = self._build_mock_repo(
            current_score=50,
            activity_count=1,
            lead_created_at=created,
            first_activity_at=first_act,
        )

        score = await test_engine.update_lead_score(
            lead_id="fake-uuid",
            activity_data={"type": "call", "outcome": "neutral"},
            lead_repo=mock_repo,
        )

        # base 50 + 0 + 5 (response ≤24h) = 55
        assert score == 55

    @pytest.mark.asyncio
    async def test_response_time_over_72_hours_subtracts_10_points(
        self, engine: LeadScoringEngine
    ):
        """Agent responded after 72 hours → -10."""
        from datetime import datetime, timedelta, timezone

        created = datetime(2026, 2, 17, 10, 0, tzinfo=timezone.utc)
        first_act = created + timedelta(hours=80)  # 80 hours

        mock_activity_repo = self._build_mock_activity_repo(
            activity_count=1, first_activity_at=first_act
        )
        test_engine = self._make_engine_with_activity_repo(mock_activity_repo)
        mock_repo = self._build_mock_repo(
            current_score=50,
            activity_count=1,
            lead_created_at=created,
            first_activity_at=first_act,
        )

        score = await test_engine.update_lead_score(
            lead_id="fake-uuid",
            activity_data={"type": "call", "outcome": "neutral"},
            lead_repo=mock_repo,
        )

        # base 50 + 0 - 10 (response > 72h) = 40
        assert score == 40

    @pytest.mark.asyncio
    async def test_response_time_not_applied_on_second_activity(
        self, engine: LeadScoringEngine
    ):
        """Second activity must NOT trigger the response-time bonus."""
        from datetime import datetime, timezone

        created = datetime(2026, 2, 17, 10, 0, tzinfo=timezone.utc)

        mock_activity_repo = self._build_mock_activity_repo(
            activity_count=2,  # second activity — guard skips
        )
        test_engine = self._make_engine_with_activity_repo(mock_activity_repo)
        mock_repo = self._build_mock_repo(
            current_score=50,
            activity_count=2,  # second activity — guard skips
            lead_created_at=created,
        )

        score = await test_engine.update_lead_score(
            lead_id="fake-uuid",
            activity_data={"type": "call", "outcome": "neutral"},
            lead_repo=mock_repo,
        )

        # base 50 + 0 (neutral call, no response-time delta) = 50
        assert score == 50

    @pytest.mark.asyncio
    async def test_score_clamped_at_100_maximum(self, engine: LeadScoringEngine):
        """Score must not exceed 100 even with response-time + activity bonus."""
        from datetime import datetime, timedelta, timezone

        created = datetime(2026, 2, 17, 10, 0, tzinfo=timezone.utc)
        first_act = created + timedelta(minutes=20)  # < 1h → +15

        mock_activity_repo = self._build_mock_activity_repo(
            activity_count=1, first_activity_at=first_act
        )
        test_engine = self._make_engine_with_activity_repo(mock_activity_repo)
        mock_repo = self._build_mock_repo(
            current_score=95,
            activity_count=1,
            lead_created_at=created,
            first_activity_at=first_act,
        )

        score = await test_engine.update_lead_score(
            lead_id="fake-uuid",
            activity_data={"type": "viewing", "outcome": "positive"},
            lead_repo=mock_repo,
        )

        # 95 + 5 (positive) + 10 (viewing) + 15 (response ≤1h) = 125 → clamped 100
        assert score == 100

    @pytest.mark.asyncio
    async def test_score_clamped_at_0_minimum(self, engine: LeadScoringEngine):
        """Score must not go below 0 even with response-time penalty."""
        from datetime import datetime, timedelta, timezone

        created = datetime(2026, 2, 17, 10, 0, tzinfo=timezone.utc)
        first_act = created + timedelta(hours=80)  # > 72h → -10

        mock_activity_repo = self._build_mock_activity_repo(
            activity_count=1, first_activity_at=first_act
        )
        test_engine = self._make_engine_with_activity_repo(mock_activity_repo)
        mock_repo = self._build_mock_repo(
            current_score=3,
            activity_count=1,
            lead_created_at=created,
            first_activity_at=first_act,
        )

        score = await test_engine.update_lead_score(
            lead_id="fake-uuid",
            activity_data={"type": "call", "outcome": "negative"},
            lead_repo=mock_repo,
        )

        # 3 + 0 - 10 (response > 72h) = -7 → clamped 0
        assert score == 0


# ---------------------------------------------------------------------------
# Response time bonus in calculate_lead_score (Task 3.1)
# ---------------------------------------------------------------------------


class TestCalculateLeadScoreResponseTime:
    @staticmethod
    def _make_rule(condition: dict, score_adjustment: int):
        """Create a mock scoring rule with given condition and adjustment."""
        from unittest.mock import MagicMock

        rule = MagicMock()
        rule.condition = condition
        rule.score_adjustment = score_adjustment
        rule.is_active = True
        return rule

    @staticmethod
    def _build_engine(first_contact_activity=None, rules=None):
        from unittest.mock import AsyncMock

        scoring_repo = AsyncMock()
        scoring_repo.seed_if_empty = AsyncMock()
        scoring_repo.get_active_rules = AsyncMock(
            return_value=rules if rules is not None else []
        )

        activity_repo = AsyncMock()
        activity_repo.find_first_contact_activity = AsyncMock(
            return_value=first_contact_activity
        )

        return LeadScoringEngine(
            scoring_rule_repo=scoring_repo,
            activity_repo=activity_repo,
        )

    @staticmethod
    def _default_rules():

        from unittest.mock import MagicMock

        rule = MagicMock()
        rule.condition = {"type": "source", "value": "website"}
        rule.score_adjustment = 50
        rule.is_active = True
        return [rule]

    @pytest.mark.asyncio
    async def test_30_min_response_adds_15_bonus(self):
        """Lead with first contact at 30 minutes → score includes +15 bonus."""
        from datetime import datetime, timedelta, timezone
        from unittest.mock import MagicMock

        created = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
        first_act_time = created + timedelta(minutes=30)

        mock_activity = MagicMock()
        mock_activity.activity_at = first_act_time

        engine = self._build_engine(
            first_contact_activity=mock_activity,
            rules=self._default_rules(),
        )

        lead_data = {
            "lead_id": "existing-uuid",
            "created_at": created,
        }
        source_details = {"source_type": "website"}

        score = await engine.calculate_lead_score(lead_data, source_details)

        # source(50) + response_bonus(15) = 65
        assert score == 65

    @pytest.mark.asyncio
    async def test_3_hour_response_adds_10_bonus(self):
        """Lead with first contact at 3 hours → score includes +10 bonus (≤4h tier)."""
        from datetime import datetime, timedelta, timezone
        from unittest.mock import MagicMock

        created = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
        first_act_time = created + timedelta(hours=3)

        mock_activity = MagicMock()
        mock_activity.activity_at = first_act_time

        engine = self._build_engine(
            first_contact_activity=mock_activity,
            rules=self._default_rules(),
        )

        lead_data = {
            "lead_id": "existing-uuid",
            "created_at": created,
        }
        source_details = {"source_type": "website"}

        score = await engine.calculate_lead_score(lead_data, source_details)

        # source(50) + response_bonus(10) = 60
        assert score == 60

    @pytest.mark.asyncio
    async def test_80_hour_no_contact_subtracts_10(self):
        """Lead with no contact after 80 hours → score includes -10 penalty."""
        from datetime import datetime, timedelta, timezone
        from unittest.mock import MagicMock

        created = datetime(2026, 3, 1, 10, 0, tzinfo=timezone.utc)
        first_act_time = created + timedelta(hours=80)

        mock_activity = MagicMock()
        mock_activity.activity_at = first_act_time

        engine = self._build_engine(
            first_contact_activity=mock_activity,
            rules=self._default_rules(),
        )

        lead_data = {
            "lead_id": "existing-uuid",
            "created_at": created,
        }
        source_details = {"source_type": "website"}

        score = await engine.calculate_lead_score(lead_data, source_details)

        # source(50) + response_bonus(-10) = 40
        assert score == 40

    @pytest.mark.asyncio
    async def test_new_lead_no_activities_bonus_zero(self):
        """New lead (no lead_id, no activities) → response time bonus = 0."""
        engine = self._build_engine(
            first_contact_activity=None,
            rules=self._default_rules(),
        )

        lead_data = {
            # no lead_id — brand-new lead
        }
        source_details = {"source_type": "website"}

        score = await engine.calculate_lead_score(lead_data, source_details)

        # source(50) + response_bonus(0) = 50
        assert score == 50
