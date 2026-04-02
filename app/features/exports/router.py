from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.features.auth.models import User
from app.features.jobs.models import Job
from app.features.exports.service import DEFAULT_FILTERS, apply_fresh_only
from sqlalchemy import select
import uuid
import csv
import io
import hashlib
from app.features.suppression.models import SuppressedEmail

router = APIRouter()

@router.get("/{job_id}/download")
async def download_export(
    job_id: uuid.UUID,
    preset: str = None,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    job = await db.scalar(select(Job).where(Job.id == job_id, Job.user_id == user.id))
    if not job or job.status != "complete":
        raise HTTPException(status_code=404, detail="Job not found or not complete")
        
    file_path = job.output_file_path
    if not file_path:
        raise HTTPException(status_code=404, detail="File missing")
        
    if preset == "fresh":
        try:
            # Fetch user's suppression hashes
            stmt = select(SuppressedEmail.email_hash).where(SuppressedEmail.user_id == user.id)
            hash_res = await db.execute(stmt)
            suppressed = set(hash_res.scalars().all())

            results = []
            with open(file_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                headers = reader.fieldnames or []
                email_col = next((h for h in headers if 'email' in h.lower()), 'email')
                
                for row in reader:
                    raw_email = str(row.get(email_col) or '').strip().lower()
                    if raw_email:
                        ehash = hashlib.sha256(raw_email.encode('utf-8')).hexdigest()
                        if ehash in suppressed:
                            continue
                    
                    parsed = dict(row)
                    parsed["burn_score"] = int(row.get("burn_score") or 0)
                    parsed["bounce_score"] = int(row.get("bounce_score") or 0)
                    parsed["domain_age_days"] = int(row.get("domain_age_days") or 999)
                    parsed["mx_valid"] = str(row.get("mx_valid")).lower() == "true"
                    results.append(parsed)
                    
            kept_rows, _ = apply_fresh_only(results, DEFAULT_FILTERS)
            
            output = io.StringIO()
            writer = csv.DictWriter(output, fieldnames=headers)
            writer.writeheader()
            for r in kept_rows:
                writer.writerow({k: r[k] for k in headers})
                
            output.seek(0)
            return StreamingResponse(
                iter([output.getvalue()]),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=fresh_{job_id}.csv"}
            )
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    else:
        try:
            def iterfile():
                with open(file_path, mode="rb") as f:
                    yield from f
            return StreamingResponse(
                iterfile(),
                media_type="text/csv",
                headers={"Content-Disposition": f"attachment; filename=full_{job_id}.csv"}
            )
        except Exception:
            raise HTTPException(status_code=404, detail="Could not read output file")

@router.get("/{job_id}/autofix")
async def download_autofix(
    job_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    import os
    import tempfile
    import zipfile
    from fastapi.responses import FileResponse
    from app.features.exports.auto_fix import write_auto_fix_csvs
    
    job = await db.scalar(select(Job).where(Job.id == job_id, Job.user_id == user.id))
    if not job or job.status != "complete" or not job.output_file_path:
        raise HTTPException(status_code=404, detail="Job not found or not complete")
        
    try:
        # Fetch user's suppression hashes
        stmt = select(SuppressedEmail.email_hash).where(SuppressedEmail.user_id == user.id)
        hash_res = await db.execute(stmt)
        suppressed = set(hash_res.scalars().all())

        results = []
        with open(job.output_file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            headers = reader.fieldnames or []
            email_col = next((h for h in headers if 'email' in h.lower()), 'email')
            
            for row in reader:
                raw_email = str(row.get(email_col) or '').strip().lower()
                if raw_email:
                    ehash = hashlib.sha256(raw_email.encode('utf-8')).hexdigest()
                    if ehash in suppressed:
                        continue
                        
                parsed = dict(row)
                parsed["syntax_valid"] = str(row.get("syntax_valid", "false")).lower() == "true"
                parsed["bounce_score"] = int(float(row.get("bounce_score") or 0))
                parsed["spam_copy_flagged"] = str(row.get("spam_copy_flagged", "false")).lower() == "true"
                parsed["is_blacklisted"] = str(row.get("is_blacklisted", "false")).lower() == "true"
                results.append(parsed)
                
        # Create a temporary directory for the CSVs
        temp_dir = tempfile.mkdtemp()
        files = write_auto_fix_csvs(job.output_file_path, results, temp_dir)
        
        # Zip them up
        zip_path = os.path.join(temp_dir, f"autofix_{job_id}.zip")
        with zipfile.ZipFile(zip_path, 'w', zipfile.ZIP_DEFLATED) as zf:
            for name, path in files.items():
                zf.write(path, os.path.basename(path))
                
        return FileResponse(
            zip_path,
            media_type="application/zip",
            filename=f"listintel_autofix_{job_id}.zip"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
