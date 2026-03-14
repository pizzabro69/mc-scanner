import asyncio
import logging
import time

from config.settings import Settings
from db.repositories.scan_repo import ScanResultRepository
from db.repositories.server_repo import ServerRepository
from scanner.ping import ping_server

logger = logging.getLogger(__name__)


class ScanPipeline:
    def __init__(
        self,
        settings: Settings,
        server_repo: ServerRepository,
        scan_repo: ScanResultRepository,
    ):
        self._settings = settings
        self._server_repo = server_repo
        self._scan_repo = scan_repo
        self._running = False

    async def run_full_scan(self) -> dict:
        """Execute a full scan cycle across all active servers."""
        if self._running:
            logger.warning("Scan already in progress, skipping")
            return {"scanned": 0, "online": 0, "total_latency": 0.0}

        self._running = True
        try:
            return await self._do_scan()
        finally:
            self._running = False

    async def _do_scan(self) -> dict:
        """Execute a full scan cycle across all active servers."""
        servers = await self._server_repo.get_active_servers()
        if not servers:
            logger.info("No active servers to scan")
            return {"scanned": 0, "online": 0, "total_latency": 0.0}

        logger.info(f"Starting scan cycle for {len(servers)} servers")
        cycle_id = await self._scan_repo.start_cycle()

        semaphore = asyncio.Semaphore(self._settings.scan_concurrency)
        stats = {"scanned": 0, "online": 0, "total_latency": 0.0}
        lock = asyncio.Lock()

        async def scan_one(server: dict) -> None:
            async with semaphore:
                result = await ping_server(
                    server["host"],
                    server["port"],
                    timeout=self._settings.scan_timeout_seconds,
                )

            now = int(time.time())
            await self._scan_repo.insert_result(
                server_id=server["id"],
                scanned_at=now,
                is_online=result.is_online,
                latency_ms=result.latency_ms,
                players_online=result.players_online,
                players_max=result.players_max,
                version_name=result.version_name,
                version_protocol=result.version_protocol,
                motd=result.motd,
                error_message=result.error_message,
            )

            if result.is_online:
                await self._server_repo.update_last_seen(server["id"], now)
                await self._server_repo.update_last_scan_data(
                    server["id"],
                    latency_ms=result.latency_ms,
                    players_online=result.players_online,
                    players_max=result.players_max,
                    version=result.version_name,
                    motd=result.motd,
                )

            async with lock:
                stats["scanned"] += 1
                if result.is_online:
                    stats["online"] += 1
                    stats["total_latency"] += result.latency_ms or 0

            if stats["scanned"] % 200 == 0:
                logger.info(f"Scan progress: {stats['scanned']}/{len(servers)}")

        tasks = [asyncio.create_task(scan_one(s)) for s in servers]
        results = await asyncio.gather(*tasks, return_exceptions=True)

        # Log any unexpected errors
        errors = 0
        for i, r in enumerate(results):
            if isinstance(r, Exception):
                errors += 1
                if errors <= 5:
                    logger.error(f"Scan task error for server {servers[i]['host']}: {r}")
        if errors > 5:
            logger.error(f"... and {errors - 5} more scan task errors")

        await self._scan_repo.finish_cycle(cycle_id, stats)
        await self._db_commit()

        logger.info(
            f"Scan cycle complete: {stats['scanned']} scanned, "
            f"{stats['online']} online"
        )
        return stats

    async def _db_commit(self) -> None:
        await self._scan_repo._db.conn.commit()
