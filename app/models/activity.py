from sqlalchemy import Column, String, Text, DateTime, CheckConstraint, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import Base
from sqlalchemy.sql import func

class LeadActivity(Base):
    __tablename__ = "lead_activities"
    activity_id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.lead_id", ondelete="CASCADE"), nullable=False)
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.agent_id", ondelete="CASCADE"), nullable=False)
    type = Column(String(50), nullable=False)
    notes = Column(Text)
    outcome = Column(String(20))
    activity_at = Column(DateTime(timezone=True), server_default=func.now())

    lead = relationship("Lead", back_populates="activities")
    agent = relationship("Agent", back_populates="activities")

    __table_args__ = (
        CheckConstraint("type IN ('call', 'email', 'whatsapp', 'viewing', 'meeting', 'offer_made')", name="ck_activity_type"),
        CheckConstraint("outcome IN ('positive', 'negative', 'neutral') OR outcome IS NULL", name="ck_activity_outcome"),
    )