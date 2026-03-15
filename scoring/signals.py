from dataclasses import dataclass


@dataclass
class SignalResult:
    name: str
    raw_value: float
    score: float  # 0-100
    weight: float
    description: str


# ---------------------------------------------------------------------------
# Opportunity signals: how valuable is this server as a lead?
# ---------------------------------------------------------------------------

def avg_players_signal(stats: dict) -> SignalResult:
    """Average concurrent players - primary opportunity signal."""
    avg = stats.get("avg_players") or 0
    if avg >= 50:
        score = 100.0
    elif avg >= 20:
        score = 75.0
    elif avg >= 10:
        score = 50.0
    elif avg >= 5:
        score = 30.0
    elif avg >= 1:
        score = 10.0
    else:
        score = 0.0
    return SignalResult("avg_players", avg, score, weight=0.50, description=f"{avg:.0f} avg players")


def max_players_signal(stats: dict) -> SignalResult:
    """Peak player count - indicates server capacity/ambition."""
    peak = stats.get("max_players_seen") or 0
    if peak >= 100:
        score = 100.0
    elif peak >= 50:
        score = 70.0
    elif peak >= 20:
        score = 40.0
    elif peak >= 5:
        score = 15.0
    else:
        score = 0.0
    return SignalResult("max_players", peak, score, weight=0.25, description=f"{peak} peak players")


def uptime_consistency_signal(stats: dict) -> SignalResult:
    """Servers that are consistently online are real communities.
    Very high downtime = probably abandoned = low opportunity."""
    total = stats.get("total_scans", 0) or 0
    online = stats.get("online_count", 0) or 0
    uptime_pct = (online / total * 100) if total > 0 else 0
    if uptime_pct >= 90:
        score = 100.0
    elif uptime_pct >= 70:
        score = 70.0
    elif uptime_pct >= 50:
        score = 40.0
    elif uptime_pct >= 30:
        score = 15.0
    else:
        score = 0.0
    return SignalResult("uptime", uptime_pct, score, weight=0.25, description=f"{uptime_pct:.0f}% uptime")


OPPORTUNITY_SIGNALS = [
    avg_players_signal,
    max_players_signal,
    uptime_consistency_signal,
]


# ---------------------------------------------------------------------------
# Pain signals: how likely are they experiencing hosting issues?
# ---------------------------------------------------------------------------

def latency_signal(stats: dict) -> SignalResult:
    """Higher avg latency = more hosting pain."""
    avg = stats.get("avg_latency_ms") or 0
    if avg >= 300:
        score = 100.0
    elif avg >= 150:
        score = 70.0
    elif avg >= 80:
        score = 40.0
    elif avg >= 40:
        score = 15.0
    else:
        score = 0.0
    return SignalResult("latency", avg, score, weight=0.30, description=f"{avg:.0f}ms avg")


def p95_latency_signal(stats: dict) -> SignalResult:
    """High P95 latency = spikes / instability."""
    p95 = stats.get("p95_latency_ms") or 0
    if p95 >= 500:
        score = 100.0
    elif p95 >= 250:
        score = 70.0
    elif p95 >= 100:
        score = 35.0
    else:
        score = 0.0
    return SignalResult("p95_latency", p95, score, weight=0.20, description=f"{p95:.0f}ms p95")


def timeout_signal(stats: dict) -> SignalResult:
    """Timeout rate - server failing to respond."""
    total = stats.get("total_scans", 0) or 0
    timeouts = stats.get("timeout_count", 0) or 0
    pct = (timeouts / total * 100) if total > 0 else 0
    if pct >= 25:
        score = 100.0
    elif pct >= 15:
        score = 70.0
    elif pct >= 5:
        score = 35.0
    elif pct >= 1:
        score = 10.0
    else:
        score = 0.0
    return SignalResult("timeouts", pct, score, weight=0.30, description=f"{pct:.1f}% timeouts")


def downtime_signal(stats: dict) -> SignalResult:
    """Some downtime shows instability, but very high = dead server (handled elsewhere)."""
    total = stats.get("total_scans", 0) or 0
    online = stats.get("online_count", 0) or 0
    pct = ((total - online) / total * 100) if total > 0 else 0
    if pct >= 30:
        score = 100.0
    elif pct >= 15:
        score = 65.0
    elif pct >= 5:
        score = 30.0
    elif pct >= 1:
        score = 10.0
    else:
        score = 0.0
    return SignalResult("downtime", pct, score, weight=0.20, description=f"{pct:.1f}% downtime")


PAIN_SIGNALS = [
    latency_signal,
    p95_latency_signal,
    timeout_signal,
    downtime_signal,
]
