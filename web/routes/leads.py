import csv
import io

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/leads")


@router.get("")
async def leads_list(
    request: Request,
    page: int = 1,
    min_score: float = 0,
    country: str | None = None,
    sort: str = "score",
):
    lead_repo = request.app.state.lead_repo
    server_repo = request.app.state.server_repo

    leads, total = await lead_repo.get_leads_paginated(
        page=page, per_page=50, min_score=min_score, country=country, sort_by=sort,
    )
    total_pages = (total + 49) // 50
    countries = await server_repo.count_by_country()

    return request.app.state.templates.TemplateResponse(
        "leads.html",
        {
            "request": request,
            "leads": leads,
            "total": total,
            "page": page,
            "total_pages": total_pages,
            "min_score": min_score,
            "country": country,
            "sort": sort,
            "countries": countries,
        },
    )


@router.get("/export")
async def export_leads(
    request: Request,
    min_score: float = 0,
    country: str | None = None,
):
    lead_repo = request.app.state.lead_repo
    leads, _ = await lead_repo.get_leads_paginated(
        page=1, per_page=10000, min_score=min_score, country=country,
    )

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        "Host", "Port", "Country", "City", "Score", "Downtime %",
        "Avg Latency (ms)", "P95 Latency (ms)", "Timeouts",
        "Avg Players", "Max Players",
    ])
    for lead in leads:
        writer.writerow([
            lead.get("host", ""),
            lead.get("port", ""),
            lead.get("country_code", ""),
            lead.get("city", ""),
            lead.get("score", 0),
            round(lead.get("downtime_pct", 0), 1),
            round(lead.get("avg_latency_ms") or 0, 1),
            round(lead.get("p95_latency_ms") or 0, 1),
            lead.get("timeout_count", 0),
            round(lead.get("avg_players") or 0, 1),
            lead.get("max_players", 0),
        ])

    output.seek(0)
    return StreamingResponse(
        iter([output.getvalue()]),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=mc_leads.csv"},
    )
