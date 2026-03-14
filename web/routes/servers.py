import json

from fastapi import APIRouter, Request

router = APIRouter(prefix="/servers")


@router.get("")
async def server_list(
    request: Request,
    page: int = 1,
    country: str | None = None,
    search: str | None = None,
    sort: str = "last_seen",
    online: str | None = None,
):
    server_repo = request.app.state.server_repo
    countries = await server_repo.count_by_country()
    servers, total = await server_repo.get_servers_paginated(
        page=page, per_page=50, country=country, search=search, sort_by=sort,
        online_only=(online == "1"),
    )
    total_pages = (total + 49) // 50

    return request.app.state.templates.TemplateResponse(
        "server_list.html",
        {
            "request": request,
            "servers": servers,
            "total": total,
            "page": page,
            "total_pages": total_pages,
            "country": country,
            "search": search or "",
            "sort": sort,
            "online": online or "",
            "countries": countries,
        },
    )


@router.get("/{server_id}")
async def server_detail(request: Request, server_id: int):
    server_repo = request.app.state.server_repo
    scan_repo = request.app.state.scan_repo
    lead_repo = request.app.state.lead_repo

    server = await server_repo.get_server_by_id(server_id)
    if not server:
        return request.app.state.templates.TemplateResponse(
            "server_detail.html",
            {"request": request, "server": None, "error": "Server not found"},
        )

    latest_scan = await scan_repo.get_latest_for_server(server_id)
    lead_score = await lead_repo.get_score_for_server(server_id)
    history = await scan_repo.get_history(server_id, limit=500)

    # Parse score details
    score_details = {}
    if lead_score and lead_score.get("score_details"):
        try:
            score_details = json.loads(lead_score["score_details"])
        except (json.JSONDecodeError, TypeError):
            pass

    return request.app.state.templates.TemplateResponse(
        "server_detail.html",
        {
            "request": request,
            "server": server,
            "latest_scan": latest_scan,
            "lead_score": lead_score,
            "score_details": score_details,
            "history": history,
        },
    )
