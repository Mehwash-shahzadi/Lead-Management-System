from sqlalchemy import Column, Numeric, Interval, Integer, DateTime, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import relationship
from app.models.base import Base
from sqlalchemy.sql import func


class AgentPerformanceMetric(Base):
    """Rolling performance statistics for an agent.

    Stores conversion rate, average deal size, average response time,
    and total leads handled.  Used by the assignment algorithm to give
    performance-based bonuses when selecting the best agent for a lead.
    """

    __tablename__ = "agent_performance_metrics"
    metric_id = Column(
        UUID(as_uuid=True), primary_key=True, server_default=func.gen_random_uuid()
    )
    agent_id = Column(
        UUID(as_uuid=True),
        ForeignKey("agents.agent_id", ondelete="CASCADE"),
        nullable=False,
    )
    conversion_rate = Column(Numeric(5, 2))
    average_deal_size = Column(Numeric(15, 2))
    average_response_time = Column(Interval)
    leads_handled = Column(Integer)
    updated_at = Column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )

    agent = relationship("Agent", back_populates="performance_metrics")
