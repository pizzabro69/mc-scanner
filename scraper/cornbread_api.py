import logging

import httpx

from scraper.base import BaseScraper, DiscoveredServer

logger = logging.getLogger(__name__)

# Country code to name mapping for the API
COUNTRY_NAMES = {
    "NL": "Netherlands",
    "DE": "Germany",
    "BE": "Belgium",
    "GB": "United Kingdom",
    "FR": "France",
}


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
        page = 0

        while True:
            try:
                resp = await client.get(
                    f"{self.BASE_URL}/servers",
                    params={
                        "country": COUNTRY_NAMES.get(country_code, country_code),
                        "page": page,
                    },
                )
                resp.raise_for_status()
                data = resp.json()
            except httpx.HTTPStatusError as e:
                logger.warning(f"[cornbread] HTTP {e.response.status_code} for {country_code} page {page}")
                break
            except Exception:
                logger.exception(f"[cornbread] Request error for {country_code} page {page}")
                break

            if not data:
                break

            for entry in data:
                host = entry.get("host") or entry.get("ip")
                port = entry.get("port", 25565)
                if not host:
                    continue

                servers.append(
                    DiscoveredServer(
                        host=str(host).strip(),
                        port=int(port),
                        country_code=country_code,
                        city=entry.get("city"),
                        latitude=entry.get("lat"),
                        longitude=entry.get("lon"),
                        source=self.name,
                    )
                )

            # If we got fewer results than a full page, we're done
            if len(data) < 25:
                break
            page += 1

        return servers
