from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.features.auth.models import User
from app.features.jobs.models import Job
from app.features.workspaces.models import Workspace
from app.features.reports.service import generate_client_report
import uuid

router = APIRouter()

@router.get("/{job_id}/report")
async def download_client_report(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    if user.plan_id not in ["agency", "growth"]:
        raise HTTPException(status_code=403, detail="Client reporting requires Growth or Agency plan")
        
    # Check job ownership
    job = await db.scalar(select(Job).where(Job.id == job_id, Job.user_id == user.id))
    if not job or job.status != "complete":
        raise HTTPException(status_code=404, detail="Completed job not found")
        
    # Get active workspace for branding
    workspace = None
    if user.active_workspace_id:
        workspace = await db.scalar(select(Workspace).where(Workspace.id == user.active_workspace_id))
        
    pdf_bytes = generate_client_report(job, workspace)
    
    filename = f"Audit_Report_{job.input_file_path.split('_', 1)[-1] if '_' in job.input_file_path else 'List'}.pdf"
    
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'}
    )
