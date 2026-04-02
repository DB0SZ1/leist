import csv
import hashlib
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.features.jobs.models import Job
from app.features.jobs.diff_models import JobDiff
import uuid


def _extract_emails_from_csv(file_path: str) -> set[str]:
    """Extract lowercased email hashes from a CSV file."""
    emails = set()
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            header = next(reader, None)
            if not header:
                return emails
            email_col = next((i for i, h in enumerate(header) if 'email' in h.lower()), 0)
            for row in reader:
                if len(row) > email_col:
                    email = row[email_col].strip().lower()
                    if email:
                        emails.add(email)
    except Exception:
        pass
    return emails


def _extract_summary_from_csv(file_path: str) -> dict:
    """Extract basic stats from a CSV output."""
    stats = {"total": 0, "burned": 0, "fresh": 0}
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                stats["total"] += 1
                score = int(row.get("burn_score") or 0)
                if score > 50:
                    stats["burned"] += 1
                elif score <= 20:
                    stats["fresh"] += 1
    except Exception:
        pass
    return stats


async def compute_diff(db: AsyncSession, user_id: uuid.UUID, job_a_id: uuid.UUID, job_b_id: uuid.UUID) -> dict:
    """
    Compare two jobs by extracting emails from their output CSVs.
    Returns the diff summary.
    """
    job_a = await db.scalar(select(Job).where(Job.id == job_a_id, Job.user_id == user_id))
    job_b = await db.scalar(select(Job).where(Job.id == job_b_id, Job.user_id == user_id))

    if not job_a or not job_b:
        return {"error": "One or both jobs not found"}

    if job_a.status != "complete" or job_b.status != "complete":
        return {"error": "Both jobs must be complete"}

    file_a = job_a.output_file_path or job_a.input_file_path
    file_b = job_b.output_file_path or job_b.input_file_path

    emails_a = _extract_emails_from_csv(file_a)
    emails_b = _extract_emails_from_csv(file_b)

    added = emails_b - emails_a
    removed = emails_a - emails_b
    unchanged = emails_a & emails_b

    # Get summary stats if output files have burn_score columns
    stats_a = _extract_summary_from_csv(file_a)
    stats_b = _extract_summary_from_csv(file_b)

    summary = {
        "added": len(added),
        "removed": len(removed),
        "unchanged": len(unchanged),
        "job_a_total": stats_a["total"],
        "job_b_total": stats_b["total"],
        "job_a_burned": stats_a["burned"],
        "job_b_burned": stats_b["burned"],
        "job_a_fresh": stats_a["fresh"],
        "job_b_fresh": stats_b["fresh"],
        "burn_delta": stats_b["burned"] - stats_a["burned"],
        "fresh_delta": stats_b["fresh"] - stats_a["fresh"],
    }

    # Persist the diff
    diff = JobDiff(
        user_id=user_id,
        job_a_id=job_a_id,
        job_b_id=job_b_id,
        summary=summary
    )
    db.add(diff)
    await db.commit()
    await db.refresh(diff)

    return {
        "id": str(diff.id),
        **summary,
        "job_a_file": job_a.input_file_path,
        "job_b_file": job_b.input_file_path,
    }
