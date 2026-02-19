import pytest
from pydantic import ValidationError

from app.schemas.lead import LeadCreate

_VALID_LEAD_KWARGS = {
    "first_name": "Fatima",
    "last_name": "Al Maktoum",
    "phone": "+971501234567",
    "nationality": "UAE",
    "language_preference": "arabic",
    "property_type": "villa",
    "preferred_areas": ["Palm Jumeirah"],
}


def _lead(**overrides) -> LeadCreate:
    return LeadCreate(**{**_VALID_LEAD_KWARGS, **overrides})


class TestBudgetRangeValid:
    """Cases where budget_min < budget_max — schema must accept."""

    def test_budget_min_less_than_max_passes(self):
        lead = _lead(budget_min=800_000, budget_max=1_500_000)
        assert lead.budget_min < lead.budget_max

    def test_budget_with_large_spread(self):
        lead = _lead(budget_min=1, budget_max=499_999_999)
        assert lead.budget_min == 1


class TestBudgetMinVsMax:
    """budget_min must be strictly less than budget_max."""

    def test_budget_min_equal_to_max_raises(self):
        with pytest.raises(ValidationError, match="must be strictly less than"):
            _lead(budget_min=1_000_000, budget_max=1_000_000)

    def test_budget_min_greater_than_max_raises(self):
        with pytest.raises(ValidationError, match="must be strictly less than"):
            _lead(budget_min=2_000_000, budget_max=1_000_000)

    def test_error_includes_actual_values(self):
        """The error message should include the offending AED amounts."""
        with pytest.raises(ValidationError, match="2000000.0 AED"):
            _lead(budget_min=2_000_000, budget_max=1_000_000)


class TestBudgetFieldConstraints:
    """Each budget field must be > 0 independently."""

    def test_budget_min_zero_raises(self):
        with pytest.raises(ValidationError):
            _lead(budget_min=0, budget_max=1_000_000)

    def test_budget_max_zero_raises(self):
        with pytest.raises(ValidationError):
            _lead(budget_min=500_000, budget_max=0)

    def test_budget_min_negative_raises(self):
        with pytest.raises(ValidationError):
            _lead(budget_min=-100, budget_max=1_000_000)

    def test_budget_max_negative_raises(self):
        with pytest.raises(ValidationError):
            _lead(budget_min=500_000, budget_max=-100)


class TestBudgetCeiling:
    """budget_max must not exceed 500,000,000 AED."""

    def test_budget_max_at_ceiling_passes(self):
        lead = _lead(budget_min=1_000, budget_max=500_000_000)
        assert lead.budget_max == 500_000_000

    def test_budget_max_above_ceiling_raises(self):
        with pytest.raises(ValidationError, match="maximum allowed value"):
            _lead(budget_min=1_000, budget_max=500_000_001)
