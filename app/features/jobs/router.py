from fastapi import APIRouter, Depends, Request, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import get_db
from app.core.dependencies import get_current_user
from app.core.responses import ok, fail
from app.features.auth.models import User
from app.features.jobs import service
from app.config import settings
import os
import aiofiles
import csv
import uuid
from app.features.audit.service import log_event
import asyncio
import hashlib
from app.features.jobs.diff_models import JobDiff

router = APIRouter()
page_router = APIRouter()
templates = Jinja2Templates(directory="app/templates")

@router.post("")
async def create_job(
    request: Request,
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    try:
        if not file.filename.endswith(".csv"):
            return JSONResponse(status_code=400, content=fail("Only CSV files are supported").model_dump())
            
        uploads = getattr(settings, "UPLOAD_DIR", "/tmp/uploads")
        os.makedirs(uploads, exist_ok=True)
        file_path = os.path.join(uploads, f"{uuid.uuid4()}_{file.filename}")
        
        async with aiofiles.open(file_path, 'wb') as out_file:
            content = await file.read()
            await out_file.write(content)
            
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if not header:
                return JSONResponse(status_code=400, content=fail("CSV is empty").model_dump())
            
            email_col = next((i for i, h in enumerate(header) if 'email' in h.lower()), 0)
            row_count = sum(1 for _ in reader)
            
        job = await service.create_job(db, user, file_path, row_count)
        
        await log_event(
            db=db,
            user_id=user.id,
            workspace_id=user.active_workspace_id,
            event_type="job.created",
            resource_type="job",
            resource_id=str(job.id),
            metadata_json={"filename": file.filename, "rows": row_count},
            ip_address=request.client.host if request.client else None
        )
        await db.commit()
        
        # Trigger Celery Task safely
        try:
            from app.workers.tasks.process_job import process_job
            from app.core.msgpack import encode
            process_job.apply_async(args=[encode({"job_id": str(job.id), "user_id": str(user.id)})])
        except ImportError:
            # We haven't created process_job.py yet, but we will in the next step
            print("Warning: Celery worker not available yet.")

        return ok({"id": job.id, "status": job.status, "total_emails": job.total_emails, "email_column": header[email_col] if email_col < len(header) else "Unknown"})
    except Exception as e:
        return JSONResponse(status_code=400, content=fail(str(e)).model_dump())

def _merge_csvs_sync(file_paths: list[dict], output_path: str):
    """
    Synchronous helper to merge CSVs.
    file_paths: list of dicts: {"path": "/tmp/...", "name": "a.csv"}
    """
    seen_emails = {}
    overlap_matrix = { f["name"]: { f2["name"]: 0 for f2 in file_paths } for f in file_paths }
    
    # First pass: gather emails and compute overlap
    for idx, fObj in enumerate(file_paths):
        with open(fObj["path"], 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if not header: continue
            email_col = next((i for i, h in enumerate(header) if 'email' in h.lower()), 0)
            
            for row in reader:
                if len(row) <= email_col: continue
                email = row[email_col].strip().lower()
                if not email: continue
                
                # Check overlaps
                if email in seen_emails:
                    for prev_source in seen_emails[email]["sources"]:
                        if prev_source != fObj["name"]:
                            overlap_matrix[prev_source][fObj["name"]] += 1
                            overlap_matrix[fObj["name"]][prev_source] += 1
                    seen_emails[email]["sources"].add(fObj["name"])
                else:
                    seen_emails[email] = {"sources": {fObj["name"]}, "first_row": row, "first_header": header}

    # Write merged
    final_count = 0
    with open(output_path, 'w', encoding='utf-8', newline='') as out_f:
        writer = csv.writer(out_f)
        # We need a unified header. Let's just use the largest header found, plus our custom columns
        best_header = []
        for v in seen_emails.values():
            if len(v["first_header"]) > len(best_header):
                best_header = v["first_header"]
                
        writer.writerow(list(best_header) + ["source_file", "appeared_in_n_lists", "is_duplicate"])
        
        for email, data in seen_emails.items():
            row = list(data["first_row"])
            # Pad row if smaller than best_header
            while len(row) < len(best_header):
                row.append("")
            
            sources = list(data["sources"])
            row.append(sources[0]) # primary source file
            row.append(str(len(sources)))
            row.append("True" if len(sources) > 1 else "False")
            writer.writerow(row)
            final_count += 1
            
    return final_count, overlap_matrix


@router.post("/merge")
async def merge_jobs(
    files: list[UploadFile] = File(...),
    enrich: bool = Form(False),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    try:
        if len(files) < 2 or len(files) > 10:
            return JSONResponse(status_code=400, content=fail("Please upload between 2 and 10 CSV files.").model_dump())
            
        uploads = getattr(settings, "UPLOAD_DIR", "/tmp/uploads")
        os.makedirs(uploads, exist_ok=True)
        
        saved_files = []
        for file in files:
            if not file.filename.endswith(".csv"):
                continue
            path = os.path.join(uploads, f"{uuid.uuid4()}_{file.filename}")
            async with aiofiles.open(path, 'wb') as out_file:
                content = await file.read()
                await out_file.write(content)
            saved_files.append({"path": path, "name": file.filename})

        if len(saved_files) < 2:
            return JSONResponse(status_code=400, content=fail("Failed to read valid CSV files.").model_dump())

        merged_file_path = os.path.join(uploads, f"merged_{uuid.uuid4()}.csv")
        
        # Merge in background thread
        final_count, overlap_matrix = await asyncio.to_thread(_merge_csvs_sync, saved_files, merged_file_path)
        
        job = await service.create_job(db, user, merged_file_path, final_count)
        job.summary = {"merge_stats": overlap_matrix}
        
        if enrich:
            try:
                from app.workers.tasks.process_job import process_job
                from app.core.msgpack import encode
                process_job.apply_async(args=[encode({"job_id": str(job.id), "user_id": str(user.id)})])
            except ImportError:
                print("Warning: Celery worker not available yet.")
        else:
            job.status = "complete"
            job.output_file_path = merged_file_path
            await db.commit()

        return ok({
            "id": job.id, 
            "status": job.status, 
            "total_emails": final_count,
            "overlap_matrix": overlap_matrix
        })
    except Exception as e:
        return JSONResponse(status_code=400, content=fail(str(e)).model_dump())

@router.get("/{id}")
async def get_job_status(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    job = await service.get_job(db, id, user.id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    return ok({
        "id": job.id,
        "status": job.status,
        "total_emails": job.total_emails,
        "processed_emails": job.processed_emails,
        "summary": job.summary,
        "error_message": job.error_message
    })

@router.get("/{id}/aging")
async def get_job_aging(
    id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    from app.features.jobs.aging_service import get_aging_history
    history = await get_aging_history(db, id, user.id)
    return ok([
        {
            "day": h.day_number,
            "fresh_count": h.fresh_count,
            "warm_count": h.warm_count,
            "burned_count": h.burned_count,
            "torched_count": h.torched_count,
            "freshness_pct": h.freshness_pct,
            "avg_burn_score": h.avg_burn_score,
            "captured_at": h.captured_at
        } for h in history
    ])

@router.post("/diff")
async def diff_jobs(
    job_a_id: uuid.UUID = Form(...),
    job_b_id: uuid.UUID = Form(...),
    db: AsyncSession = Depends(get_db),
    user: User = Depends(get_current_user)
):
    from app.features.jobs.diff_service import compute_diff
    try:
        result = await compute_diff(db, user.id, job_a_id, job_b_id)
        if "error" in result:
            return JSONResponse(status_code=400, content=fail(result["error"]).model_dump())
        return ok(result)
    except Exception as e:
        return JSONResponse(status_code=400, content=fail(str(e)).model_dump())

@page_router.get("/dashboard", response_class=HTMLResponse)
async def dashboard_page(request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    if not user.onboarding_completed and request.cookies.get("onboarding_skipped") != "1":
        from fastapi.responses import RedirectResponse
        return RedirectResponse(url="/onboarding")
    jobs = await service.get_jobs_by_user(db, user.id, limit=5)
    return templates.TemplateResponse("dashboard/index.html", {
        "request": request,
        "user": user,
        "recent_jobs": jobs
    })

@page_router.get("/jobs", response_class=HTMLResponse)
async def jobs_page(request: Request, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    jobs = await service.get_jobs_by_user(db, user.id, limit=50)
    return templates.TemplateResponse("dashboard/job_list.html", {
        "request": request,
        "user": user,
        "jobs": jobs
    })

@page_router.get("/jobs/compare", response_class=HTMLResponse)
async def job_compare_page(request: Request, a: str = None, b: str = None, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    all_jobs = await service.get_jobs_by_user(db, user.id, limit=50)
    completed_jobs = [j for j in all_jobs if j.status == "complete"]
    diff_result = None

    if a and b:
        from app.features.jobs.diff_service import compute_diff
        try:
            diff_result = await compute_diff(db, user.id, uuid.UUID(a), uuid.UUID(b))
        except Exception:
            diff_result = {"error": "Could not compute diff"}

    return templates.TemplateResponse("dashboard/job_compare.html", {
        "request": request,
        "user": user,
        "jobs": completed_jobs,
        "diff": diff_result,
        "selected_a": a,
        "selected_b": b
    })

@page_router.get("/jobs/{id}", response_class=HTMLResponse)
async def job_detail_page(request: Request, id: uuid.UUID, db: AsyncSession = Depends(get_db), user: User = Depends(get_current_user)):
    job = await service.get_job(db, id, user.id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
        
    readiness = None
    if job.status == "complete" and job.summary:
        from app.features.jobs.readiness import compute_readiness
        readiness = compute_readiness(job.summary, job.total_emails)
        
    niche_benchmark = None
    if user.niche:
        from app.features.burn.benchmark_service import get_latest_benchmark_for_niche
        niche_benchmark = await get_latest_benchmark_for_niche(db, user.niche)
        
    return templates.TemplateResponse("dashboard/job_detail.html", {
        "request": request,
        "user": user,
        "job": job,
        "readiness": readiness,
        "niche_benchmark": niche_benchmark
    })

@page_router.get("/timing", response_class=HTMLResponse)
async def campaign_timing_page(
    request: Request, 
    show_sample: bool = False,
    db: AsyncSession = Depends(get_db), 
    user: User = Depends(get_current_user)
):
    from app.features.burn.timing_service import get_timing_heatmap_for_user, get_optimal_windows
    
    niche = user.niche or "Default"
    heatmap, is_sample, has_data = await get_timing_heatmap_for_user(db, user.id, niche, show_sample=show_sample)
    optimal_windows = get_optimal_windows(heatmap)
    
    return templates.TemplateResponse("dashboard/timing.html", {
        "request": request,
        "user": user,
        "heatmap": heatmap,
        "optimal": optimal_windows,
        "is_sample": is_sample,
        "has_data": has_data
    })
