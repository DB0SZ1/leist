"""
Campaign Simulator Service
Predicts inbox vs spam vs blocked placement based on sender health, recipient list quality, and copy analysis.
"""
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.features.jobs.models import Job
from app.features.domains.models import TrackedDomain
from app.features.copilot.service import analyze_email_content
import structlog

log = structlog.get_logger()

async def simulate_campaign(
    db: AsyncSession,
    user_id: str,
    domain: str,
    job_id: str,
    subject: str,
    body: str,
    volume_per_day: int
) -> dict:
    
    domain = domain.strip().lower()
    
    # 1. Evaluate Sender Domain (40% weight)
    sender_score_base = 100
    spf_valid = True
    dkim_found = True
    dmarc_policy = "none"
    rbl_hits = 0
    
    # Try to find a recent domain check
    chk = await db.scalar(
        select(TrackedDomain)
        .where(TrackedDomain.domain_name == domain)
    )
    if chk:
        if chk.status == "Healthy":
            sender_score_base = 98
            rbl_hits = 0
        elif chk.status == "At Risk":
            sender_score_base = 75
            rbl_hits = 1
        elif chk.status == "Blacklisted":
            sender_score_base = 50
            rbl_hits = 3
        else:
            sender_score_base = 80
            rbl_hits = 0
            
        spf_valid = True
        dkim_found = True
        dmarc_policy = "reject" if chk.status == "Healthy" else "none"
    else:
        raise ValueError("Domain has not been scanned yet. Please run a Health Check on this domain before simulating.")
        
    sender_impact = (sender_score_base / 100.0)
    
    # 2. Evaluate Recipient List Quality (40% weight)
    recipient_impact = 1.0
    if job_id:
        job = await db.scalar(select(Job).where(Job.id == job_id, Job.user_id == user_id))
        if job and job.summary:
            s = job.summary
            total = job.total_emails or 1
            fresh = s.get('fresh', 0)
            burned = s.get('burned', 0)
            catchall = s.get('catchall', 0)
            
            # Simple heuristic: 100% fresh = 1.0, burned = 0.1
            fresh_pct = fresh / total
            burned_pct = burned / total
            
            recipient_impact = max(0.2, (fresh_pct * 1.0) + ((1 - fresh_pct - burned_pct) * 0.6) - (burned_pct * 0.8))
        else:
            recipient_impact = 0.5 # Unknown list quality
    
    # 3. Evaluate Content Quality (20% weight)
    copy_analysis = await analyze_email_content(subject, body)
    spam_score = copy_analysis.get('spam_score', 0) # 0 is best, 100 is worst
    agg_score = copy_analysis.get('aggressiveness_score', 0)
    
    content_impact = 1.0 - ((spam_score * 0.7 + agg_score * 0.3) / 100.0)
    content_impact = max(0.1, content_impact)
    
    # Global Penalty: High volume per day without warmup lowers the score drastically
    volume_penalty = 1.0
    if volume_per_day > 100 and sender_score_base < 90:
        volume_penalty = 0.8
    if volume_per_day > 500 and sender_score_base < 90:
        volume_penalty = 0.5
        
    # Calculate Final Placements
    # Target distribution based on impacts
    inbox_prob = sender_impact * 0.45 + recipient_impact * 0.35 + content_impact * 0.20
    inbox_prob *= volume_penalty
    
    # Base blocking from RBLs / hard bounces
    block_prob = 0.05 + (0.1 if rbl_hits > 0 else 0) + (0.1 if not spf_valid else 0)
    if recipient_impact < 0.4: block_prob += 0.15
    
    inbox_pct = int(min(0.98, max(0.01, inbox_prob)) * 100)
    block_pct = int(min(0.99 - (inbox_pct/100), max(0.01, block_prob)) * 100)
    spam_pct = 100 - inbox_pct - block_pct
    
    # Safety clamp
    if spam_pct < 0: spam_pct = 0
    if inbox_pct + spam_pct + block_pct != 100:
        spam_pct = 100 - inbox_pct - block_pct
        
    recommendations = []
    if not spf_valid or not dkim_found:
        recommendations.append("Authenticate your domain! Missing SPF/DKIM is drastically increasing block rates.")
    if rbl_hits > 0:
        recommendations.append("Your domain is on a blacklist. Delist it before sending.")
    if recipient_impact < 0.5:
        recommendations.append("Your list quality is poor. Use the Auto-Fix tool to remove burned emails before sending.")
    if spam_score > 40:
        recommendations.append(f"Your email copy contains spam triggers (Spam Score: {spam_score}/100). Rewrite it using the Copilot.")
    if volume_penalty < 1.0:
        recommendations.append("You are sending too much volume for your domain's reputation. Reduce daily sends.")
        
    if not recommendations:
        recommendations.append("Campaign looks solid! Just monitor early bounce rates.")

    return {
        "inbox_pct": inbox_pct,
        "spam_pct": spam_pct,
        "block_pct": block_pct,
        "sender_impact": int(sender_impact * 100),
        "recipient_impact": int(recipient_impact * 100),
        "content_impact": int(content_impact * 100),
        "recommendations": recommendations,
        "copy_feedback": copy_analysis.get('feedback', '')
    }
