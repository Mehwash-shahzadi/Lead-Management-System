from sqlalchemy import Column, String, DateTime, CheckConstraint, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import Base
from sqlalchemy.sql import func

class LeadPropertyInterest(Base):
    __tablename__ = "lead_property_interests"
    interest_id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    lead_id = Column(UUID(as_uuid=True), ForeignKey("leads.lead_id", ondelete="CASCADE"), nullable=False)
    property_id = Column(UUID(as_uuid=True), nullable=False)
    interest_level = Column(String(20), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())

    lead = relationship("Lead", back_populates="property_interests")

    __table_args__ = (
        CheckConstraint("interest_level IN ('high', 'medium', 'low')", name="ck_interest_level"),
    )