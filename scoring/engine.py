import json
import logging
import time

from config.settings import Settings
from db.repositories.lead_repo import LeadRepository
from db.repositories.scan_repo import ScanResultRepository
from db.repositories.server_repo import ServerRepository
from scoring.signals import ALL_SIGNALS

logger = logging.getLogger(__name__)


class LeadScoringEngine:
    def __init__(
        self,
        settings: Settings,
        server_repo: ServerRepository,
        scan_repo: ScanResultRepository,
        lead_repo: LeadRepository,
    ):
        self._settings = settings
        self._server_repo = server_repo
        self._scan_repo = scan_repo
        self._lead_repo = lead_repo

    async def score_all_servers(self) -> int:
        """Recalculate lead scores for all active servers."""
        since = int(time.time()) - (self._settings.scoring_window_hours * 3600)
        servers = await self._server_repo.get_active_servers()
        scored = 0

        for server in servers:
            try:
                stats = await self._scan_repo.get_stats_for_scoring(
                    server["id"], since
                )
                if (stats.get("total_scans") or 0) < self._settings.min_scans_for_scoring:
                    continue

                signals = [fn(stats) for fn in ALL_SIGNALS]
                total_weight = sum(s.weight for s in signals)
                composite = sum(s.score * s.weight for s in signals) / total_weight

                # Multiplier: high players + bad perf = prime lead
                perf_signals = [
                    s for s in signals if s.name in ("downtime", "latency", "timeouts")
                ]
                avg_perf_score = sum(s.score for s in perf_signals) / len(perf_signals)
                player_signal = next(s for s in signals if s.name == "player_load")

                if player_signal.raw_value > 20 and avg_perf_score > 40:
                    composite = min(composite * 1.3, 100)

                # Zero out tiny/dead servers
                if player_signal.raw_value < 3 and (stats.get("avg_latency_ms") or 0) == 0:
                    composite = 0

                details = {
                    s.name: {
                        "raw": round(s.raw_value, 2),
                        "score": round(s.score, 2),
                        "weight": s.weight,
                        "desc": s.description,
                    }
                    for s in signals
                }

                await self._lead_repo.upsert_score(
                    server_id=server["id"],
                    score=round(composite, 2),
                    downtime_pct=stats.get("downtime_pct", 0),
                    avg_latency_ms=stats.get("avg_latency_ms"),
                    p95_latency_ms=stats.get("p95_latency_ms"),
                    timeout_count=stats.get("timeout_count", 0),
                    avg_players=stats.get("avg_players"),
                    max_players=stats.get("max_players_seen"),
                    score_details=json.dumps(details),
                    calculated_at=int(time.time()),
                    window_hours=self._settings.scoring_window_hours,
                )
                scored += 1
            except Exception:
                logger.exception(f"Error scoring server {server['id']}")

        await self._lead_repo._db.conn.commit()
        return scored
