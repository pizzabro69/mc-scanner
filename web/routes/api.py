import time

from fastapi import APIRouter, Request

router = APIRouter(prefix="/api")


@router.get("/servers/{server_id}/history")
async def server_history(request: Request, server_id: int, hours: int = 168):
    scan_repo = request.app.state.scan_repo
    since = int(time.time()) - (hours * 3600)
    history = await scan_repo.get_history(server_id, since=since, limit=2000)

    return {
        "server_id": server_id,
        "hours": hours,
        "data": [
            {
                "time": r["scanned_at"],
                "online": bool(r["is_online"]),
                "latency": r.get("latency_ms"),
                "players": r.get("players_online"),
            }
            for r in reversed(history)  # chronological order
        ],
    }


@router.get("/stats/summary")
async def stats_summary(request: Request):
    server_repo = request.app.state.server_repo
    scan_repo = request.app.state.scan_repo
    lead_repo = request.app.state.lead_repo

    return {
        "total_servers": await server_repo.total_active(),
        "online_now": await scan_repo.get_online_count_now(),
        "avg_score": round(await lead_repo.get_avg_score(), 1),
        "countries": await server_repo.count_by_country(),
    }


@router.get("/stats/cycles")
async def scan_cycles(request: Request, limit: int = 24):
    scan_repo = request.app.state.scan_repo
    cycles = await scan_repo.get_recent_cycles(limit=limit)
    return {
        "cycles": [
            {
                "started_at": c["started_at"],
                "finished_at": c.get("finished_at"),
                "scanned": c.get("servers_scanned", 0),
                "online": c.get("servers_online", 0),
                "avg_latency": c.get("avg_latency_ms"),
                "status": c.get("status"),
            }
            for c in cycles
        ]
    }
