from app.workers.celery_app import app
import asyncio
import uuid
from datetime import datetime, timezone
from app.core.database import async_session_maker
from app.features.prospects.models import ProspectJob, Prospect
from app.features.prospects.sources.apollo import search_apollo
from app.features.prospects.schemas import ICPFilters
from app.features.processing.pipeline import process_batch
from app.features.billing.service import deduct_credits
from app.features.burn.service import bulk_insert_pool, hash_email
import structlog

logger = structlog.get_logger()

@app.task(name="app.workers.tasks.process_prospect_job.process_prospect_job", bind=True)
def process_prospect_job(self, payload: dict):
    job_id = payload.get("job_id")
    user_id = payload.get("user_id")
    if not job_id or not user_id:
        return

    asyncio.run(run_prospect_job_async(job_id, user_id))


async def run_prospect_job_async(job_id_str: str, user_id_str: str):
    job_id = uuid.UUID(job_id_str)
    user_id = uuid.UUID(user_id_str)

    async with async_session_maker() as db:
        job = await db.get(ProspectJob, job_id)
        if not job or job.status != "queued":
            return

        job.status = "sourcing"
        await db.commit()

        try:
            filters = ICPFilters(**job.icp_filters)
            
            # 1. Source the leads from Apollo
            raw_results = await search_apollo(filters, limit=job.target_count)
            job.found_count = len(raw_results)
            
            if not raw_results:
                job.status = "complete"
                job.completed_at = datetime.now(timezone.utc)
                await db.commit()
                return

            job.status = "enriching"
            await db.commit()

            # 2. Enrich the leads (pass them through the 8 layers)
            enriched_results = await process_batch(raw_results, {})
            
            # 3. Store Results and Compute Score
            db_prospects = []
            successful_count = 0
            
            for r in enriched_results:
                # Calculate Prospect Score (simplified version of spec formula)
                burn = r.get("burn_score", 100)
                burn_quality = max(0, 40 - burn) / 40 * 20
                
                # Base score from email confidence
                base_score = int((r.get("email_confidence", 50) / 100.0) * 40)
                
                # Bonus for clean Infra/Safe Domain
                if r.get("spam_filter") is None:
                    base_score += 15
                if r.get("domain_risk") == "Safe":
                    base_score += 15
                if not r.get("syntax_valid") or not r.get("mx_valid"):
                    base_score = 0
                    
                final_score = int(min(100, max(0, base_score + burn_quality)))
                
                prospect_status = "enriched" if final_score > 30 else "filtered"
                if prospect_status == "enriched":
                    successful_count += 1
                
                db_prospects.append(Prospect(
                    job_id=job.id,
                    user_id=user_id,
                    email=r.get("email"),
                    first_name=r.get("first_name"),
                    last_name=r.get("last_name"),
                    full_name=r.get("full_name"),
                    company=r.get("company"),
                    title=r.get("title"),
                    industry=r.get("industry"),
                    linkedin_url=r.get("linkedin_url"),
                    domain=r.get("domain"),
                    apollo_id=r.get("apollo_id"),
                    source="apollo",
                    email_confidence=r.get("email_confidence"),
                    status=prospect_status,
                    prospect_score=final_score,
                    burn_score=r.get("burn_score"),
                    spam_filter=r.get("spam_filter"),
                    enrichment_data=r
                ))
            
            db.add_all(db_prospects)
            
            # 4. Burn Pool Contribution
            email_list = [r.get("email", "") for r in enriched_results if r.get("email")]
            await bulk_insert_pool(db, email_list, str(user_id), str(job_id))
            
            # 5. Deduce Credits
            # Assuming Prospecting credits are 1.5x of Job credits, we'll just deduct raw number for now.
            credits_to_deduct = successful_count
            await deduct_credits(db, user_id, credits_to_deduct)
            job.credits_used = credits_to_deduct

            job.status = "complete"
            job.enriched_count = successful_count
            job.completed_at = datetime.now(timezone.utc)
            await db.commit()

        except Exception as e:
            logger.error("prospect_job_failed", job_id=str(job_id), error=str(e))
            job.status = "failed"
            job.error_detail = str(e)
            await db.commit()
