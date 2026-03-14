import asyncio
import logging
import re

import httpx
from bs4 import BeautifulSoup

from scraper.base import BaseScraper, DiscoveredServer

logger = logging.getLogger(__name__)

COUNTRY_SLUGS = {
    "NL": "netherlands",
    "DE": "germany",
    "BE": "belgium",
    "GB": "united-kingdom",
    "FR": "france",
}


class MinecraftMPScraper(BaseScraper):
    """Scraper for minecraft-mp.com country-filtered server lists."""

    name = "minecraft_mp"
    BASE_URL = "https://minecraft-mp.com/country"

    async def scrape(self, countries: list[str]) -> list[DiscoveredServer]:
        servers: list[DiscoveredServer] = []

        async with httpx.AsyncClient(
            timeout=20.0,
            follow_redirects=True,
            headers={"User-Agent": "MCScanner/1.0 (server monitoring tool)"},
        ) as client:
            for country_code in countries:
                slug = COUNTRY_SLUGS.get(country_code)
                if not slug:
                    continue
                try:
                    country_servers = await self._scrape_country(
                        client, slug, country_code
                    )
                    servers.extend(country_servers)
                    logger.info(
                        f"[minecraft-mp] {country_code}: found {len(country_servers)} servers"
                    )
                except Exception:
                    logger.exception(f"[minecraft-mp] Error scraping {country_code}")

        return servers

    async def _scrape_country(
        self, client: httpx.AsyncClient, slug: str, country_code: str
    ) -> list[DiscoveredServer]:
        servers: list[DiscoveredServer] = []

        for page in range(1, 20):  # Max 20 pages per country
            url = f"{self.BASE_URL}/{slug}/" if page == 1 else f"{self.BASE_URL}/{slug}/{page}/"
            try:
                resp = await client.get(url)
                if resp.status_code == 404:
                    break
                resp.raise_for_status()
            except httpx.HTTPStatusError:
                break

            soup = BeautifulSoup(resp.text, "lxml")
            table = soup.find("table", class_="table")
            if not table:
                break

            rows = table.find_all("tr")[1:]  # Skip header
            if not rows:
                break

            for row in rows:
                try:
                    # Look for the server address in a clipboard/copy element or td
                    addr_el = row.find(attrs={"data-clipboard-text": True})
                    if addr_el:
                        addr = addr_el["data-clipboard-text"].strip()
                    else:
                        tds = row.find_all("td")
                        if len(tds) < 2:
                            continue
                        addr = tds[1].get_text(strip=True)

                    if not addr:
                        continue

                    host, port = self._parse_address(addr)
                    if host:
                        servers.append(
                            DiscoveredServer(
                                host=host,
                                port=port,
                                country_code=country_code,
                                source=self.name,
                            )
                        )
                except Exception:
                    continue

            # Rate limit: 2 seconds between pages
            await asyncio.sleep(2)

        return servers

    @staticmethod
    def _parse_address(addr: str) -> tuple[str, int]:
        """Parse 'host:port' or 'host' into (host, port)."""
        addr = addr.strip().lower()
        if ":" in addr:
            parts = addr.rsplit(":", 1)
            try:
                return parts[0], int(parts[1])
            except ValueError:
                return parts[0], 25565
        return addr, 25565
