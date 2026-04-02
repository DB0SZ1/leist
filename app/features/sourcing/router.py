from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import HTMLResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.features.auth.models import User
from app.core.dependencies import get_current_user
from app.core.database import templates

router = APIRouter()
page_router = APIRouter()

@router.get("/search")
async def search_leads(
    q: str = Query("", description="Keywords to search, e.g. CTO software"),
    industry: str = Query(None),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Simulates a Lead Source DB (Tool 2). 
    In production, this routes to Apollo/ZoomInfo/Scraper API.
    """
    # Scaffold mock results
    results = [
        {"name": "Sarah Miller", "title": "VP Engineering", "company": "TechFlow", "email": "sarah.m@techflow.inc", "score": 98},
        {"name": "David Chen", "title": "Co-founder & CTO", "company": "Nexus Systems", "email": "dchen@nexus.io", "score": 92},
        {"name": "Elena Rodriguez", "title": "Director of Technology", "company": "Vantage", "email": "elena.ro@vantage.corp", "score": 88},
    ]
    
    # Simple mock filtering
    if q:
        results = [r for r in results if q.lower() in r['title'].lower() or q.lower() in r['company'].lower()]
        
    return {"status": "success", "results": results, "total": len(results)}

@page_router.get("/sourcing", response_class=HTMLResponse)
async def sourcing_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("dashboard/sourcing.html", {
        "request": request,
        "user": user
    })
