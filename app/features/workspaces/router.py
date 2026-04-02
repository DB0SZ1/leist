from fastapi import APIRouter, Depends, Request, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from app.core.database import get_db, templates
from app.core.dependencies import get_current_user
from app.features.auth.models import User
from app.features.workspaces.models import Workspace, WorkspaceMember
from typing import Optional

router = APIRouter()
page_router = APIRouter()

class CreateWorkspaceReq(BaseModel):
    name: str

class InviteMemberReq(BaseModel):
    email: str
    role: str

class SwitchWorkspaceReq(BaseModel):
    workspace_id: Optional[str] = None # None means revert to personal workspace

class UpdateBrandingReq(BaseModel):
    brand_company_name: str
    brand_color: str
    brand_logo_url: str

@page_router.get("/workspaces", response_class=HTMLResponse)
async def workspaces_page(request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    # Get all workspaces the user is a member of
    stmt = select(Workspace, WorkspaceMember).join(WorkspaceMember, Workspace.id == WorkspaceMember.workspace_id).where(WorkspaceMember.user_id == user.id)
    results = await db.execute(stmt)
    my_workspaces = []
    
    current_workspace_name = "Personal Account"
    
    for ws, mem in results:
        my_workspaces.append({"id": str(ws.id), "name": ws.name, "role": mem.role, "credits": ws.credits_remaining})
        if user.active_workspace_id == ws.id:
            current_workspace_name = ws.name

    # If active workspace, get members
    active_members = []
    if user.active_workspace_id:
        mem_stmt = select(WorkspaceMember, User).join(User, User.id == WorkspaceMember.user_id).where(WorkspaceMember.workspace_id == user.active_workspace_id)
        mems = await db.execute(mem_stmt)
        for m, u in mems:
            active_members.append({
                "id": str(m.id),
                "email": u.email,
                "role": m.role,
                "joined": m.created_at
            })
            
    return templates.TemplateResponse("dashboard/workspaces.html", {
        "request": request,
        "user": user,
        "my_workspaces": my_workspaces,
        "active_members": active_members,
        "current_workspace_name": current_workspace_name
    })

@router.post("")
async def create_workspace(req: CreateWorkspaceReq, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    if user.plan_id not in ["agency", "growth"]:
        return JSONResponse(status_code=403, content={"success": False, "error": "Workspaces require Growth or Agency plan."})
        
    ws = Workspace(name=req.name, owner_id=user.id, credits_remaining=0)
    db.add(ws)
    await db.flush()
    
    mem = WorkspaceMember(workspace_id=ws.id, user_id=user.id, role="owner")
    db.add(mem)
    
    # Auto-switch context
    user.active_workspace_id = ws.id
    await db.commit()
    
    return {"success": True, "workspace_id": str(ws.id)}

@router.post("/switch")
async def switch_workspace(req: SwitchWorkspaceReq, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    if not req.workspace_id:
        user.active_workspace_id = None
    else:
        # Verify membership
        mem = await db.scalar(select(WorkspaceMember).where(WorkspaceMember.workspace_id == req.workspace_id, WorkspaceMember.user_id == user.id))
        if not mem:
            return JSONResponse(status_code=403, content={"success": False, "error": "You are not a member of this workspace"})
        user.active_workspace_id = req.workspace_id
        
    await db.commit()
    return {"success": True}

@router.post("/invite")
async def invite_member(req: InviteMemberReq, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    if not user.active_workspace_id:
        return JSONResponse(status_code=400, content={"success": False, "error": "You must be in a workspace context to invite"})
        
    # Check if target user exists
    target = await db.scalar(select(User).where(User.email == req.email.lower().strip()))
    if not target:
        return JSONResponse(status_code=404, content={"success": False, "error": "User with that email does not exist. Have them register first."})
        
    # Ensure inviter is owner/admin
    mem = await db.scalar(select(WorkspaceMember).where(WorkspaceMember.workspace_id == user.active_workspace_id, WorkspaceMember.user_id == user.id))
    if not mem or mem.role not in ["owner", "admin"]:
        return JSONResponse(status_code=403, content={"success": False, "error": "Only admins can invite members."})
        
    # Check if already a member
    existing = await db.scalar(select(WorkspaceMember).where(WorkspaceMember.workspace_id == user.active_workspace_id, WorkspaceMember.user_id == target.id))
    if existing:
        return JSONResponse(status_code=400, content={"success": False, "error": "User is already in this workspace."})
        
    new_mem = WorkspaceMember(workspace_id=user.active_workspace_id, user_id=target.id, role=req.role)
    db.add(new_mem)
    await db.commit()
    
    return {"success": True, "message": f"Added {target.email} to workspace"}

@router.patch("/brand")
async def update_branding(req: UpdateBrandingReq, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    if not user.active_workspace_id:
        return JSONResponse(status_code=400, content={"success": False, "error": "No active workspace context"})
        
    mem = await db.scalar(select(WorkspaceMember).where(WorkspaceMember.workspace_id == user.active_workspace_id, WorkspaceMember.user_id == user.id))
    if not mem or mem.role not in ["owner", "admin"]:
        return JSONResponse(status_code=403, content={"success": False, "error": "Only admins can update branding"})
        
    ws = await db.scalar(select(Workspace).where(Workspace.id == user.active_workspace_id))
    ws.brand_company_name = req.brand_company_name
    ws.brand_color = req.brand_color
    ws.brand_logo_url = req.brand_logo_url
    
    await db.commit()
    return {"success": True, "message": "Branding updated"}
