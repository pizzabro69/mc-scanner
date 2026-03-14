from db.engine import Database


class LeadRepository:
    def __init__(self, db: Database):
        self._db = db

    async def upsert_score(
        self,
        server_id: int,
        score: float,
        downtime_pct: float,
        avg_latency_ms: float | None,
        p95_latency_ms: float | None,
        timeout_count: int,
        avg_players: float | None,
        max_players: int | None,
        score_details: str,
        calculated_at: int,
        window_hours: int,
    ) -> None:
        await self._db.conn.execute(
            """INSERT INTO lead_scores
               (server_id, score, downtime_pct, avg_latency_ms, p95_latency_ms,
                timeout_count, avg_players, max_players, score_details, calculated_at, window_hours)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(server_id) DO UPDATE SET
                   score = excluded.score,
                   downtime_pct = excluded.downtime_pct,
                   avg_latency_ms = excluded.avg_latency_ms,
                   p95_latency_ms = excluded.p95_latency_ms,
                   timeout_count = excluded.timeout_count,
                   avg_players = excluded.avg_players,
                   max_players = excluded.max_players,
                   score_details = excluded.score_details,
                   calculated_at = excluded.calculated_at,
                   window_hours = excluded.window_hours""",
            (server_id, score, downtime_pct, avg_latency_ms, p95_latency_ms,
             timeout_count, avg_players, max_players, score_details, calculated_at, window_hours),
        )

    async def get_top_leads(self, limit: int = 10, country: str | None = None) -> list[dict]:
        if country:
            cursor = await self._db.conn.execute(
                """SELECT ls.*, s.host, s.port, s.country_code, s.city
                   FROM lead_scores ls
                   JOIN servers s ON s.id = ls.server_id
                   WHERE s.is_active = 1 AND ls.score > 0 AND s.country_code = ?
                   ORDER BY ls.score DESC LIMIT ?""",
                (country, limit),
            )
        else:
            cursor = await self._db.conn.execute(
                """SELECT ls.*, s.host, s.port, s.country_code, s.city
                   FROM lead_scores ls
                   JOIN servers s ON s.id = ls.server_id
                   WHERE s.is_active = 1 AND ls.score > 0
                   ORDER BY ls.score DESC LIMIT ?""",
                (limit,),
            )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_leads_paginated(
        self,
        page: int = 1,
        per_page: int = 50,
        min_score: float = 0,
        country: str | None = None,
        sort_by: str = "score",
    ) -> tuple[list[dict], int]:
        where_clauses = ["s.is_active = 1", "ls.score >= ?"]
        params: list = [min_score]

        if country:
            where_clauses.append("s.country_code = ?")
            params.append(country)

        where = " AND ".join(where_clauses)

        allowed_sorts = {
            "score": "ls.score DESC",
            "downtime": "ls.downtime_pct DESC",
            "latency": "ls.avg_latency_ms DESC NULLS LAST",
            "players": "ls.avg_players DESC NULLS LAST",
        }
        order = allowed_sorts.get(sort_by, "ls.score DESC")

        count_cursor = await self._db.conn.execute(
            f"""SELECT COUNT(*) FROM lead_scores ls
                JOIN servers s ON s.id = ls.server_id
                WHERE {where}""",
            params,
        )
        total = (await count_cursor.fetchone())[0]

        offset = (page - 1) * per_page
        cursor = await self._db.conn.execute(
            f"""SELECT ls.*, s.host, s.port, s.country_code, s.city
                FROM lead_scores ls
                JOIN servers s ON s.id = ls.server_id
                WHERE {where}
                ORDER BY {order}
                LIMIT ? OFFSET ?""",
            params + [per_page, offset],
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows], total

    async def get_score_for_server(self, server_id: int) -> dict | None:
        cursor = await self._db.conn.execute(
            "SELECT * FROM lead_scores WHERE server_id = ?", (server_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_avg_score(self) -> float:
        cursor = await self._db.conn.execute(
            "SELECT AVG(score) FROM lead_scores WHERE score > 0"
        )
        row = await cursor.fetchone()
        return row[0] or 0.0
