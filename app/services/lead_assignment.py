from typing import Dict, Any, Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, func
from app.models.agent import Agent
from app.models.assignment import LeadAssignment
from app.models.lead import Lead
from app.exceptions import AgentOverloadError
from fastapi import HTTPException

class LeadAssignmentManager:
    async def _find_best_agent(self, lead_data: Dict[str, Any], db: AsyncSession) -> Agent:
        # Get available agents
        result = await db.execute(select(Agent).where(Agent.active_leads_count < 50))
        agents = result.scalars().all()
        
        if not agents:
            raise AgentOverloadError()
        
        # Convert Pydantic model to dict if needed
        if hasattr(lead_data, 'dict'):
            lead_dict = lead_data.dict()
        else:
            lead_dict = lead_data
        
        # Calculate match scores
        lead_property_type = lead_dict.get("property_type")
        lead_areas = lead_dict.get("preferred_areas", [])
        lead_language = lead_dict.get("language_preference")
        
        best_agent = None
        best_score = -1
        
        for agent in agents:
            score = 0
            if lead_property_type and lead_property_type in (agent.specialization_property_type or []):
                score += 1
            if any(area in (agent.specialization_areas or []) for area in lead_areas):
                score += 1
            if lead_language and lead_language in (agent.language_skills or []):
                score += 1
            
            if score > best_score or (score == best_score and (best_agent is None or agent.active_leads_count < best_agent.active_leads_count)):
                best_score = score
                best_agent = agent
        
        return best_agent

    async def assign_lead(self, lead_data: Dict[str, Any], db: AsyncSession) -> UUID:
        best_agent = await self._find_best_agent(lead_data, db)
        
        # Just return the agent_id, don't create assignment record yet
        return best_agent.agent_id

    async def reassign_lead(self, lead_id: UUID, reason: str, db: AsyncSession, new_agent_id: Optional[UUID] = None) -> UUID:
        # Get current assignment
        result = await db.execute(select(LeadAssignment).where(LeadAssignment.lead_id == lead_id))
        assignment = result.scalar_one_or_none()
        if not assignment:
            raise HTTPException(status_code=404, detail="Assignment not found")
        
        old_agent_id = assignment.agent_id
        
        if new_agent_id is None:
            # Auto assign
            result = await db.execute(select(Lead).where(Lead.lead_id == lead_id))
            lead = result.scalar_one()
            lead_data = {
                "lead_id": lead.lead_id,
                "property_type": lead.property_type,
                "preferred_areas": lead.preferred_areas,
                "language_preference": lead.language_preference
            }
            new_agent = await self._find_best_agent(lead_data, db)
            new_agent_id = new_agent.agent_id
        else:
            # Check new agent availability
            result = await db.execute(select(Agent).where(Agent.agent_id == new_agent_id))
            new_agent = result.scalar_one_or_none()
            if not new_agent or new_agent.active_leads_count >= 50:
                raise AgentOverloadError()
        
        # Update assignment
        assignment.agent_id = new_agent_id
        assignment.reassigned_at = func.now()
        assignment.reason = reason
        
        # Update counts
        await db.execute(update(Agent).where(Agent.agent_id == old_agent_id).values(active_leads_count=Agent.active_leads_count - 1))
        await db.execute(update(Agent).where(Agent.agent_id == new_agent_id).values(active_leads_count=Agent.active_leads_count + 1))
        await db.commit()
        
        return new_agent_id
