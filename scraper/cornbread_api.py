import logging
import struct
import socket

import httpx

from scraper.base import BaseScraper, DiscoveredServer

logger = logging.getLogger(__name__)

PAGE_SIZE = 100


def int_ip_to_str(ip_int: int) -> str:
    """Convert a 32-bit integer IP to dotted-quad string."""
    return socket.inet_ntoa(struct.pack("!I", ip_int))


class CornbreadAPIScraper(BaseScraper):
    """Scraper for api.cornbread2100.com - structured JSON API with geo data."""

    name = "cornbread_api"
    BASE_URL = "https://api.cornbread2100.com"

    async def scrape(self, countries: list[str]) -> list[DiscoveredServer]:
        servers: list[DiscoveredServer] = []

        async with httpx.AsyncClient(timeout=30.0) as client:
            for country_code in countries:
                try:
                    page_servers = await self._scrape_country(client, country_code)
                    servers.extend(page_servers)
                    logger.info(
                        f"[cornbread] {country_code}: found {len(page_servers)} servers"
                    )
                except Exception:
                    logger.exception(f"[cornbread] Error scraping {country_code}")

        return servers

    async def _scrape_country(
        self, client: httpx.AsyncClient, country_code: str
    ) -> list[DiscoveredServer]:
        servers: list[DiscoveredServer] = []
        skip = 0

        while True:
            try:
                resp = await client.get(
                    f"{self.BASE_URL}/servers",
                    params={
                        "country": country_code,
                        "skip": skip,
                        "limit": PAGE_SIZE,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPStatusError as e:
                logger.warning(f"[cornbread] HTTP {e.response.status_code} for {country_code} skip={skip}")
                break
            except Exception:
                logger.exception(f"[cornbread] Request error for {country_code} skip={skip}")
                break

            if not data:
                break

            for entry in data:
                ip_raw = entry.get("ip")
                port = entry.get("port", 25565)
                if ip_raw is None:
                    continue

                # API returns IPs as 32-bit integers
                if isinstance(ip_raw, int):
                    try:
                        host = int_ip_to_str(ip_raw)
                    except (struct.error, OSError):
                        continue
                else:
                    host = str(ip_raw).strip()

                geo = entry.get("geo") or {}

                servers.append(
                    DiscoveredServer(
                        host=host,
                        port=int(port),
                        country_code=geo.get("country", country_code),
                        city=geo.get("city"),
                        latitude=geo.get("lat"),
                        longitude=geo.get("lon"),
                        source=self.name,
                    )
                )

            if len(data) < PAGE_SIZE:
                break
            skip += PAGE_SIZE

        return servers
