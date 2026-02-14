from sqlalchemy import Column, String, Integer, DateTime
from sqlalchemy.dialects.postgresql import UUID, JSONB
from app.models.base import Base
from sqlalchemy.sql import func

class LeadScoringRule(Base):
    __tablename__ = "lead_scoring_rules"
    rule_id = Column(UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid())
    rule_name = Column(String(100), nullable=False)
    score_adjustment = Column(Integer, nullable=False)
    condition = Column(JSONB, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())