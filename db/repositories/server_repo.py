import time

from db.engine import Database


class ServerRepository:
    def __init__(self, db: Database):
        self._db = db

    async def upsert_server(
        self,
        host: str,
        port: int,
        country_code: str | None = None,
        city: str | None = None,
        lat: float | None = None,
        lon: float | None = None,
        source: str | None = None,
    ) -> int:
        now = int(time.time())
        cursor = await self._db.conn.execute(
            """INSERT INTO servers (host, port, country_code, city, latitude, longitude, source, first_seen)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(host, port) DO UPDATE SET
                   country_code = COALESCE(excluded.country_code, servers.country_code),
                   city = COALESCE(excluded.city, servers.city),
                   latitude = COALESCE(excluded.latitude, servers.latitude),
                   longitude = COALESCE(excluded.longitude, servers.longitude),
                   is_active = 1
               RETURNING id""",
            (host.lower(), port, country_code, city, lat, lon, source, now),
        )
        row = await cursor.fetchone()
        await self._db.conn.commit()
        return row[0]

    async def get_active_servers(self) -> list[dict]:
        cursor = await self._db.conn.execute(
            "SELECT id, host, port, country_code FROM servers WHERE is_active = 1"
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_server_by_id(self, server_id: int) -> dict | None:
        cursor = await self._db.conn.execute(
            "SELECT * FROM servers WHERE id = ?", (server_id,)
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_servers_paginated(
        self,
        page: int = 1,
        per_page: int = 50,
        country: str | None = None,
        search: str | None = None,
        sort_by: str = "last_seen",
        online_only: bool = False,
    ) -> tuple[list[dict], int]:
        where_clauses = ["s.is_active = 1"]
        params: list = []

        if country:
            where_clauses.append("s.country_code = ?")
            params.append(country)
        if search:
            where_clauses.append("s.host LIKE ?")
            params.append(f"%{search}%")
        if online_only:
            cutoff = int(time.time()) - 900  # seen in last 15 minutes
            where_clauses.append("""s.id IN (
                SELECT DISTINCT server_id FROM scan_results
                WHERE is_online = 1 AND scanned_at >= ?)""")
            params.append(cutoff)

        where = " AND ".join(where_clauses)

        allowed_sorts = {
            "last_seen": "s.last_seen DESC NULLS LAST",
            "host": "s.host ASC",
            "players": "COALESCE(ls.avg_players, s.last_players_online, 0) DESC",
            "score": "COALESCE(ls.score, 0) DESC",
            "latency": "COALESCE(ls.avg_latency_ms, s.last_latency_ms, 9999) ASC",
        }
        order = allowed_sorts.get(sort_by, "s.last_seen DESC NULLS LAST")

        count_cursor = await self._db.conn.execute(
            f"SELECT COUNT(*) FROM servers s WHERE {where}", params
        )
        total = (await count_cursor.fetchone())[0]

        offset = (page - 1) * per_page
        cursor = await self._db.conn.execute(
            f"""SELECT s.*, ls.score, ls.avg_latency_ms, ls.avg_players, ls.downtime_pct
                FROM servers s
                LEFT JOIN lead_scores ls ON ls.server_id = s.id
                WHERE {where}
                ORDER BY {order}
                LIMIT ? OFFSET ?""",
            params + [per_page, offset],
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows], total

    async def update_last_seen(self, server_id: int, timestamp: int) -> None:
        await self._db.conn.execute(
            "UPDATE servers SET last_seen = ? WHERE id = ?", (timestamp, server_id)
        )

    async def update_last_scan_data(
        self,
        server_id: int,
        latency_ms: float | None = None,
        players_online: int | None = None,
        players_max: int | None = None,
        version: str | None = None,
        motd: str | None = None,
    ) -> None:
        await self._db.conn.execute(
            """UPDATE servers SET last_latency_ms = ?, last_players_online = ?,
               last_players_max = ?, last_version = ?, last_motd = ?
               WHERE id = ?""",
            (latency_ms, players_online, players_max, version, motd, server_id),
        )

    async def update_geo(
        self, server_id: int, country_code: str, city: str | None = None,
        lat: float | None = None, lon: float | None = None,
    ) -> None:
        await self._db.conn.execute(
            """UPDATE servers SET country_code = ?, city = ?, latitude = ?, longitude = ?
               WHERE id = ? AND country_code IS NULL""",
            (country_code, city, lat, lon, server_id),
        )

    async def get_servers_without_country(self, limit: int = 100) -> list[dict]:
        cursor = await self._db.conn.execute(
            "SELECT id, host, port FROM servers WHERE country_code IS NULL AND is_active = 1 LIMIT ?",
            (limit,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def deactivate_stale_servers(self, stale_days: int = 30) -> int:
        cutoff = int(time.time()) - (stale_days * 86400)
        cursor = await self._db.conn.execute(
            """UPDATE servers SET is_active = 0
               WHERE is_active = 1 AND (last_seen IS NULL OR last_seen < ?) AND first_seen < ?""",
            (cutoff, cutoff),
        )
        await self._db.conn.commit()
        return cursor.rowcount

    async def count_by_country(self) -> list[dict]:
        cursor = await self._db.conn.execute(
            """SELECT COALESCE(country_code, 'Unknown') as country_code, COUNT(*) as count
               FROM servers WHERE is_active = 1
               GROUP BY country_code ORDER BY count DESC"""
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def total_active(self) -> int:
        cursor = await self._db.conn.execute(
            "SELECT COUNT(*) FROM servers WHERE is_active = 1"
        )
        return (await cursor.fetchone())[0]
