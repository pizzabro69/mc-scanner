import asyncio
import logging
import socket

import httpx

from db.repositories.server_repo import ServerRepository

logger = logging.getLogger(__name__)


class GeoFilter:
    """Resolve and geolocate servers using ip-api.com batch API."""

    BATCH_URL = "http://ip-api.com/batch"
    BATCH_SIZE = 100  # ip-api.com limit
    RATE_LIMIT_DELAY = 1.5  # seconds between batch requests

    def __init__(self, server_repo: ServerRepository):
        self._server_repo = server_repo

    async def resolve_missing_countries(self) -> int:
        """Find servers without country data and geolocate them."""
        servers = await self._server_repo.get_servers_without_country(limit=500)
        if not servers:
            return 0

        resolved = 0
        async with httpx.AsyncClient(timeout=15.0) as client:
            for i in range(0, len(servers), self.BATCH_SIZE):
                batch = servers[i : i + self.BATCH_SIZE]
                try:
                    count = await self._resolve_batch(client, batch)
                    resolved += count
                except Exception:
                    logger.exception(f"Error resolving geo batch {i}")

                if i + self.BATCH_SIZE < len(servers):
                    await asyncio.sleep(self.RATE_LIMIT_DELAY)

        await self._server_repo._db.conn.commit()
        logger.info(f"Geo-resolved {resolved} servers")
        return resolved

    async def _resolve_batch(
        self, client: httpx.AsyncClient, servers: list[dict]
    ) -> int:
        # Resolve hostnames to IPs first
        ips = {}
        for s in servers:
            try:
                ip = socket.gethostbyname(s["host"])
                ips[s["id"]] = ip
            except socket.gaierror:
                continue

        if not ips:
            return 0

        # Batch lookup
        payload = [
            {"query": ip, "fields": "status,countryCode,city,lat,lon"}
            for ip in ips.values()
        ]
        resp = await client.post(self.BATCH_URL, json=payload)
        resp.raise_for_status()
        results = resp.json()

        resolved = 0
        server_ids = list(ips.keys())
        for idx, result in enumerate(results):
            if idx >= len(server_ids):
                break
            if result.get("status") != "success":
                continue

            await self._server_repo.update_geo(
                server_id=server_ids[idx],
                country_code=result.get("countryCode"),
                city=result.get("city"),
                lat=result.get("lat"),
                lon=result.get("lon"),
            )
            resolved += 1

        return resolved
