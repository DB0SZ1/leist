"""
Layer 2 — Spam Filter & Gateway Detection
Identifies enterprise email security gateways from MX records.
Returns None when no gateway detected (clean send path).
"""
import json
from pathlib import Path
from .base import BaseLayer, LayerResult
import structlog

log = structlog.get_logger()

# Load signatures from JSON file at module level
_SPAM_FILTER_SIGNATURES: dict[str, list[str]] | None = None

def _load_signatures() -> dict[str, list[str]]:
    global _SPAM_FILTER_SIGNATURES
    if _SPAM_FILTER_SIGNATURES is not None:
        return _SPAM_FILTER_SIGNATURES

    sig_path = Path(__file__).parent.parent / "signatures" / "spam_filters.json"
    if sig_path.exists():
        with open(sig_path) as f:
            _SPAM_FILTER_SIGNATURES = json.load(f)
    else:
        log.warning("signatures.spam_filters_missing", path=str(sig_path))
        _SPAM_FILTER_SIGNATURES = {}
    return _SPAM_FILTER_SIGNATURES


def detect_spam_filter(mx_records: list[str]) -> str | None:
    if not mx_records:
        return None

    signatures = _load_signatures()
    for mx_hostname in mx_records:
        mx_lower = mx_hostname.lower()
        for provider, patterns in signatures.items():
            for pattern in patterns:
                if pattern in mx_lower:
                    return provider  # first match wins

    return None  # no gateway detected — clean send path


class SpamFilterLayer(BaseLayer):
    layer_id = "spam_filter"

    async def run(self, row: dict, context: dict) -> LayerResult:
        try:
            email = row.get("email", "").lower().strip()
            mx_records = context.get("mx_records", {}).get(email, [])
            provider = detect_spam_filter(mx_records)

            return LayerResult(
                layer_id=self.layer_id,
                success=True,
                spam_filter=provider,
            )
        except Exception as e:
            log.error("layer.spam_filter.failed", error=str(e)[:200])
            return LayerResult(
                layer_id=self.layer_id, success=False,
                error=str(e)[:200],
            )
