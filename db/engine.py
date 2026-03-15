import logging

import aiosqlite
from pathlib import Path

logger = logging.getLogger(__name__)


class Database:
    def __init__(self, db_path: Path):
        self._db_path = db_path
        self._connection: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self._db_path.parent.mkdir(parents=True, exist_ok=True)
        self._connection = await aiosqlite.connect(self._db_path)
        self._connection.row_factory = aiosqlite.Row
        await self._connection.execute("PRAGMA journal_mode=WAL")
        await self._connection.execute("PRAGMA busy_timeout=5000")
        await self._connection.execute("PRAGMA synchronous=NORMAL")
        await self._connection.execute("PRAGMA foreign_keys=ON")

    async def close(self) -> None:
        if self._connection:
            await self._connection.close()

    async def initialize_schema(self) -> None:
        schema_path = Path(__file__).parent / "schema.sql"
        schema_sql = schema_path.read_text()
        await self._connection.executescript(schema_sql)
        await self._run_migrations()

    async def _run_migrations(self) -> None:
        """Add columns that don't exist yet on the servers table."""
        server_migrations = [
            ("last_latency_ms", "REAL"),
            ("last_players_online", "INTEGER"),
            ("last_players_max", "INTEGER"),
            ("last_version", "TEXT"),
            ("last_motd", "TEXT"),
        ]
        for col, col_type in server_migrations:
            try:
                await self._connection.execute(
                    f"ALTER TABLE servers ADD COLUMN {col} {col_type}"
                )
                logger.info(f"Added column servers.{col}")
            except Exception:
                pass  # Column already exists

        lead_migrations = [
            ("opportunity_score", "REAL DEFAULT 0"),
            ("pain_score", "REAL DEFAULT 0"),
        ]
        for col, col_type in lead_migrations:
            try:
                await self._connection.execute(
                    f"ALTER TABLE lead_scores ADD COLUMN {col} {col_type}"
                )
                logger.info(f"Added column lead_scores.{col}")
            except Exception:
                pass  # Column already exists

        await self._connection.commit()

    @property
    def conn(self) -> aiosqlite.Connection:
        assert self._connection is not None, "Database not connected"
        return self._connection
