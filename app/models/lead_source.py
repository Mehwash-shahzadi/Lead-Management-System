from sqlalchemy import Column, String, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import Base
from sqlalchemy.sql import func
from sqlalchemy import CheckConstraint,DateTime

class LeadSource(Base):
    __tablename__ = "lead_sources"
    source_id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.lead_id", ondelete="CASCADE"), nullable=False)
    source_type = Column(String(50), nullable=False)
    campaign_id = Column(String(100))
    referrer_agent_id = Column(UUID(as_uuid=True), ForeignKey("agents.agent_id", ondelete="SET NULL"))
    property_id = Column(UUID(as_uuid=True))
    utm_source = Column(String(100))
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    lead = relationship("Lead", back_populates="sources")
    referrer_agent = relationship("Agent")

    __table_args__ = (
        CheckConstraint("source_type IN ('bayut', 'propertyFinder', 'dubizzle', 'website', 'walk_in', 'referral')", name="ck_source_type"),
    )