from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.responses import ok, fail
from app.features.auth.models import User
from app.features.bounces.schemas import BounceSubmit
from app.features.bounces import service
from pydantic import BaseModel
from fastapi import HTTPException
import hashlib
from sqlalchemy import select, update
from app.features.bounces.models import BounceEvent
from app.features.workspaces.service import get_active_workspace_id

router = APIRouter()

@router.post("")
async def submit_bounces(
    req: BounceSubmit,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    try:
        res = await service.submit_bounces(db, user, req.bounces)
        return ok(res)
    except Exception as e:
        return JSONResponse(status_code=400, content=fail(str(e)).model_dump())

class BounceSubmission(BaseModel):
    email: str
    bounce_domain: str
    reason: str

@router.post("/submit", summary="Crowdsource a bounce for credits")
async def submit_bounce(
    req: BounceSubmission,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Submits a new organic bounce. If valid, issues a reward credit
    to the workspace.
    """
    try:
        ws_id = await get_active_workspace_id(user, db)
        if not ws_id:
            raise HTTPException(status_code=400, detail="No active workspace")

        # Fast normalization
        target = req.email.lower().strip()
        domain = target.split('@')[-1] if '@' in target else req.bounce_domain
        h = hashlib.sha256(target.encode()).hexdigest()

        # Check if already exists
        stmt = select(BounceEvent).where(BounceEvent.email_hash == h)
        exists = await db.scalar(stmt)
        
        if exists:
            return {"status": "rejected", "detail": "Bounce already registered in global pool."}
            
        # Register the bounce
        new_bounce = BounceEvent(
            email_hash=h,
            bounce_type="hard",
            user_id=user.id
        )
        db.add(new_bounce)

        # Reward workspace (1 credit per valid organic bounce)
        from app.features.workspaces.models import Workspace
        ws_stmt = update(Workspace).where(Workspace.id == ws_id).values(credits=Workspace.credits + 1)
        await db.execute(ws_stmt)
        
        await db.commit()
        
        return {
            "status": "accepted",
            "detail": "Bounce recorded. 1 credit added to workspace.",
            "hash": h
        }
    except Exception as e:
        return JSONResponse(status_code=400, content=fail(str(e)).model_dump())
