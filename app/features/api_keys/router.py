from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.responses import ok, fail
from app.features.auth.models import User
from app.features.api_keys.models import APIKey
from app.features.api_keys.schemas import KeyCreateRequest
from app.features.api_keys import service
from sqlalchemy import select
import uuid
import secrets
from passlib.context import CryptContext

from app.features.workspaces.models import Workspace
from app.features.workspaces.service import get_active_workspace_id

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

router = APIRouter()
page_router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.post("")
async def create_api_key(
    req: KeyCreateRequest,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    ws_id = await get_active_workspace_id(user, db)
    workspace = await db.scalar(select(Workspace).where(Workspace.id == ws_id))
    if user.plan not in ["pro", "agency"]:
        return JSONResponse(status_code=403, content=fail("API Key creation requires Pro plan or higher").model_dump())
     # Custom White-Label Prefix support (Phase 4.7)
    prefix = "listintel"
    
    # Simple check if workspace has a 'white_label' metadata config (simulated logic)
    # E.g. {"custom_prefix": "agencyX"}
    if hasattr(workspace, "metadata_") and workspace.metadata_ and "custom_prefix" in workspace.metadata_:
        prefix = workspace.metadata_["custom_prefix"]
    elif user.plan == "agency": # Changed from user.plan_id to user.plan for consistency with existing code
        prefix = "agency"

    # Generate Secure Key
    raw_key = f"{prefix}_{secrets.token_urlsafe(32)}"
    key_hash = pwd_context.hash(raw_key)

    key = APIKey(
        user_id=user.id,
        key_hash=key_hash,
        label=req.label,
        ip_whitelist=req.ip_whitelist
    )
    db.add(key)
    await db.commit()
    await db.refresh(key)
    
    return ok({
        "id": key.id,
        "label": key.label,
        "raw_key": raw_key,
        "created_at": key.created_at
    })

@router.delete("/{key_id}")
async def revoke_api_key(
    key_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    key = await db.scalar(select(APIKey).where(APIKey.id == key_id, APIKey.user_id == user.id))
    if not key:
        raise HTTPException(status_code=404, detail="Key not found")
        
    key.is_revoked = True
    await db.commit()
    return ok({"message": "Key revoked"})

@page_router.get("/api-keys", response_class=HTMLResponse)
async def api_keys_page(request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    keys = await db.scalars(select(APIKey).where(APIKey.user_id == user.id, APIKey.is_revoked == False))
    return templates.TemplateResponse("api_keys/index.html", {
        "request": request,
        "user": user,
        "keys": keys.all()
    })
