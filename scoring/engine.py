import json
import logging
import time

from config.settings import Settings
from db.repositories.lead_repo import LeadRepository
from db.repositories.scan_repo import ScanResultRepository
from db.repositories.server_repo import ServerRepository
from scoring.signals import OPPORTUNITY_SIGNALS, PAIN_SIGNALS

logger = logging.getLogger(__name__)


def _weighted_score(signals) -> float:
    total_weight = sum(s.weight for s in signals)
    if total_weight == 0:
        return 0
    return sum(s.score * s.weight for s in signals) / total_weight


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

                # Compute opportunity and pain sub-scores
                opp_signals = [fn(stats) for fn in OPPORTUNITY_SIGNALS]
                pain_signals = [fn(stats) for fn in PAIN_SIGNALS]

                opportunity = _weighted_score(opp_signals)
                pain = _weighted_score(pain_signals)

                # Final score: opportunity gates the score, pain multiplies it.
                # A dead server with high pain still scores near zero.
                # Formula: opportunity * (0.4 + 0.6 * pain/100)
                # - Server with 0 pain still gets 40% of opportunity (good server, might upgrade)
                # - Server with max pain gets full opportunity score
                # - Server with 0 opportunity gets near-zero regardless of pain
                if opportunity < 1:
                    final_score = 0.0
                else:
                    pain_factor = 0.4 + 0.6 * (pain / 100)
                    final_score = opportunity * pain_factor

                # Clamp
                final_score = max(0, min(final_score, 100))

                # Build details for both signal groups
                all_signals = opp_signals + pain_signals
                details = {
                    "opportunity_score": round(opportunity, 2),
                    "pain_score": round(pain, 2),
                    "signals": {
                        s.name: {
                            "raw": round(s.raw_value, 2),
                            "score": round(s.score, 2),
                            "weight": s.weight,
                            "desc": s.description,
                        }
                        for s in all_signals
                    },
                }

                await self._lead_repo.upsert_score(
                    server_id=server["id"],
                    score=round(final_score, 2),
                    opportunity_score=round(opportunity, 2),
                    pain_score=round(pain, 2),
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
