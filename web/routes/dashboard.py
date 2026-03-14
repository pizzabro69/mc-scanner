from fastapi import APIRouter, Request

router = APIRouter()


@router.get("/")
async def dashboard(request: Request):
    server_repo = request.app.state.server_repo
    scan_repo = request.app.state.scan_repo
    lead_repo = request.app.state.lead_repo

    total_servers = await server_repo.total_active()
    online_now = await scan_repo.get_recent_online_count()
    top_leads = await lead_repo.get_top_leads(limit=10)
    countries = await server_repo.count_by_country()
    recent_cycles = await scan_repo.get_recent_cycles(limit=24)
    avg_score = await lead_repo.get_avg_score()
    last_cycle = await scan_repo.get_last_cycle()
    error_breakdown = await scan_repo.get_error_breakdown(limit_hours=1)

    return request.app.state.templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "total_servers": total_servers,
            "online_now": online_now,
            "top_leads": top_leads,
            "countries": countries,
            "recent_cycles": recent_cycles,
            "avg_score": round(avg_score, 1),
            "last_cycle": last_cycle,
            "error_breakdown": error_breakdown,
        },
    )
