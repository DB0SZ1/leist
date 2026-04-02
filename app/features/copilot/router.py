from fastapi import APIRouter, Depends, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.features.auth.models import User
from app.features.copilot.service import analyze_email_content
from app.core.database import templates
import structlog

log = structlog.get_logger()
router = APIRouter()
page_router = APIRouter()

class EmailDraftRequest(BaseModel):
    subject: str
    body: str

@page_router.get("/copilot", response_class=HTMLResponse)
async def copilot_page(request: Request, user: User = Depends(get_current_user)):
    return templates.TemplateResponse("dashboard/copilot.html", {
        "request": request,
        "user": user
    })

@router.post("/analyze")
async def analyze_draft(
    req: EmailDraftRequest,
    user: User = Depends(get_current_user)
):
    try:
        analysis = await analyze_email_content(req.subject, req.body)
        return {"success": True, "analysis": analysis}
    except Exception as e:
        log.error("Error analyzing draft", error=str(e))
        return JSONResponse(status_code=500, content={"success": False, "error": str(e)})
