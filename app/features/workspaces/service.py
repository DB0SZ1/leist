from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.features.workspaces.models import Workspace
from app.features.auth.models import User

async def get_active_workspace_id(user: User, db: AsyncSession) -> str:
    """
    Retrieves the currently active workspace ID for the user.
    Falls back to finding a workspace they own if active_workspace_id is not set.
    """
    if getattr(user, "active_workspace_id", None):
        return str(user.active_workspace_id)
        
    stmt = select(Workspace).where(Workspace.owner_id == user.id)
    ws = await db.scalar(stmt)
    if ws:
        return str(ws.id)
        
    return str(user.id)
