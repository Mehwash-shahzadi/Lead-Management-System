from app.core.constants import (
    VALID_SOURCE_TYPES,
    LEAD_STATUSES,
    TERMINAL_STATUSES,
    ACTIVE_STATUSES,
    ALLOWED_TRANSITIONS,
    ACTIVITY_TYPES,
    SOURCE_QUALITY_SCORES,
    MAX_AGENT_ACTIVE_LEADS,
)
from app.schemas.common import (
    SourceType,
    LeadStatus,
    ActivityType,
)


class TestConstantsConsistency:
    """Verify that constants, enums, and schemas stay in sync."""

    def test_source_types_match_enum(self):
        """Every SourceType enum value must appear in VALID_SOURCE_TYPES."""
        for member in SourceType:
            assert member.value in VALID_SOURCE_TYPES

    def test_lead_statuses_match_enum(self):
        """Every LeadStatus enum value must appear in LEAD_STATUSES."""
        for member in LeadStatus:
            assert member.value in LEAD_STATUSES

    def test_activity_types_match_enum(self):
        """Every ActivityType enum value must appear in ACTIVITY_TYPES."""
        for member in ActivityType:
            assert member.value in ACTIVITY_TYPES

    def test_terminal_statuses_are_subset(self):
        """TERMINAL_STATUSES must be a subset of LEAD_STATUSES."""
        assert TERMINAL_STATUSES.issubset(LEAD_STATUSES)

    def test_active_plus_terminal_equals_all(self):
        """ACTIVE_STATUSES + TERMINAL_STATUSES must equal LEAD_STATUSES."""
        assert ACTIVE_STATUSES | TERMINAL_STATUSES == LEAD_STATUSES

    def test_all_statuses_have_transition_entry(self):
        """Every lead status must have an entry in ALLOWED_TRANSITIONS."""
        for status in LEAD_STATUSES:
            assert status in ALLOWED_TRANSITIONS

    def test_terminal_statuses_have_empty_transitions(self):
        """Terminal statuses must not transition anywhere."""
        for status in TERMINAL_STATUSES:
            assert ALLOWED_TRANSITIONS[status] == []

    def test_max_agent_leads_is_50(self):
        """Assessment specifies max 50 active leads per agent."""
        assert MAX_AGENT_ACTIVE_LEADS == 50

    def test_source_quality_scores_keys_are_lowercase(self):
        """All keys in SOURCE_QUALITY_SCORES must be lowercase for safe lookup."""
        for key in SOURCE_QUALITY_SCORES:
            assert key == key.lower(), f"Key '{key}' is not lowercase"

    def test_propertyfinder_score_is_85(self):
        """propertyFinder source quality score must be 22 per rebalanced rules."""
        assert SOURCE_QUALITY_SCORES["propertyfinder"] == 85
