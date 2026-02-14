from typing import List, Dict, Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text, func, case
from app.database import AsyncSessionLocal


class LeadAnalytics:
    @staticmethod
    async def get_lead_conversion_rates_by_source_and_agent() -> List[Dict[str, Any]]:
        """Lead conversion rates by source and agent - dynamically calculated"""
        query = text("""
            SELECT
                l.source_type,
                la.agent_id,
                a.full_name as agent_name,
                ROUND(
                    (COUNT(CASE WHEN l.status = 'converted' THEN 1 END) * 100.0 / NULLIF(COUNT(*), 0)),
                    2
                ) as conversion_rate,
                COUNT(*) as total_leads,
                COUNT(CASE WHEN l.status = 'converted' THEN 1 END) as converted_leads
            FROM leads l
            JOIN lead_assignments la ON l.lead_id = la.lead_id
            JOIN agents a ON la.agent_id = a.agent_id
            GROUP BY l.source_type, la.agent_id, a.full_name
            ORDER BY l.source_type, conversion_rate DESC
        """)

        async with AsyncSessionLocal() as session:
            result = await session.execute(query)
            return [dict(row) for row in result.mappings()]

    @staticmethod
    async def get_average_time_to_conversion_by_property_type() -> List[Dict[str, Any]]:
        """Average time to conversion by property type - only for actual conversions"""
        query = text("""
            SELECT
                l.property_type,
                AVG(EXTRACT(EPOCH FROM (ch.changed_at - l.created_at))) / 86400 as avg_days_to_conversion,
                COUNT(*) as total_conversions
            FROM leads l
            JOIN lead_conversion_history ch ON l.lead_id = ch.lead_id
            WHERE ch.status_to = 'converted'
            AND l.property_type IS NOT NULL
            GROUP BY l.property_type
            HAVING COUNT(*) > 0
            ORDER BY avg_days_to_conversion
        """)

        async with AsyncSessionLocal() as session:
            result = await session.execute(query)
            return [dict(row) for row in result.mappings()]

    @staticmethod
    async def get_monthly_lead_volume_trends() -> List[Dict[str, Any]]:
        """Monthly lead volume trends"""
        query = text("""
            SELECT
                DATE_TRUNC('month', created_at) as month,
                COUNT(*) as lead_volume,
                COUNT(CASE WHEN status = 'converted' THEN 1 END) as converted_volume
            FROM leads
            GROUP BY DATE_TRUNC('month', created_at)
            ORDER BY month DESC
        """)

        async with AsyncSessionLocal() as session:
            result = await session.execute(query)
            return [dict(row) for row in result.mappings()]

    @staticmethod
    async def get_agent_performance_rankings() -> List[Dict[str, Any]]:
        """Agent performance rankings - dynamically calculated from actual data"""
        query = text("""
            WITH agent_stats AS (
                SELECT
                    a.agent_id,
                    a.full_name,
                    COUNT(la.lead_id) as leads_assigned,
                    COUNT(CASE WHEN l.status = 'converted' THEN 1 END) as conversions,
                    ROUND(
                        (COUNT(CASE WHEN l.status = 'converted' THEN 1 END) * 100.0 / NULLIF(COUNT(la.lead_id), 0)),
                        2
                    ) as conversion_rate,
                    COALESCE(AVG(lch.deal_value), 0) as average_deal_size,
                    AVG(EXTRACT(EPOCH FROM (la2.activity_at - l.created_at))/3600) as avg_response_hours
                FROM agents a
                LEFT JOIN lead_assignments la ON a.agent_id = la.agent_id
                LEFT JOIN leads l ON la.lead_id = l.lead_id
                LEFT JOIN lead_conversion_history lch ON l.lead_id = lch.lead_id AND lch.status_to = 'converted'
                LEFT JOIN LATERAL (
                    SELECT activity_at
                    FROM lead_activities la_inner
                    WHERE la_inner.lead_id = l.lead_id
                    ORDER BY activity_at
                    LIMIT 1
                ) la2 ON true
                GROUP BY a.agent_id, a.full_name
            )
            SELECT
                agent_id,
                full_name,
                leads_assigned,
                conversions,
                conversion_rate,
                average_deal_size,
                avg_response_hours
            FROM agent_stats
            WHERE leads_assigned > 0
            ORDER BY conversion_rate DESC, average_deal_size DESC
        """)

        async with AsyncSessionLocal() as session:
            result = await session.execute(query)
            return [dict(row) for row in result.mappings()]

    @staticmethod
    async def get_revenue_attribution_by_lead_source() -> List[Dict[str, Any]]:
        """Revenue attribution by lead source - using proper deal_value column"""
        query = text("""
            SELECT
                l.source_type,
                COALESCE(SUM(lch.deal_value), 0) as total_revenue,
                COUNT(DISTINCT l.lead_id) as converted_leads,
                ROUND(AVG(lch.deal_value), 2) as average_deal_size
            FROM leads l
            JOIN lead_conversion_history lch ON l.lead_id = lch.lead_id
            WHERE lch.status_to = 'converted'
            AND lch.deal_value IS NOT NULL
            GROUP BY l.source_type
            ORDER BY total_revenue DESC
        """)

        async with AsyncSessionLocal() as session:
            result = await session.execute(query)
            return [dict(row) for row in result.mappings()]

    @staticmethod
    async def get_high_scoring_leads_not_converted() -> List[Dict[str, Any]]:
        """High-scoring leads that didn't convert - identify patterns"""
        query = text("""
            SELECT
                source_type,
                nationality,
                budget_min,
                budget_max,
                property_type,
                COUNT(*) as lead_count,
                ROUND(AVG(score), 2) as avg_score,
                MIN(created_at) as earliest_lead,
                MAX(created_at) as latest_lead
            FROM leads
            WHERE score > 80
            AND status != 'converted'
            GROUP BY source_type, nationality, budget_min, budget_max, property_type
            ORDER BY lead_count DESC, avg_score DESC
        """)

        async with AsyncSessionLocal() as session:
            result = await session.execute(query)
            return [dict(row) for row in result.mappings()]

    @staticmethod
    async def get_low_scoring_leads_converted() -> List[Dict[str, Any]]:
        """Low-scoring leads that converted - identify opportunities"""
        query = text("""
            SELECT
                source_type,
                nationality,
                budget_min,
                budget_max,
                property_type,
                COUNT(*) as lead_count,
                ROUND(AVG(score), 2) as avg_score,
                AVG(lch.deal_value) as avg_deal_value
            FROM leads l
            JOIN lead_conversion_history lch ON l.lead_id = lch.lead_id
            WHERE l.score < 50
            AND lch.status_to = 'converted'
            GROUP BY source_type, nationality, budget_min, budget_max, property_type
            ORDER BY lead_count DESC, avg_score DESC
        """)

        async with AsyncSessionLocal() as session:
            result = await session.execute(query)
            return [dict(row) for row in result.mappings()]

    @staticmethod
    async def get_source_quality_comparison_over_time() -> List[Dict[str, Any]]:
        """Source quality comparison over time"""
        query = text("""
            SELECT
                source_type,
                DATE_TRUNC('month', created_at) as month,
                ROUND(AVG(score), 2) as avg_score,
                COUNT(*) as lead_count,
                COUNT(CASE WHEN status = 'converted' THEN 1 END) as converted_count
            FROM leads
            GROUP BY source_type, DATE_TRUNC('month', created_at)
            ORDER BY month DESC, source_type, avg_score DESC
        """)

        async with AsyncSessionLocal() as session:
            result = await session.execute(query)
            return [dict(row) for row in result.mappings()]

    @staticmethod
    async def get_optimal_follow_up_timing_analysis() -> List[Dict[str, Any]]:
        """Optimal follow-up timing analysis - optimized CTE usage"""
        query = text("""
            WITH activity_sequences AS (
                SELECT
                    la.lead_id,
                    la.activity_at,
                    la.outcome,
                    LEAD(la.activity_at) OVER (PARTITION BY la.lead_id ORDER BY la.activity_at) as next_activity_at,
                    LEAD(la.outcome) OVER (PARTITION BY la.lead_id ORDER BY la.activity_at) as next_outcome,
                    l.status = 'converted' as lead_converted
                FROM lead_activities la
                JOIN leads l ON la.lead_id = l.lead_id
                WHERE la.activity_at IS NOT NULL
            ),
            timing_buckets AS (
                SELECT
                    CASE
                        WHEN EXTRACT(EPOCH FROM (next_activity_at - activity_at))/3600 <= 1 THEN '0-1 hours'
                        WHEN EXTRACT(EPOCH FROM (next_activity_at - activity_at))/3600 <= 4 THEN '1-4 hours'
                        WHEN EXTRACT(EPOCH FROM (next_activity_at - activity_at))/3600 <= 24 THEN '4-24 hours'
                        WHEN EXTRACT(EPOCH FROM (next_activity_at - activity_at))/3600 <= 72 THEN '1-3 days'
                        ELSE '3+ days'
                    END as time_bucket,
                    CASE WHEN next_outcome = 'positive' OR lead_converted THEN 1 ELSE 0 END as positive_outcome
                FROM activity_sequences
                WHERE next_activity_at IS NOT NULL
            )
            SELECT
                time_bucket,
                COUNT(*) as total_follow_ups,
                SUM(positive_outcome) as positive_outcomes,
                ROUND((SUM(positive_outcome) * 100.0 / NULLIF(COUNT(*), 0)), 2) as positive_outcome_rate
            FROM timing_buckets
            GROUP BY time_bucket
            ORDER BY
                CASE time_bucket
                    WHEN '0-1 hours' THEN 1
                    WHEN '1-4 hours' THEN 2
                    WHEN '4-24 hours' THEN 3
                    WHEN '1-3 days' THEN 4
                    WHEN '3+ days' THEN 5
                END
        """)

        async with AsyncSessionLocal() as session:
            result = await session.execute(query)
            return [dict(row) for row in result.mappings()]

    @staticmethod
    async def get_current_workload_distribution() -> List[Dict[str, Any]]:
        """Current workload distribution"""
        query = text("""
            SELECT
                agent_id,
                full_name,
                active_leads_count,
                specialization_property_type,
                specialization_areas
            FROM agents
            ORDER BY active_leads_count DESC
        """)

        async with AsyncSessionLocal() as session:
            result = await session.execute(query)
            return [dict(row) for row in result.mappings()]

    @staticmethod
    async def get_agents_approaching_maximum_capacity() -> List[Dict[str, Any]]:
        """Agents approaching maximum capacity - configurable threshold"""
        query = text("""
            SELECT
                agent_id,
                full_name,
                active_leads_count,
                50 - active_leads_count as remaining_capacity
            FROM agents
            WHERE active_leads_count > 40
            ORDER BY active_leads_count DESC
        """)

        async with AsyncSessionLocal() as session:
            result = await session.execute(query)
            return [dict(row) for row in result.mappings()]

    @staticmethod
    async def get_specialized_vs_general_agent_performance() -> List[Dict[str, Any]]:
        """Specialized vs general agent performance - dynamic calculation"""
        query = text("""
            WITH agent_performance AS (
                SELECT
                    a.agent_id,
                    CASE
                        WHEN array_length(a.specialization_property_type, 1) > 0 THEN 'specialized'
                        ELSE 'general'
                    END as agent_category,
                    COUNT(la.lead_id) as total_leads,
                    COUNT(CASE WHEN l.status = 'converted' THEN 1 END) as conversions,
                    ROUND(
                        (COUNT(CASE WHEN l.status = 'converted' THEN 1 END) * 100.0 / NULLIF(COUNT(la.lead_id), 0)),
                        2
                    ) as conversion_rate
                FROM agents a
                LEFT JOIN lead_assignments la ON a.agent_id = la.agent_id
                LEFT JOIN leads l ON la.lead_id = l.lead_id
                GROUP BY a.agent_id, agent_category
            )
            SELECT
                agent_category,
                ROUND(AVG(conversion_rate), 2) as avg_conversion_rate,
                COUNT(*) as agent_count,
                SUM(total_leads) as total_leads_handled,
                SUM(conversions) as total_conversions
            FROM agent_performance
            WHERE total_leads > 0
            GROUP BY agent_category
        """)

        async with AsyncSessionLocal() as session:
            result = await session.execute(query)
            return [dict(row) for row in result.mappings()]

    @staticmethod
    async def get_lead_response_time_correlation_with_conversion() -> List[Dict[str, Any]]:
        """Lead response time correlation with conversion - dynamic calculation"""
        query = text("""
            WITH response_times AS (
                SELECT
                    a.agent_id,
                    AVG(EXTRACT(EPOCH FROM (first_activity.activity_at - l.created_at))/3600) as avg_response_hours,
                    COUNT(CASE WHEN l.status = 'converted' THEN 1 END) as conversions,
                    COUNT(la.lead_id) as total_leads,
                    ROUND(
                        (COUNT(CASE WHEN l.status = 'converted' THEN 1 END) * 100.0 / NULLIF(COUNT(la.lead_id), 0)),
                        2
                    ) as conversion_rate
                FROM agents a
                JOIN lead_assignments la ON a.agent_id = la.agent_id
                JOIN leads l ON la.lead_id = l.lead_id
                LEFT JOIN LATERAL (
                    SELECT activity_at
                    FROM lead_activities la_inner
                    WHERE la_inner.lead_id = l.lead_id
                    ORDER BY activity_at
                    LIMIT 1
                ) first_activity ON true
                GROUP BY a.agent_id
                HAVING COUNT(la.lead_id) > 0
            ),
            response_buckets AS (
                SELECT
                    CASE
                        WHEN avg_response_hours < 1 THEN '< 1 hour'
                        WHEN avg_response_hours < 4 THEN '1-4 hours'
                        WHEN avg_response_hours < 24 THEN '4-24 hours'
                        WHEN avg_response_hours < 72 THEN '1-3 days'
                        ELSE '3+ days'
                    END as response_time_bucket,
                    conversion_rate,
                    total_leads
                FROM response_times
                WHERE avg_response_hours IS NOT NULL
            )
            SELECT
                response_time_bucket,
                ROUND(AVG(conversion_rate), 2) as avg_conversion_rate,
                COUNT(*) as agent_count,
                SUM(total_leads) as total_leads
            FROM response_buckets
            GROUP BY response_time_bucket
            ORDER BY
                CASE response_time_bucket
                    WHEN '< 1 hour' THEN 1
                    WHEN '1-4 hours' THEN 2
                    WHEN '4-24 hours' THEN 3
                    WHEN '1-3 days' THEN 4
                    WHEN '3+ days' THEN 5
                END
        """)

        async with AsyncSessionLocal() as session:
            result = await session.execute(query)
            return [dict(row) for row in result.mappings()]

   