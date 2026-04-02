"""
Bonus Layer — Domain Blacklist (Spamhaus DBL)
Not in LAYERS.md 8-layer spec but adds value.
Checks if email domain is on Spamhaus Domain Block List.
"""
from .base import BaseLayer, LayerResult
from app.core.redis import get_redis
import aiodns
from aiodns.error import DNSError
import json
import structlog

log = structlog.get_logger()


class DomainBlacklistLayer(BaseLayer):
    layer_id = "domain_blacklist"

    async def run(self, row: dict, context: dict) -> LayerResult:
        try:
            email = row.get("email", "").lower().strip()
            domain = email.split("@")[1] if "@" in email else ""
            if not domain:
                return LayerResult(
                    layer_id=self.layer_id, success=True,
                    is_blacklisted=False, blacklist_reason=None,
                )

            # Check cache
            redis = await get_redis()
            cache_key = f"blacklist:{domain}"
            cached = await redis.get(cache_key)
            if cached:
                data = json.loads(cached)
                return LayerResult(
                    layer_id=self.layer_id, success=True,
                    is_blacklisted=data.get("is_blacklisted", False),
                    blacklist_reason=data.get("blacklist_reason"),
                )

            is_blacklisted = False
            reason = None

            try:
                resolver = aiodns.DNSResolver()
                query_domain = f"{domain}.dbl.spamhaus.org"
                result = await resolver.query(query_domain, "A")
                if result:
                    is_blacklisted = True
                    code = result[0].host
                    reason_map = {
                        "127.0.1.2": "Spam domain",
                        "127.0.1.4": "Phishing domain",
                        "127.0.1.5": "Malware domain",
                        "127.0.1.6": "Botnet C&C domain",
                    }
                    reason = reason_map.get(code, "Listed in Spamhaus DBL")
                    if code.startswith("127.0.1.10"):
                        reason = "Abused legitimate domain"
            except DNSError:
                pass  # NXDOMAIN = not listed (good)
            except Exception as e:
                log.warning("domain_blacklist.error", domain=domain, error=str(e)[:200])

            data = {"is_blacklisted": is_blacklisted, "blacklist_reason": reason}
            await redis.setex(cache_key, 86400, json.dumps(data))

            return LayerResult(
                layer_id=self.layer_id, success=True,
                is_blacklisted=is_blacklisted,
                blacklist_reason=reason,
            )
        except Exception as e:
            log.error("layer.domain_blacklist.failed", error=str(e)[:200])
            return LayerResult(
                layer_id=self.layer_id, success=False,
                error=str(e)[:200],
            )
