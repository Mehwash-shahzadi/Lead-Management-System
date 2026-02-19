from typing import Any, Dict, List, Optional, Tuple

from sqlalchemy import text

from app.repositories.base import BaseRepository


class AnalyticsRepository(BaseRepository):
    """Encapsulates every analytics SQL query."""

    @staticmethod
    def _paginate(sql: str) -> str:
        """Wrap a raw SQL string for offset pagination with an embedded total.

        Uses the ``COUNT(*) OVER()`` window function so that the total
        row count is computed alongside the paginated data in a **single
        query**.  The window function is evaluated *before*
        ``OFFSET``/``LIMIT``, so every returned row carries the full
        (un-paged) count in the ``_total_count`` column.
        """
        inner = sql.rstrip().rstrip(";")
        return (
            f"SELECT *, COUNT(*) OVER() AS _total_count\n"
            f"FROM ({inner}) _page_sub\n"
            f"OFFSET :skip LIMIT :limit"
        )

    @staticmethod
    def _keyset_paginate(
        sql: str,
        sort_column: str,
        descending: bool = True,
    ) -> str:
        """Append a keyset WHERE clause, LIMIT, and an embedded total count.

        Uses two CTEs:

        * ``_base`` — materialises the original query once.
        * ``_total`` — counts all rows in ``_base`` (the full,
          un-filtered total).

        The outer ``SELECT`` cross-joins ``_total`` (a single row) with
        ``_base``, applies the cursor filter, and limits.  Because
        PostgreSQL materialises CTEs that are referenced more than once,
        ``_base`` is scanned only once for both the count and the data.
        """
        op = "<" if descending else ">"
        inner = sql.rstrip().rstrip(";")
        return (
            f"WITH _base AS (\n{inner}\n),\n"
            f"_total AS (SELECT COUNT(*) AS cnt FROM _base)\n"
            f"SELECT _base.*, _total.cnt AS _total_count\n"
            f"FROM _base CROSS JOIN _total\n"
            f"WHERE (:cursor IS NULL OR {sort_column} {op} CAST(:cursor AS TEXT))\n"
            f"LIMIT :limit"
        )

    @staticmethod
    def _extract_total(rows: List[Dict[str, Any]]) -> int:
        """Extract and strip the ``_total_count`` column from paginated rows.

        Both :meth:`_paginate` and :meth:`_keyset_paginate` embed the
        total count in every result row.  This helper reads the value
        from the first row, strips the column from *all* rows, and
        returns the count.

        Returns ``0`` when the result set is empty (table is empty or
        the requested page is past the end).
        """
        if not rows:
            return 0
        total: int = rows[0].get("_total_count", 0)
        for row in rows:
            row.pop("_total_count", None)
        return total

    async def _execute_keyset(
        self,
        sql: str,
        sort_column: str,
        *,
        cursor: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
        descending: bool = True,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[Dict[str, Any]], int, Optional[str]]:
        """Execute with keyset pagination if cursor is provided, else offset.

        The total count is embedded in the query via a window function
        (offset mode) or a CTE (keyset mode), so no separate full-scan
        ``COUNT(*)`` subquery is required.

        Returns ``(rows, total_count, next_cursor)``.
        """
        params: Dict[str, Any] = {"skip": skip, "limit": limit}
        if extra_params:
            params.update(extra_params)

        if cursor is not None:
            query = text(self._keyset_paginate(sql, sort_column, descending))
            params["cursor"] = cursor
            # skip is not used in keyset mode; remove to avoid confusion
            params.pop("skip", None)
        else:
            query = text(self._paginate(sql))

        result = await self._db.execute(query, params)
        rows = [dict(r) for r in result.mappings()]
        total_count = self._extract_total(rows)

        next_cursor: Optional[str] = None
        if rows and len(rows) == limit:
            last = rows[-1]
            if sort_column in last and last[sort_column] is not None:
                next_cursor = str(last[sort_column])

        return rows, total_count, next_cursor

    async def _execute_offset(
        self,
        sql: str,
        *,
        skip: int = 0,
        limit: int = 50,
        extra_params: Optional[Dict[str, Any]] = None,
    ) -> Tuple[List[Dict[str, Any]], int]:
        """Execute with offset pagination and return ``(rows, total_count)``.

        The total count is embedded in the query via a ``COUNT(*) OVER()``
        window function, so no separate full-scan ``COUNT(*)`` subquery
        is required.
        """
        params: Dict[str, Any] = {"skip": skip, "limit": limit}
        if extra_params:
            params.update(extra_params)

        result = await self._db.execute(text(self._paginate(sql)), params)
        rows = [dict(r) for r in result.mappings()]
        total_count = self._extract_total(rows)

        return rows, total_count

    _SQL_CONVERSION_RATES = """
        SELECT
            l.source_type,
            la.agent_id,
            a.full_name as agent_name,
            ROUND(
                (COUNT(CASE WHEN l.status = 'converted' THEN 1 END) * 100.0
                 / NULLIF(COUNT(*), 0)),
                2
            ) as conversion_rate,
            COUNT(*) as total_leads,
            COUNT(CASE WHEN l.status = 'converted' THEN 1 END) as converted_leads
        FROM leads l
        JOIN lead_assignments la ON l.lead_id = la.lead_id
        JOIN agents a ON la.agent_id = a.agent_id
        GROUP BY l.source_type, la.agent_id, a.full_name
        ORDER BY l.source_type, conversion_rate DESC
    """

    async def lead_conversion_rates_by_source_and_agent(
        self,
        *,
        cursor: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Dict[str, Any]], int, Optional[str]]:
        return await self._execute_keyset(
            self._SQL_CONVERSION_RATES,
            "source_type",
            cursor=cursor,
            skip=skip,
            limit=limit,
            descending=False,
        )

    async def average_time_to_conversion_by_property_type(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Dict[str, Any]], int]:
        sql = """
            SELECT
                l.property_type,
                AVG(EXTRACT(EPOCH FROM (ch.changed_at - l.created_at))) / 86400
                    as avg_days_to_conversion,
                COUNT(*) as total_conversions
            FROM leads l
            JOIN lead_conversion_history ch ON l.lead_id = ch.lead_id
            WHERE ch.status_to = 'converted'
              AND l.property_type IS NOT NULL
            GROUP BY l.property_type
            HAVING COUNT(*) > 0
            ORDER BY avg_days_to_conversion
        """
        return await self._execute_offset(sql, skip=skip, limit=limit)

    _SQL_MONTHLY_TRENDS = """
        SELECT
            DATE_TRUNC('month', created_at) as month,
            COUNT(*) as lead_volume,
            COUNT(CASE WHEN status = 'converted' THEN 1 END)
                as converted_volume
        FROM leads
        GROUP BY DATE_TRUNC('month', created_at)
        ORDER BY month DESC
    """

    async def monthly_lead_volume_trends(
        self,
        *,
        cursor: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Dict[str, Any]], int, Optional[str]]:
        return await self._execute_keyset(
            self._SQL_MONTHLY_TRENDS,
            "month",
            cursor=cursor,
            skip=skip,
            limit=limit,
            descending=True,
        )

    async def agent_performance_rankings(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Dict[str, Any]], int]:
        sql = """
            WITH agent_stats AS (
                SELECT
                    a.agent_id,
                    a.full_name,
                    COUNT(la.lead_id) as leads_assigned,
                    COUNT(CASE WHEN l.status = 'converted' THEN 1 END)
                        as conversions,
                    ROUND(
                        (COUNT(CASE WHEN l.status = 'converted' THEN 1 END)
                         * 100.0 / NULLIF(COUNT(la.lead_id), 0)),
                        2
                    ) as conversion_rate,
                    COALESCE(AVG(lch.deal_value), 0) as average_deal_size,
                    AVG(EXTRACT(EPOCH FROM
                        (la2.activity_at - l.created_at))/3600)
                        as avg_response_hours
                FROM agents a
                LEFT JOIN lead_assignments la ON a.agent_id = la.agent_id
                LEFT JOIN leads l ON la.lead_id = l.lead_id
                LEFT JOIN lead_conversion_history lch
                    ON l.lead_id = lch.lead_id
                   AND lch.status_to = 'converted'
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
                agent_id, full_name, leads_assigned, conversions,
                conversion_rate, average_deal_size, avg_response_hours
            FROM agent_stats
            WHERE leads_assigned > 0
            ORDER BY conversion_rate DESC, average_deal_size DESC
        """
        return await self._execute_offset(sql, skip=skip, limit=limit)

    async def revenue_attribution_by_lead_source(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Dict[str, Any]], int]:
        sql = """
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
        """
        return await self._execute_offset(sql, skip=skip, limit=limit)

    async def high_scoring_leads_not_converted(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Dict[str, Any]], int]:
        sql = """
            SELECT
                source_type, nationality,
                budget_min, budget_max, property_type,
                COUNT(*) as lead_count,
                ROUND(AVG(score), 2) as avg_score,
                MIN(created_at) as earliest_lead,
                MAX(created_at) as latest_lead
            FROM leads
            WHERE score > 80
              AND status != 'converted'
            GROUP BY source_type, nationality, budget_min,
                     budget_max, property_type
            ORDER BY lead_count DESC, avg_score DESC
        """
        return await self._execute_offset(sql, skip=skip, limit=limit)

    async def low_scoring_leads_converted(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Dict[str, Any]], int]:
        sql = """
            SELECT
                source_type, nationality,
                budget_min, budget_max, property_type,
                COUNT(*) as lead_count,
                ROUND(AVG(score), 2) as avg_score,
                AVG(lch.deal_value) as avg_deal_value
            FROM leads l
            JOIN lead_conversion_history lch ON l.lead_id = lch.lead_id
            WHERE l.score < 50
              AND lch.status_to = 'converted'
            GROUP BY source_type, nationality, budget_min,
                     budget_max, property_type
            ORDER BY lead_count DESC, avg_score DESC
        """
        return await self._execute_offset(sql, skip=skip, limit=limit)

    async def source_quality_comparison_over_time(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Dict[str, Any]], int]:
        sql = """
            SELECT
                source_type,
                DATE_TRUNC('month', created_at) as month,
                ROUND(AVG(score), 2) as avg_score,
                COUNT(*) as lead_count,
                COUNT(CASE WHEN status = 'converted' THEN 1 END)
                    as converted_count
            FROM leads
            GROUP BY source_type, DATE_TRUNC('month', created_at)
            ORDER BY month DESC, source_type, avg_score DESC
        """
        return await self._execute_offset(sql, skip=skip, limit=limit)

    async def optimal_follow_up_timing_analysis(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Dict[str, Any]], int]:
        sql = """
            WITH activity_sequences AS (
                SELECT
                    la.lead_id,
                    la.activity_at,
                    la.outcome,
                    LEAD(la.activity_at) OVER (
                        PARTITION BY la.lead_id ORDER BY la.activity_at
                    ) as next_activity_at,
                    LEAD(la.outcome) OVER (
                        PARTITION BY la.lead_id ORDER BY la.activity_at
                    ) as next_outcome,
                    l.status = 'converted' as lead_converted
                FROM lead_activities la
                JOIN leads l ON la.lead_id = l.lead_id
                WHERE la.activity_at IS NOT NULL
            ),
            timing_buckets AS (
                SELECT
                    CASE
                        WHEN EXTRACT(EPOCH FROM
                            (next_activity_at - activity_at))/3600 <= 1
                            THEN '0-1 hours'
                        WHEN EXTRACT(EPOCH FROM
                            (next_activity_at - activity_at))/3600 <= 4
                            THEN '1-4 hours'
                        WHEN EXTRACT(EPOCH FROM
                            (next_activity_at - activity_at))/3600 <= 24
                            THEN '4-24 hours'
                        WHEN EXTRACT(EPOCH FROM
                            (next_activity_at - activity_at))/3600 <= 72
                            THEN '1-3 days'
                        ELSE '3+ days'
                    END as time_bucket,
                    CASE
                        WHEN next_outcome = 'positive' OR lead_converted
                        THEN 1 ELSE 0
                    END as positive_outcome
                FROM activity_sequences
                WHERE next_activity_at IS NOT NULL
            )
            SELECT
                time_bucket,
                COUNT(*) as total_follow_ups,
                SUM(positive_outcome) as positive_outcomes,
                ROUND(
                    (SUM(positive_outcome) * 100.0
                     / NULLIF(COUNT(*), 0)), 2
                ) as positive_outcome_rate
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
        """
        return await self._execute_offset(sql, skip=skip, limit=limit)

    _SQL_WORKLOAD_DIST = """
        SELECT
            agent_id, full_name, active_leads_count,
            specialization_property_type, specialization_areas
        FROM agents
        ORDER BY active_leads_count DESC
    """

    async def current_workload_distribution(
        self,
        *,
        cursor: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Dict[str, Any]], int, Optional[str]]:
        return await self._execute_keyset(
            self._SQL_WORKLOAD_DIST,
            "active_leads_count",
            cursor=cursor,
            skip=skip,
            limit=limit,
            descending=True,
        )

    _SQL_APPROACHING_CAP = """
        SELECT
            agent_id, full_name, active_leads_count,
            50 - active_leads_count as remaining_capacity
        FROM agents
        WHERE active_leads_count > :threshold
        ORDER BY active_leads_count DESC
    """

    async def agents_approaching_maximum_capacity(
        self,
        threshold: int = 40,
        *,
        cursor: Optional[str] = None,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Dict[str, Any]], int, Optional[str]]:
        return await self._execute_keyset(
            self._SQL_APPROACHING_CAP,
            "active_leads_count",
            cursor=cursor,
            skip=skip,
            limit=limit,
            descending=True,
            extra_params={"threshold": threshold},
        )

    async def specialized_vs_general_agent_performance(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Dict[str, Any]], int]:
        sql = """
            WITH agent_performance AS (
                SELECT
                    a.agent_id,
                    CASE
                        WHEN array_length(
                            a.specialization_property_type, 1) > 0
                        THEN 'specialized'
                        ELSE 'general'
                    END as agent_category,
                    COUNT(la.lead_id) as total_leads,
                    COUNT(CASE WHEN l.status = 'converted' THEN 1 END)
                        as conversions,
                    ROUND(
                        (COUNT(CASE WHEN l.status = 'converted' THEN 1 END)
                         * 100.0 / NULLIF(COUNT(la.lead_id), 0)),
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
        """
        return await self._execute_offset(sql, skip=skip, limit=limit)

    async def lead_response_time_correlation_with_conversion(
        self,
        *,
        skip: int = 0,
        limit: int = 50,
    ) -> Tuple[List[Dict[str, Any]], int]:
        sql = """
            WITH response_times AS (
                SELECT
                    a.agent_id,
                    AVG(EXTRACT(EPOCH FROM
                        (first_activity.activity_at - l.created_at))/3600)
                        as avg_response_hours,
                    COUNT(CASE WHEN l.status = 'converted' THEN 1 END)
                        as conversions,
                    COUNT(la.lead_id) as total_leads,
                    ROUND(
                        (COUNT(CASE WHEN l.status = 'converted' THEN 1 END)
                         * 100.0 / NULLIF(COUNT(la.lead_id), 0)),
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
        """
        return await self._execute_offset(sql, skip=skip, limit=limit)
