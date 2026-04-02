import httpx
from typing import List, Dict, Any
from app.config import settings
from app.features.prospects.schemas import ICPFilters
import structlog
import asyncio

logger = structlog.get_logger()

async def search_apollo(filters: ICPFilters, limit: int = 100) -> List[Dict[str, Any]]:
    """
    Apollo People Search API.
    Returns contacts matching ICP filters.
    """
    if not settings.APOLLO_API_KEY:
        logger.warning("Apollo API key is empty. Sourcing will yield zero results.")
        # In a real setup without a key, you might fail or return an empty list
        return []

    # Map our ICPFilters to Apollo's payload
    payload = {
        "api_key": settings.APOLLO_API_KEY,
        "contact_email_status": ["verified", "extrapolated", "likely_to_engage"],
        "per_page": min(limit, 100),
        "page": 1,
    }

    if filters.company_industries:
        payload["q_organization_industries"] = filters.company_industries
    
    # company size range mapping
    if filters.company_size_min is not None or filters.company_size_max is not None:
        c_min = filters.company_size_min or 1
        c_max = filters.company_size_max or 1000000
        payload["q_organization_num_employees_ranges"] = [f"{c_min},{c_max}"]
        
    if filters.company_locations:
        payload["q_organization_locations"] = filters.company_locations
        
    if filters.contact_job_titles:
        payload["person_titles"] = filters.contact_job_titles
        
    if filters.contact_seniorities:
        payload["person_seniorities"] = filters.contact_seniorities
        
    if filters.contact_departments:
        payload["person_departments"] = filters.contact_departments

    url = "https://api.apollo.io/v1/mixed_people/search"
    
    results = []
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.post(url, json=payload, timeout=30.0)
            response.raise_for_status()
            data = response.json()
            
            raw_people = data.get("people", [])
            for p in raw_people:
                # Map Apollo's standard return format to our generic format
                org = p.get("organization") or {}
                
                results.append({
                    "apollo_id": p.get("id"),
                    "first_name": p.get("first_name"),
                    "last_name": p.get("last_name"),
                    "full_name": p.get("name"),
                    "title": p.get("title"),
                    "seniority": p.get("seniority"),
                    "email": p.get("email"),
                    "linkedin_url": p.get("linkedin_url"),
                    "company": org.get("name"),
                    "domain": org.get("primary_domain"),
                    "industry": org.get("industry"),
                    "company_size": org.get("estimated_num_employees"),
                    "location": p.get("city") or org.get("city"),
                    "email_confidence": 90 if p.get("email_status") == "verified" else 50
                })
                
        except Exception as e:
            logger.error("apollo_api_error", error=str(e))
            raise e
            
    return results
