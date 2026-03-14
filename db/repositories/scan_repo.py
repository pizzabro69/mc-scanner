import time

from db.engine import Database


class ScanResultRepository:
    def __init__(self, db: Database):
        self._db = db

    async def insert_result(
        self,
        server_id: int,
        scanned_at: int,
        is_online: bool,
        latency_ms: float | None = None,
        players_online: int | None = None,
        players_max: int | None = None,
        version_name: str | None = None,
        version_protocol: int | None = None,
        motd: str | None = None,
        error_message: str | None = None,
    ) -> int:
        cursor = await self._db.conn.execute(
            """INSERT INTO scan_results
               (server_id, scanned_at, is_online, latency_ms, players_online, players_max,
                version_name, version_protocol, motd, error_message)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (server_id, scanned_at, int(is_online), latency_ms, players_online,
             players_max, version_name, version_protocol, motd, error_message),
        )
        return cursor.lastrowid

    async def get_history(
        self, server_id: int, since: int | None = None, limit: int = 1000
    ) -> list[dict]:
        if since:
            cursor = await self._db.conn.execute(
                """SELECT * FROM scan_results
                   WHERE server_id = ? AND scanned_at >= ?
                   ORDER BY scanned_at DESC LIMIT ?""",
                (server_id, since, limit),
            )
        else:
            cursor = await self._db.conn.execute(
                """SELECT * FROM scan_results
                   WHERE server_id = ?
                   ORDER BY scanned_at DESC LIMIT ?""",
                (server_id, limit),
            )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_latest_for_server(self, server_id: int) -> dict | None:
        cursor = await self._db.conn.execute(
            "SELECT * FROM scan_results WHERE server_id = ? ORDER BY scanned_at DESC LIMIT 1",
            (server_id,),
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_stats_for_scoring(self, server_id: int, since_timestamp: int) -> dict:
        cursor = await self._db.conn.execute(
            """SELECT
                COUNT(*) as total_scans,
                SUM(is_online) as online_count,
                AVG(CASE WHEN is_online = 1 THEN latency_ms END) as avg_latency_ms,
                AVG(CASE WHEN is_online = 1 THEN players_online END) as avg_players,
                MAX(players_online) as max_players_seen,
                SUM(CASE WHEN error_message = 'timeout' THEN 1 ELSE 0 END) as timeout_count
               FROM scan_results
               WHERE server_id = ? AND scanned_at >= ?""",
            (server_id, since_timestamp),
        )
        row = await cursor.fetchone()
        result = dict(row)

        # Calculate p95 latency
        p95_cursor = await self._db.conn.execute(
            """SELECT latency_ms FROM scan_results
               WHERE server_id = ? AND scanned_at >= ? AND is_online = 1 AND latency_ms IS NOT NULL
               ORDER BY latency_ms ASC""",
            (server_id, since_timestamp),
        )
        latencies = [r[0] for r in await p95_cursor.fetchall()]
        if latencies:
            idx = int(len(latencies) * 0.95)
            result["p95_latency_ms"] = latencies[min(idx, len(latencies) - 1)]
        else:
            result["p95_latency_ms"] = None

        # Downtime percentage
        total = result["total_scans"] or 0
        online = result["online_count"] or 0
        result["downtime_pct"] = ((total - online) / total * 100) if total > 0 else 0

        return result

    async def start_cycle(self) -> int:
        now = int(time.time())
        cursor = await self._db.conn.execute(
            "INSERT INTO scan_cycles (started_at) VALUES (?)", (now,)
        )
        await self._db.conn.commit()
        return cursor.lastrowid

    async def finish_cycle(self, cycle_id: int, stats: dict) -> None:
        now = int(time.time())
        avg_lat = (
            stats["total_latency"] / stats["online"]
            if stats.get("online", 0) > 0
            else None
        )
        await self._db.conn.execute(
            """UPDATE scan_cycles
               SET finished_at = ?, servers_scanned = ?, servers_online = ?,
                   avg_latency_ms = ?, status = 'completed'
               WHERE id = ?""",
            (now, stats.get("scanned", 0), stats.get("online", 0), avg_lat, cycle_id),
        )
        await self._db.conn.commit()

    async def get_recent_cycles(self, limit: int = 24) -> list[dict]:
        cursor = await self._db.conn.execute(
            "SELECT * FROM scan_cycles ORDER BY started_at DESC LIMIT ?", (limit,)
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_online_count_now(self) -> int:
        """Count servers that were online in the most recent scan cycle."""
        cursor = await self._db.conn.execute(
            """SELECT servers_online FROM scan_cycles
               WHERE status = 'completed' ORDER BY finished_at DESC LIMIT 1"""
        )
        row = await cursor.fetchone()
        return row[0] if row else 0

    async def get_error_breakdown(self, limit_hours: int = 1) -> list[dict]:
        """Get breakdown of error types from recent scans."""
        cutoff = int(time.time()) - (limit_hours * 3600)
        cursor = await self._db.conn.execute(
            """SELECT
                COALESCE(error_message, 'online') as error_type,
                COUNT(*) as count
               FROM scan_results
               WHERE scanned_at >= ?
               GROUP BY error_type
               ORDER BY count DESC""",
            (cutoff,),
        )
        rows = await cursor.fetchall()
        return [dict(r) for r in rows]

    async def get_last_cycle(self) -> dict | None:
        """Get the most recent completed scan cycle, falling back to running."""
        cursor = await self._db.conn.execute(
            """SELECT * FROM scan_cycles
               WHERE status = 'completed'
               ORDER BY finished_at DESC LIMIT 1"""
        )
        row = await cursor.fetchone()
        if row:
            return dict(row)
        # Fall back to any running cycle
        cursor = await self._db.conn.execute(
            "SELECT * FROM scan_cycles ORDER BY started_at DESC LIMIT 1"
        )
        row = await cursor.fetchone()
        return dict(row) if row else None

    async def get_recent_online_count(self) -> int:
        """Count servers online in the last hour of scans."""
        cutoff = int(time.time()) - 3600
        cursor = await self._db.conn.execute(
            """SELECT COUNT(DISTINCT server_id) FROM scan_results
               WHERE scanned_at >= ? AND is_online = 1""",
            (cutoff,),
        )
        return (await cursor.fetchone())[0]

    async def cleanup_old_results(self, older_than_days: int = 90) -> int:
        cutoff = int(time.time()) - (older_than_days * 86400)
        cursor = await self._db.conn.execute(
            "DELETE FROM scan_results WHERE scanned_at < ?", (cutoff,)
        )
        await self._db.conn.commit()
        return cursor.rowcount
