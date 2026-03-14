import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from config.settings import Settings
from db.engine import Database
from db.repositories.lead_repo import LeadRepository
from db.repositories.scan_repo import ScanResultRepository
from db.repositories.server_repo import ServerRepository
from scanner.pipeline import ScanPipeline
from scanner.scheduler import ScanScheduler
from scoring.engine import LeadScoringEngine
from scraper.orchestrator import ScrapeOrchestrator
from web.routes import dashboard, servers, leads, api

logger = logging.getLogger(__name__)

WEB_DIR = Path(__file__).parent
templates = Jinja2Templates(directory=str(WEB_DIR / "templates"))


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings: Settings = app.state.settings

    # Database
    db = Database(settings.db_path)
    await db.connect()
    await db.initialize_schema()
    app.state.db = db

    # Repositories
    server_repo = ServerRepository(db)
    scan_repo = ScanResultRepository(db)
    lead_repo = LeadRepository(db)
    app.state.server_repo = server_repo
    app.state.scan_repo = scan_repo
    app.state.lead_repo = lead_repo

    # Pipeline & scoring
    pipeline = ScanPipeline(settings, server_repo, scan_repo)
    scoring = LeadScoringEngine(settings, server_repo, scan_repo, lead_repo)
    app.state.pipeline = pipeline
    app.state.scoring = scoring

    # Scraper
    orchestrator = ScrapeOrchestrator(settings, db, server_repo)
    app.state.orchestrator = orchestrator

    # Scheduler
    scheduler = ScanScheduler(
        settings, pipeline, scoring, scrape_func=orchestrator.run_full_scrape
    )
    scheduler.start()
    app.state.scheduler = scheduler

    # Suppress noisy DNS resolution errors from mcstatus SRV lookups
    loop = asyncio.get_event_loop()
    _default_handler = loop.get_exception_handler()

    def _quiet_dns_handler(loop, context):
        exc = context.get("exception")
        if isinstance(exc, OSError) and "address" in str(exc).lower() or "name" in str(exc).lower():
            return  # Suppress DNS resolution noise
        if _default_handler:
            _default_handler(loop, context)
        else:
            loop.default_exception_handler(context)

    loop.set_exception_handler(_quiet_dns_handler)

    # Trigger initial run in background
    asyncio.create_task(scheduler.trigger_initial_run())

    yield

    # Shutdown
    scheduler.shutdown()
    await db.close()


def create_app(settings: Settings | None = None) -> FastAPI:
    if settings is None:
        settings = Settings()

    app = FastAPI(title="MC Scanner", lifespan=lifespan)
    app.state.settings = settings

    # Static files
    static_dir = WEB_DIR / "static"
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Templates
    app.state.templates = templates

    # Routes
    app.include_router(dashboard.router)
    app.include_router(servers.router)
    app.include_router(leads.router)
    app.include_router(api.router)

    return app
