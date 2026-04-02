"""
Layer 6 — Domain Age & Risk Analysis
Redis-first WHOIS lookup to determine domain registration age.
Bulk pre-computation: deduplicates by domain, checks Redis cache first.
"""
import asyncio
import json
from datetime import datetime, timedelta
from typing import Any
from .base import BaseLayer, LayerResult
import structlog

log = structlog.get_logger()


def classify_risk(age_days: int | None) -> str:
    if age_days is None:
        return "Unknown"
    if age_days >= 365:
        return "Safe"
    if age_days >= 180:
        return "Medium"
    if age_days >= 60:
        return "High"
    return "VeryHigh"  # under 60 days — extreme caution


class DomainAgeLayer(BaseLayer):
    layer_id = "domain_age"

    async def bulk_lookup(self, keys: list[str], **kwargs) -> dict[str, dict]:
        """
        keys: list of unique domain strings
        kwargs may include: redis (aioredis.Redis instance)
        Returns: {domain: {"age_days": int|None, "risk": str}}
        """
        redis = kwargs.get("redis")
        if not redis:
            from app.core.redis import get_redis
            redis = await get_redis()

        result = {}
        uncached = []

        # 1. Check Redis for all domains at once
        if keys:
            cache_keys = [f"whois:{d}" for d in keys]
            cached_values = await redis.mget(*cache_keys)

            for domain, cached in zip(keys, cached_values):
                if cached is not None:
                    cached_str = cached.decode() if isinstance(cached, bytes) else cached
                    if cached_str == "unknown":
                        result[domain] = {"age_days": None, "risk": "Unknown"}
                    else:
                        try:
                            age_days = int(cached_str)
                            result[domain] = {
                                "age_days": age_days,
                                "risk": classify_risk(age_days),
                            }
                        except ValueError:
                            uncached.append(domain)
                else:
                    uncached.append(domain)

        # 2. Live WHOIS only for uncached domains
        if uncached:
            tasks = [self._whois_lookup(d) for d in uncached]
            whois_results = await asyncio.gather(*tasks, return_exceptions=True)

            for domain, whois_result in zip(uncached, whois_results):
                if isinstance(whois_result, Exception):
                    # Cache failure briefly (7 days)
                    try:
                        await redis.setex(f"whois:{domain}", 86400 * 7, "unknown")
                    except Exception:
                        pass
                    result[domain] = {"age_days": None, "risk": "Unknown"}
                else:
                    age_days = whois_result.get("age_days")
                    try:
                        await redis.setex(
                            f"whois:{domain}",
                            86400 * 30,  # 30-day TTL
                            str(age_days) if age_days is not None else "unknown",
                        )
                    except Exception:
                        pass
                    result[domain] = whois_result

        return result

    async def run(self, row: dict, context: dict) -> LayerResult:
        try:
            email = row.get("email", "").lower().strip()
            domain = email.split("@")[1] if "@" in email else ""

            # Extract base domain from subdomain (mail.company.com → company.com)
            parts = domain.split(".")
            if len(parts) > 2:
                domain = ".".join(parts[-2:])

            domain_ages = context.get("domain_ages", {})
            data = domain_ages.get(domain, {"age_days": None, "risk": "Unknown"})

            return LayerResult(
                layer_id=self.layer_id,
                success=True,
                domain_age_days=data["age_days"],
                domain_risk=data["risk"],
            )
        except Exception as e:
            log.error("layer.domain_age.failed", error=str(e)[:200])
            return LayerResult(
                layer_id=self.layer_id, success=False,
                error=str(e)[:200],
            )

    async def _whois_lookup(self, domain: str) -> dict:
        """Run python-whois in a thread pool (it's a sync library)."""
        try:
            import whois
            info = await asyncio.to_thread(whois.whois, domain)
            creation_date = self._parse_creation_date(info)
            if not creation_date:
                return {"age_days": None, "risk": "Unknown"}
            age_days = (datetime.now() - creation_date.replace(tzinfo=None)).days
            age_days = max(0, age_days)
            return {"age_days": age_days, "risk": classify_risk(age_days)}
        except Exception:
            return {"age_days": None, "risk": "Unknown"}

    def _parse_creation_date(self, info) -> datetime | None:
        """
        python-whois returns creation_date as datetime, list[datetime], or None.
        Different registrars return different formats — handle all.
        """
        cd = info.creation_date
        if not cd:
            return None
        if isinstance(cd, list):
            valid_dates = [d for d in cd if isinstance(d, datetime)]
            return min(valid_dates) if valid_dates else None
        if isinstance(cd, datetime):
            return cd
        return None
