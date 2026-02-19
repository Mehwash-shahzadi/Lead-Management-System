from app.core.constants import VALID_SOURCE_TYPES
from app.schemas.common import SourceType


class TestSourceTypeConsistency:
    """Ensure SourceType enum is the single source of truth."""

    def test_enum_values_match_valid_source_types(self):
        """set(SourceType) values must exactly equal VALID_SOURCE_TYPES."""
        enum_values = {member.value for member in SourceType}
        assert enum_values == VALID_SOURCE_TYPES, (
            f"SourceType enum values {enum_values} != "
            f"VALID_SOURCE_TYPES {VALID_SOURCE_TYPES}"
        )

    def test_lead_model_check_constraint_contains_all_sources(self):
        """The ck_source_type CHECK constraint on Lead must list every SourceType."""
        from app.models.lead import Lead

        # Find the ck_source_type constraint text
        ck_text = None
        for constraint in Lead.__table_args__:
            if hasattr(constraint, "name") and constraint.name == "ck_source_type":
                ck_text = str(constraint.sqltext)
                break

        assert ck_text is not None, "ck_source_type constraint not found on Lead"

        for member in SourceType:
            assert member.value in ck_text, (
                f"SourceType value '{member.value}' missing from Lead "
                f"CHECK constraint: {ck_text}"
            )

    def test_lead_source_model_check_constraint_contains_all_sources(self):
        """The ck_lead_source_source_type CHECK constraint on LeadSource must list every SourceType."""
        from app.models.lead_source import LeadSource

        ck_text = None
        for constraint in LeadSource.__table_args__:
            if (
                hasattr(constraint, "name")
                and constraint.name == "ck_lead_source_source_type"
            ):
                ck_text = str(constraint.sqltext)
                break

        assert ck_text is not None, (
            "ck_lead_source_source_type constraint not found on LeadSource"
        )

        for member in SourceType:
            assert member.value in ck_text, (
                f"SourceType value '{member.value}' missing from LeadSource "
                f"CHECK constraint: {ck_text}"
            )
