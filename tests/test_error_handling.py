import pytest

from app.dependencies import LeadValidator
from app.core.exceptions import (
    InvalidStatusTransitionError,
)
from app.schemas.common import LeadStatus


class TestStatusTransitions:
    """Verify every valid and invalid status transition."""

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "current,new",
        [
            ("new", LeadStatus.contacted),
            ("new", LeadStatus.lost),
            ("contacted", LeadStatus.qualified),
            ("contacted", LeadStatus.lost),
            ("qualified", LeadStatus.viewing_scheduled),
            ("qualified", LeadStatus.lost),
            ("viewing_scheduled", LeadStatus.negotiation),
            ("viewing_scheduled", LeadStatus.qualified),
            ("viewing_scheduled", LeadStatus.lost),
            ("negotiation", LeadStatus.converted),
            ("negotiation", LeadStatus.lost),
        ],
    )
    async def test_valid_transitions(self, current: str, new: LeadStatus):
        """All transitions defined in ALLOWED_TRANSITIONS must succeed."""
        # Should not raise
        await LeadValidator.validate_status_transition(current, new)

    @pytest.mark.asyncio
    @pytest.mark.parametrize(
        "current,new",
        [
            ("new", LeadStatus.converted),
            ("new", LeadStatus.negotiation),
            ("new", LeadStatus.qualified),
            ("contacted", LeadStatus.converted),
            ("contacted", LeadStatus.viewing_scheduled),
            ("converted", LeadStatus.new),
            ("lost", LeadStatus.new),
            ("lost", LeadStatus.contacted),
        ],
    )
    async def test_invalid_transitions(self, current: str, new: LeadStatus):
        """Transitions NOT in ALLOWED_TRANSITIONS must raise."""
        with pytest.raises(InvalidStatusTransitionError):
            await LeadValidator.validate_status_transition(current, new)

    @pytest.mark.asyncio
    async def test_terminal_states_block_all_transitions(self):
        """Neither 'converted' nor 'lost' may transition anywhere."""
        for terminal in ("converted", "lost"):
            for target in LeadStatus:
                if target.value == terminal:
                    continue
                with pytest.raises(InvalidStatusTransitionError):
                    await LeadValidator.validate_status_transition(terminal, target)


# ---------------------------------------------------------------------------
# Lead data validation
# ---------------------------------------------------------------------------


class TestLeadDataValidation:
    @pytest.mark.asyncio
    async def test_validate_lead_data_accepts_any_dict(self):
        """No-op hook should accept any dict without raising."""
        await LeadValidator.validate_lead_data(
            {"budget_min": 1_000_000, "budget_max": 500_000}
        )
        await LeadValidator.validate_lead_data(
            {"budget_min": 500_000, "budget_max": 1_000_000}
        )
        await LeadValidator.validate_lead_data({})
