from dataclasses import dataclass


@dataclass
class SignalResult:
    name: str
    raw_value: float
    score: float  # 0-100
    weight: float
    description: str


def downtime_signal(stats: dict) -> SignalResult:
    """Higher downtime % = better lead. 50% offline = max score."""
    total = stats.get("total_scans", 0) or 0
    online = stats.get("online_count", 0) or 0
    pct = ((total - online) / total * 100) if total > 0 else 0
    score = min(pct * 2, 100)
    return SignalResult("downtime", pct, score, weight=0.30, description=f"{pct:.1f}% downtime")


def latency_signal(stats: dict) -> SignalResult:
    """Higher avg latency = better lead. 500ms+ = max score."""
    avg = stats.get("avg_latency_ms") or 0
    score = max(0, min((avg - 50) / 4.5, 100))
    return SignalResult("latency", avg, score, weight=0.20, description=f"{avg:.0f}ms avg")


def latency_variance_signal(stats: dict) -> SignalResult:
    """High P95/avg ratio = unstable. Ratio of 4x = max score."""
    avg = stats.get("avg_latency_ms") or 1
    p95 = stats.get("p95_latency_ms") or avg
    ratio = p95 / avg if avg > 0 else 1
    score = max(0, min((ratio - 1) * 33, 100))
    return SignalResult("latency_variance", ratio, score, weight=0.10, description=f"P95/avg: {ratio:.1f}x")


def timeout_signal(stats: dict) -> SignalResult:
    """Higher timeout rate = better lead. 33% = max score."""
    total = stats.get("total_scans", 0) or 0
    timeouts = stats.get("timeout_count", 0) or 0
    pct = (timeouts / total * 100) if total > 0 else 0
    score = min(pct * 3, 100)
    return SignalResult("timeouts", pct, score, weight=0.20, description=f"{pct:.1f}% timeouts")


def player_load_signal(stats: dict) -> SignalResult:
    """More players = more valuable lead target."""
    avg_players = stats.get("avg_players") or 0
    if avg_players < 5:
        score = 0.0
    elif avg_players < 20:
        score = 30.0
    elif avg_players < 50:
        score = 60.0
    else:
        score = 100.0
    return SignalResult("player_load", avg_players, score, weight=0.20, description=f"{avg_players:.0f} avg players")


ALL_SIGNALS = [
    downtime_signal,
    latency_signal,
    latency_variance_signal,
    timeout_signal,
    player_load_signal,
]
