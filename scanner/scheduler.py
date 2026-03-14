import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from config.settings import Settings
from scanner.pipeline import ScanPipeline
from scoring.engine import LeadScoringEngine

logger = logging.getLogger(__name__)


class ScanScheduler:
    def __init__(
        self,
        settings: Settings,
        pipeline: ScanPipeline,
        scoring_engine: LeadScoringEngine,
        scrape_func=None,
    ):
        self._settings = settings
        self._pipeline = pipeline
        self._scoring = scoring_engine
        self._scrape_func = scrape_func
        self._scheduler = AsyncIOScheduler()

    def start(self) -> None:
        # Scan every N minutes
        self._scheduler.add_job(
            self._run_scan_and_score,
            "interval",
            minutes=self._settings.scan_interval_minutes,
            id="scan_cycle",
            name="MC Server Scan Cycle",
        )

        # Scrape every N hours
        if self._scrape_func:
            self._scheduler.add_job(
                self._scrape_func,
                "interval",
                hours=self._settings.scrape_interval_hours,
                id="scrape_cycle",
                name="Server List Scrape",
            )

        self._scheduler.start()
        logger.info(
            f"Scheduler started: scan every {self._settings.scan_interval_minutes}min, "
            f"scrape every {self._settings.scrape_interval_hours}h"
        )

    async def _run_scan_and_score(self) -> None:
        try:
            stats = await self._pipeline.run_full_scan()
            logger.info(f"Scan done: {stats}")
            scored = await self._scoring.score_all_servers()
            logger.info(f"Scored {scored} servers")
        except Exception:
            logger.exception("Error in scan/score cycle")

    async def trigger_initial_run(self) -> None:
        """Run scrape + scan + score on startup."""
        try:
            if self._scrape_func:
                logger.info("Running initial scrape...")
                await self._scrape_func()
            logger.info("Running initial scan...")
            await self._pipeline.run_full_scan()
            logger.info("Running initial scoring...")
            await self._scoring.score_all_servers()
        except Exception:
            logger.exception("Error in initial run")

    def shutdown(self) -> None:
        self._scheduler.shutdown(wait=False)
