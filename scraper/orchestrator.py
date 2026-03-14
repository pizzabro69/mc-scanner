import logging
import time

from config.settings import Settings
from db.engine import Database
from db.repositories.server_repo import ServerRepository
from scraper.base import DiscoveredServer
from scraper.cornbread_api import CornbreadAPIScraper
from scraper.geo_filter import GeoFilter
from scraper.minecraft_mp import MinecraftMPScraper

logger = logging.getLogger(__name__)


class ScrapeOrchestrator:
    def __init__(self, settings: Settings, db: Database, server_repo: ServerRepository):
        self._settings = settings
        self._db = db
        self._server_repo = server_repo
        self._scrapers = [
            CornbreadAPIScraper(),
            MinecraftMPScraper(),
        ]
        self._geo_filter = GeoFilter(server_repo)

    async def run_full_scrape(self) -> dict:
        """Run all scrapers, deduplicate, store, and geo-resolve."""
        all_servers: list[DiscoveredServer] = []
        countries = self._settings.target_countries

        for scraper in self._scrapers:
            try:
                logger.info(f"Running scraper: {scraper.name}")
                servers = await scraper.scrape(countries)
                all_servers.extend(servers)
                logger.info(f"[{scraper.name}] found {len(servers)} total servers")

                # Log to scrape_log
                await self._log_scrape(scraper.name, len(servers))
            except Exception:
                logger.exception(f"Scraper {scraper.name} failed")
                await self._log_scrape(scraper.name, 0, error=True)

        # Deduplicate by (host, port)
        seen = set()
        unique_servers = []
        for s in all_servers:
            key = (s.host.lower(), s.port)
            if key not in seen:
                seen.add(key)
                unique_servers.append(s)

        logger.info(
            f"Deduplication: {len(all_servers)} -> {len(unique_servers)} unique servers"
        )

        # Upsert into database
        new_count = 0
        for s in unique_servers:
            await self._server_repo.upsert_server(
                host=s.host,
                port=s.port,
                country_code=s.country_code,
                city=s.city,
                lat=s.latitude,
                lon=s.longitude,
                source=s.source,
            )

        await self._db.conn.commit()

        # Geo-resolve servers missing country data
        try:
            resolved = await self._geo_filter.resolve_missing_countries()
            logger.info(f"Geo-resolved {resolved} servers")
        except Exception:
            logger.exception("Geo-resolution failed")

        # Deactivate stale servers
        stale = await self._server_repo.deactivate_stale_servers()
        if stale:
            logger.info(f"Deactivated {stale} stale servers")

        total_active = await self._server_repo.total_active()
        logger.info(f"Total active servers: {total_active}")

        return {
            "scraped": len(all_servers),
            "unique": len(unique_servers),
            "active": total_active,
        }

    async def _log_scrape(
        self, source_name: str, count: int, error: bool = False
    ) -> None:
        now = int(time.time())
        await self._db.conn.execute(
            """INSERT INTO scrape_log (source_name, scraped_at, servers_found, status, error_message)
               VALUES (?, ?, ?, ?, ?)""",
            (source_name, now, count, "error" if error else "success", None),
        )
