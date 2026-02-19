from typing import Any, Dict, List


DEFAULT_SCORING_RULES: List[Dict[str, Any]] = [
    {
        "rule_name": "High Budget (>10M AED)",
        "score_adjustment": 20,
        "condition": {"type": "budget_min", "threshold": 10_000_000},
    },
    {
        "rule_name": "Medium-High Budget (>5M AED)",
        "score_adjustment": 15,
        "condition": {"type": "budget_min", "threshold": 5_000_000},
    },
    {
        "rule_name": "Medium Budget (>2M AED)",
        "score_adjustment": 10,
        "condition": {"type": "budget_min", "threshold": 2_000_000},
    },
    {
        "rule_name": "Low Budget (default)",
        "score_adjustment": 5,
        "condition": {"type": "budget_min", "threshold": 0},
    },
    {
        "rule_name": "Referral Source",
        "score_adjustment": 95,
        "condition": {"type": "source", "value": "referral"},
    },
    {
        "rule_name": "Bayut Source",
        "score_adjustment": 90,
        "condition": {"type": "source", "value": "bayut"},
    },
    {
        "rule_name": "PropertyFinder Source",
        "score_adjustment": 85,
        "condition": {"type": "source", "value": "propertyfinder"},
    },
    {
        "rule_name": "Website Source",
        "score_adjustment": 80,
        "condition": {"type": "source", "value": "website"},
    },
    {
        "rule_name": "Dubizzle Source",
        "score_adjustment": 75,
        "condition": {"type": "source", "value": "dubizzle"},
    },
    {
        "rule_name": "Walk-in Source",
        "score_adjustment": 70,
        "condition": {"type": "source", "value": "walk_in"},
    },
    {
        "rule_name": "UAE/Emirati Nationality",
        "score_adjustment": 10,
        "condition": {"type": "nationality", "values": ["UAE", "Emirati"]},
    },
    {
        "rule_name": "GCC Nationality",
        "score_adjustment": 5,
        "condition": {
            "type": "nationality",
            "values": ["Saudi", "Kuwait", "Bahrain", "Qatar", "Oman"],
        },
    },
    {
        "rule_name": "Has Property Type",
        "score_adjustment": 5,
        "condition": {"type": "property_type"},
    },
    {
        "rule_name": "Has Preferred Areas",
        "score_adjustment": 5,
        "condition": {"type": "preferred_areas"},
    },
    {
        "rule_name": "Referral Bonus",
        "score_adjustment": 10,
        "condition": {"type": "referral"},
    },
    {
        "rule_name": "Positive Interaction",
        "score_adjustment": 5,
        "condition": {"type": "activity_outcome", "value": "positive"},
    },
    {
        "rule_name": "Property Viewing",
        "score_adjustment": 10,
        "condition": {"type": "activity_type", "value": "viewing"},
    },
    {
        "rule_name": "Offer Made",
        "score_adjustment": 20,
        "condition": {"type": "activity_type", "value": "offer_made"},
    },
    {
        "rule_name": "No Response 7 Days",
        "score_adjustment": -10,
        "condition": {"type": "inactivity_days", "threshold": 7},
    },
    {
        "rule_name": "Response Time <= 1 Hour",
        "score_adjustment": 15,
        "condition": {"type": "response_time", "max_hours": 1},
    },
    {
        "rule_name": "Response Time <= 4 Hours",
        "score_adjustment": 10,
        "condition": {"type": "response_time", "max_hours": 4},
    },
    {
        "rule_name": "Response Time <= 24 Hours",
        "score_adjustment": 5,
        "condition": {"type": "response_time", "max_hours": 24},
    },
    {
        "rule_name": "Response Time <= 72 Hours",
        "score_adjustment": 0,
        "condition": {"type": "response_time", "max_hours": 72},
    },
    {
        "rule_name": "Response Time > 72 Hours",
        "score_adjustment": -10,
        "condition": {"type": "response_time", "min_hours": 72},
    },
]
