from sqlalchemy import Column, String, Text, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import Base
from sqlalchemy.sql import func

class LeadConversionHistory(Base):
    __tablename__ = "lead_conversion_history"
    history_id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.lead_id", ondelete="CASCADE"), nullable=False)
    status_from = Column(String(50))
    status_to = Column(String(50))
    changed_at = Column(DateTime(timezone=True), server_default=func.now())
    agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.agent_id"))
    notes = Column(Text)

    lead = relationship("Lead", back_populates="conversion_history")