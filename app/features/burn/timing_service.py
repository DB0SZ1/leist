"""
Campaign Timing Intelligence Service
Generates historical heatmap data for a given niche to determine the best times to send.
Since we don't have direct SMTP connection yet (Phase 5), this aggregates historical list 
processing and burn rates per day/hour to construct a 'Send Window' heatmap.
"""
from datetime import datetime, timezone
import random
from typing import Dict, List, Any

from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from app.features.jobs.models import Job

async def get_timing_heatmap_for_user(db: AsyncSession, user_id, niche: str, show_sample: bool = False) -> tuple[List[Dict[str, Any]], bool, bool]:
    """
    Returns a 7x24 grid representing the best times to send.
    If show_sample is True, generates deterministic data.
    Otherwise, aggregates real completed jobs. If no jobs, returns empty heatmap with all 0s.
    Returns (heatmap, is_sample, has_data)
    """
    days = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"]
    
    if show_sample:
        seed = sum(ord(c) for c in (niche or "default"))
        rng = random.Random(seed)
        heatmap = []
        for day_idx, day in enumerate(days):
            day_data = {"day": day, "hours": []}
            for hour in range(24):
                if day_idx < 5:
                    if 8 <= hour <= 17:
                        base_score = rng.randint(60, 95)
                    else:
                        base_score = rng.randint(20, 50)
                else:
                    base_score = rng.randint(10, 40)
                day_data["hours"].append({"hour": hour, "score": base_score})
            heatmap.append(day_data)
        return heatmap, True, True

    # Real data aggregation
    stmt = select(Job.completed_at).where(Job.user_id == user_id, Job.completed_at.is_not(None))
    result = await db.execute(stmt)
    jobs = result.scalars().all()
    
    if not jobs:
        heatmap = [{"day": day, "hours": [{"hour": h, "score": 0} for h in range(24)]} for day in days]
        return heatmap, False, False

    # Naive scoring based on when jobs completed.
    counts = {(d, h): 0 for d in range(7) for h in range(24)}
    max_c = int(0)
    for dt in jobs:
        counts[(dt.weekday(), dt.hour)] += 1
        curr_c = int(counts[(dt.weekday(), dt.hour)])
        if curr_c > max_c:
            max_c = curr_c
            
    heatmap = []
    for day_idx, day in enumerate(days):
        day_data = {"day": day, "hours": []}
        for hour in range(24):
            c = counts.get((day_idx, hour), 0)
            score = int((c * 100) / max_c) if max_c > 0 else 0
            day_data["hours"].append({"hour": hour, "score": score})
        heatmap.append(day_data)
        
    return heatmap, False, True

def get_optimal_windows(heatmap: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Extracts the top 3 optimal sending windows from the heatmap."""
    all_hours: List[Dict[str, Any]] = []
    for day in heatmap:
        for hour_data in day["hours"]:
            all_hours.append({
                "day": day["day"],
                "hour": hour_data["hour"],
                "score": hour_data["score"]
            })
            
    # Sort by score descending
    all_hours.sort(key=lambda x: x["score"], reverse=True)
    return all_hours[:3]
