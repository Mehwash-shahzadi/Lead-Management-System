from typing import Dict, FrozenSet, List

from app.schemas.common import SourceType

VALID_SOURCE_TYPES: FrozenSet[str] = frozenset(s.value for s in SourceType)

SOURCE_TYPE_CHECK_CLAUSE: str = (
    f"source_type IN ({', '.join(repr(s.value) for s in SourceType)})"
)

LEAD_STATUSES: FrozenSet[str] = frozenset(
    {
        "new",
        "contacted",
        "qualified",
        "viewing_scheduled",
        "negotiation",
        "converted",
        "lost",
    }
)

# Terminal states — no further transitions allowed
TERMINAL_STATUSES: FrozenSet[str] = frozenset({"converted", "lost"})

# Active statuses (not terminal)
ACTIVE_STATUSES: FrozenSet[str] = LEAD_STATUSES - TERMINAL_STATUSES

ALLOWED_TRANSITIONS: Dict[str, List[str]] = {
    "new": ["contacted", "lost"],
    "contacted": ["qualified", "lost"],
    "qualified": ["viewing_scheduled", "lost"],
    "viewing_scheduled": ["negotiation", "qualified", "lost"],
    "negotiation": ["converted", "lost"],
    "converted": [],  # terminal
    "lost": [],  # terminal
}


ACTIVITY_TYPES: FrozenSet[str] = frozenset(
    {"call", "email", "whatsapp", "viewing", "meeting", "offer_made"}
)

ACTIVITY_OUTCOMES: FrozenSet[str] = frozenset({"positive", "negative", "neutral"})
TASK_TYPES: FrozenSet[str] = frozenset({"call", "email", "whatsapp", "viewing"})
TASK_PRIORITIES: FrozenSet[str] = frozenset({"high", "medium", "low"})
TASK_STATUSES: FrozenSet[str] = frozenset({"pending", "completed", "overdue"})

INTEREST_LEVELS: FrozenSet[str] = frozenset({"high", "medium", "low"})
MAX_AGENT_ACTIVE_LEADS: int = 50


SOURCE_QUALITY_SCORES: Dict[str, int] = {
    "bayut": 90,
    "propertyfinder": 85,
    "website": 80,
    "dubizzle": 75,
    "walk_in": 70,
    "referral": 95,
}
