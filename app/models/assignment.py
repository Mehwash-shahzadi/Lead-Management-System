
from sqlalchemy import Column, DateTime, Text, UniqueConstraint, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import Base
from sqlalchemy.sql import func

class LeadAssignment(Base):
    __tablename__ = "lead_assignments"
    assignment_id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.lead_id", ondelete="CASCADE"), nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.agent_id", ondelete="CASCADE"), nullable=False)
    assigned_at = Column(DateTime(timezone=True), server_default=func.now())
    reassigned_at = Column(DateTime(timezone=True))
    reason = Column(Text)

    lead = relationship("Lead", back_populates="assignments")
    agent = relationship("Agent", back_populates="assignments")

    __table_args__ = (
        UniqueConstraint("lead_id", name="uq_lead_assignment"),
    )