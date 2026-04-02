from fastapi import APIRouter, Depends, UploadFile, File, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
import aiofiles
import os
import uuid

from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.responses import ok, fail
from app.features.auth.models import User
from app.config import settings
from app.features.suppression import service

router = APIRouter()
page_router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.post("/upload")
async def upload_suppression_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    try:
        if not file.filename.endswith(".csv"):
            return JSONResponse(status_code=400, content=fail("Only CSV files are supported").model_dump())
            
        uploads = getattr(settings, "UPLOAD_DIR", "/tmp/uploads")
        os.makedirs(uploads, exist_ok=True)
        file_path = os.path.join(uploads, f"suppression_{uuid.uuid4()}_{file.filename}")
        
        async with aiofiles.open(file_path, 'wb') as out_file:
            content = await file.read()
            await out_file.write(content)
            
        # Process in background? Or await here? Sync should be fine since it's just hashing and DB inserting
        count = await service.process_suppression_csv(db, user.id, file_path)
        
        return ok({"message": f"Successfully added {count} emails to the suppression list.", "count": count})
    except Exception as e:
        return JSONResponse(status_code=400, content=fail(str(e)).model_dump())

@router.delete("")
async def clear_suppressions(
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    try:
        await service.clear_suppressions(db, user.id)
        return ok({"message": "Suppression list cleared."})
    except Exception as e:
        return JSONResponse(status_code=400, content=fail(str(e)).model_dump())

@page_router.get("/settings/suppression", response_class=HTMLResponse)
async def suppression_page(request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    count = await service.get_suppression_count(db, user.id)
    return templates.TemplateResponse("settings/suppression.html", {
        "request": request,
        "user": user,
        "suppression_count": count
    })
