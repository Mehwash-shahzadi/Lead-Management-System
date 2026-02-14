from typing import Dict, Any
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import update, select
from app.models.lead import Lead
from app.models.activity import LeadActivity
from sqlalchemy.sql import func
from datetime import datetime, timedelta

class LeadScoringEngine:
    async def calculate_lead_score(self, lead_data: Dict[str, Any], source_details: Dict[str, Any], db: AsyncSession) -> int:
        score = 0
        
        # Budget range
        budget_max = lead_data.get("budget_max")
        if budget_max:
            if budget_max > 10000000:
                score += 20
            elif budget_max > 5000000:
                score += 15
            elif budget_max > 2000000:
                score += 10
            else:
                score += 5
        
        # Source quality
        source_type = source_details.get("source_type", "").lower()
        source_scores = {
            "bayut": 90,
            "propertyfinder": 85,
            "website": 80,
            "dubizzle": 75,
            "walk_in": 70,
            "referral": 95
        }
        score += source_scores.get(source_type, 50)
        
        # Nationality
        nationality = lead_data.get("nationality", "").lower()
        if "uae" in nationality or "emirati" in nationality:
            score += 10
        elif any(gcc in nationality for gcc in ["saudi", "kuwait", "bahrain", "qatar", "oman"]):
            score += 5
        
        # Property type preference
        if lead_data.get("property_type"):
            score += 5
        
        # Preferred areas match
        if lead_data.get("preferred_areas"):
            score += 5
        
        # Referral bonus
        if source_details.get("referrer_agent_id"):
            score += 10
        
        return min(100, max(0, score))

    async def update_lead_score(self, lead_id: UUID, activity_data: Dict[str, Any], db: AsyncSession) -> int:
        # Get current score
        result = await db.execute(select(Lead.score).where(Lead.lead_id == lead_id))
        current_score = result.scalar_one()
        
        adjustment = 0
        activity_type = activity_data.get("type")
        outcome = activity_data.get("outcome")
        
        if outcome == "positive":
            adjustment += 5
        if activity_type == "viewing":
            adjustment += 10
        if activity_type == "offer_made":
            adjustment += 20
        if activity_type == "no_response":
            adjustment -= 10
        
        new_score = min(100, max(0, current_score + adjustment))
        
        await db.execute(update(Lead).where(Lead.lead_id == lead_id).values(score=new_score))
        
        return new_score
