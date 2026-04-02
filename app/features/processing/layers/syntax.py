"""
Layer 1 — Syntax & MX Validation
Runs first. Produces mx_records for Layers 2 and 3.
Catches: invalid syntax, role addresses, disposable domains, dead MX.
"""
import re
import asyncio
from pathlib import Path
from .base import BaseLayer, LayerResult
import aiodns
import structlog

log = structlog.get_logger()

# RFC 5322 simplified — covers 99.9% of real email addresses
EMAIL_REGEX = re.compile(
    r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
)

ROLE_PREFIXES = frozenset([
    # Primary roles
    "info", "admin", "noreply", "no-reply", "contact", "support",
    "help", "hello", "team", "sales", "billing", "accounts",
    # Marketing roles
    "marketing", "newsletter", "notifications", "alerts", "campaigns",
    "digest", "updates", "news", "promo", "deals",
    # Technical roles
    "webmaster", "postmaster", "abuse", "spam", "security",
    "bounce", "mailer-daemon", "mailerdaemon", "donotreply", "do-not-reply",
    # Service roles
    "careers", "jobs", "press", "media", "legal", "privacy",
    "feedback", "enquiries", "enquiry", "service",
])

# Load disposable domains once at module level
_DISPOSABLE_DOMAINS: frozenset[str] | None = None

def _load_disposable_domains() -> frozenset[str]:
    global _DISPOSABLE_DOMAINS
    if _DISPOSABLE_DOMAINS is not None:
        return _DISPOSABLE_DOMAINS

    sig_path = Path(__file__).parent.parent / "signatures" / "disposable_domains.txt"
    if sig_path.exists():
        with open(sig_path) as f:
            _DISPOSABLE_DOMAINS = frozenset(
                line.strip().lower() for line in f if line.strip()
            )
    else:
        _DISPOSABLE_DOMAINS = frozenset()
        log.warning("signatures.disposable_domains_missing", path=str(sig_path))
    return _DISPOSABLE_DOMAINS


def is_role_address(local_part: str) -> bool:
    local = local_part.lower().strip()
    if local in ROLE_PREFIXES:
        return True
    for prefix in ROLE_PREFIXES:
        if local.startswith(prefix + "-") or local.startswith(prefix + "_"):
            return True
    return False


def is_disposable(domain: str) -> bool:
    return domain.lower() in _load_disposable_domains()


class SyntaxLayer(BaseLayer):
    layer_id = "syntax"

    async def run(self, row: dict, context: dict) -> LayerResult:
        try:
            email = row.get("email", "").lower().strip()
            if not email or "@" not in email:
                return LayerResult(
                    layer_id=self.layer_id, success=True,
                    syntax_valid=False, syntax_tag="invalid",
                    mx_valid=False, mx_records=[],
                )

            local, domain = email.rsplit("@", 1)

            # ── Syntax check ──
            if not EMAIL_REGEX.match(email):
                return LayerResult(
                    layer_id=self.layer_id, success=True,
                    syntax_valid=False, syntax_tag="invalid",
                    mx_valid=False, mx_records=[],
                )

            # ── Disposable domain check ──
            if is_disposable(domain):
                # Still check MX for completeness
                mx_valid, mx_records = await self._check_mx(domain)
                return LayerResult(
                    layer_id=self.layer_id, success=True,
                    syntax_valid=True, syntax_tag="disposable",
                    mx_valid=mx_valid, mx_records=mx_records,
                )

            # ── Role address check ──
            tag = "role" if is_role_address(local) else "valid"

            # ── MX record verification ──
            mx_valid, mx_records = await self._check_mx(domain)

            return LayerResult(
                layer_id=self.layer_id, success=True,
                syntax_valid=True, syntax_tag=tag,
                mx_valid=mx_valid, mx_records=mx_records,
            )

        except Exception as e:
            log.error("layer.syntax.failed", error=str(e)[:200])
            return LayerResult(
                layer_id=self.layer_id, success=False,
                error=str(e)[:200],
            )

    async def _check_mx(self, domain: str) -> tuple[bool, list[str]]:
        """Check MX records using Google + Cloudflare DNS."""
        try:
            resolver = aiodns.DNSResolver(
                nameservers=["8.8.8.8", "8.8.4.4", "1.1.1.1"],
                timeout=3.0,
                tries=2,
            )
            records = await resolver.query(domain, "MX")
            if not records:
                return False, []
            sorted_records = sorted(records, key=lambda r: r.priority)
            hostnames = [r.host.rstrip(".").lower() for r in sorted_records]
            return True, hostnames
        except aiodns.error.DNSError:
            return False, []
        except asyncio.TimeoutError:
            return False, []
        except Exception:
            return False, []
