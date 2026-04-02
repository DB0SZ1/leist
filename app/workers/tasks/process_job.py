from app.workers.celery_app import app
import asyncio
from app.core.database import async_session_maker
from app.features.jobs.models import Job, JobResult
from app.features.processing.pipeline import process_batch
from app.features.processing.csv_reader import parse_csv
from app.features.processing.csv_writer import write_enriched_csv
from app.features.billing.service import deduct_credits
from app.features.burn.service import bulk_insert_pool, hash_email
from datetime import datetime, timezone
import uuid
import os


@app.task(name="app.workers.tasks.process_job.process_job", bind=True)
def process_job(self, payload: dict):
    job_id = payload.get("job_id")
    user_id = payload.get("user_id")
    if not job_id or not user_id:
        return

    asyncio.run(run_job_async(job_id, user_id))


async def run_job_async(job_id_str: str, user_id_str: str):
    job_id = uuid.UUID(job_id_str)
    user_id = uuid.UUID(user_id_str)

    async with async_session_maker() as db:
        job = await db.get(Job, job_id)
        if not job or job.status != "queued":
            return

        job.status = "processing"
        await db.commit()

        try:
            # Parse CSV → list[dict] with all original columns + normalised "email"
            rows = parse_csv(job.input_file_path)

            # Process batch through the 8+1 layer pipeline
            results = await process_batch(rows, {})
            job.processed_emails = len(results)

            # Store per-email results in DB
            db_results = []
            fresh, burned, mimecast = 0, 0, 0
            total_burn = 0

            for idx, r in enumerate(results):
                db_results.append(JobResult(
                    job_id=job.id,
                    row_index=idx,
                    email_hash=hash_email(r.get("email", "")),
                    original_email=r.get("email"),
                    syntax_valid=r.get("syntax_valid"),
                    syntax_tag=r.get("syntax_tag"),
                    mx_valid=r.get("mx_valid"),
                    spam_filter=r.get("spam_filter"),
                    email_infra=r.get("email_infra"),
                    domain_age_days=r.get("domain_age_days"),
                    domain_risk=r.get("domain_risk"),
                    is_catchall=r.get("is_catchall"),
                    catchall_confidence=r.get("catchall_confidence"),
                    burn_score=r.get("burn_score"),
                    burn_tag=r.get("burn_tag"),
                    burn_times_seen=r.get("burn_times_seen"),
                    bounce_score=r.get("bounce_score"),
                    bounce_type=r.get("bounce_type"),
                    spam_copy_score=r.get("spam_copy_score"),
                    spam_copy_flagged=r.get("spam_copy_flagged"),
                    spam_copy_reason=r.get("spam_copy_reason"),
                    is_blacklisted=r.get("is_blacklisted"),
                    blacklist_reason=r.get("blacklist_reason"),
                ))

                if r.get("burn_tag") == "Fresh":
                    fresh += 1
                if r.get("burn_tag") in ("Burned", "Torched"):
                    burned += 1
                if r.get("spam_filter") == "Mimecast":
                    mimecast += 1
                total_burn += r.get("burn_score", 0)

            db.add_all(db_results)

            # Contribute emails to burn pool (the network effect)
            email_list = [r.get("email", "") for r in results if r.get("email")]
            await bulk_insert_pool(db, email_list, str(user_id), str(job_id))

            # Deduct credits
            await deduct_credits(db, user_id, job.processed_emails)
            job.credits_charged = job.processed_emails

            job.status = "enriching"
            await db.commit()

            # Write enriched CSV
            output_path = job.input_file_path.replace(".csv", "_enriched.csv")
            write_enriched_csv(job.input_file_path, output_path, results)

            # Compute summary stats
            total = len(results) or 1
            avg_burn = round(total_burn / total, 1)
            spam_filter_count = sum(1 for r in results if r.get("spam_filter"))
            catchall_count = sum(1 for r in results if r.get("is_catchall"))
            invalid_count = sum(1 for r in results if not r.get("syntax_valid"))
            blacklisted_count = sum(1 for r in results if r.get("is_blacklisted"))

            # Infra distribution
            infra_dist = {}
            for r in results:
                infra = r.get("email_infra", "Unknown")
                infra_dist[infra] = infra_dist.get(infra, 0) + 1

            # Spam filter distribution
            filter_dist = {}
            for r in results:
                sf = r.get("spam_filter")
                if sf:
                    filter_dist[sf] = filter_dist.get(sf, 0) + 1

            job.output_file_path = output_path
            job.status = "complete"
            job.summary = {
                "total": len(results),
                "fresh": fresh,
                "burned": burned,
                "mimecast": mimecast,
                "avg_burn": avg_burn,
                "spam_filter_count": spam_filter_count,
                "catchall_count": catchall_count,
                "invalid_count": invalid_count,
                "blacklisted_count": blacklisted_count,
                "infra_distribution": infra_dist,
                "filter_distribution": filter_dist,
            }
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()

            # Fire Webhook if configured
            from app.features.integrations.service import get_user_webhook, trigger_webhook_payload
            from app.features.jobs.readiness import compute_readiness
            
            webhook = await get_user_webhook(db, job.user_id)
            if webhook and webhook.is_active and webhook.url:
                readiness = compute_readiness(job.summary)
                payload = {
                    "job_id": str(job.id),
                    "status": job.status,
                    "total_emails": job.total_emails,
                    "readiness_score": readiness["score"],
                    "fresh_count": job.summary.get("fresh", 0),
                    "download_url": f"https://listintel.io/api/v1/exports/{job.id}/download"
                }
                await trigger_webhook_payload(webhook.url, payload)

        except Exception as e:
            job.status = "failed"
            job.error_message = str(e)
            await db.commit()
            raise
