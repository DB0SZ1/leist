"""
Layer 3 — Infrastructure Detection
Identifies email hosting platform from MX records.
Returns "SMTP" when no known provider matches (every email has SOME infra).
Critical difference from Layer 2 which returns None for no match.
"""
import json
from pathlib import Path
from .base import BaseLayer, LayerResult
import structlog

log = structlog.get_logger()

_INFRA_SIGNATURES: dict[str, list[str]] | None = None

def _load_signatures() -> dict[str, list[str]]:
    global _INFRA_SIGNATURES
    if _INFRA_SIGNATURES is not None:
        return _INFRA_SIGNATURES

    sig_path = Path(__file__).parent.parent / "signatures" / "infra_providers.json"
    if sig_path.exists():
        with open(sig_path) as f:
            _INFRA_SIGNATURES = json.load(f)
    else:
        log.warning("signatures.infra_providers_missing", path=str(sig_path))
        _INFRA_SIGNATURES = {}
    return _INFRA_SIGNATURES


def detect_infra(mx_records: list[str]) -> str:
    if not mx_records:
        return "SMTP"  # no MX = assume custom SMTP

    signatures = _load_signatures()
    for mx in mx_records:
        mx_lower = mx.lower()
        for provider, patterns in signatures.items():
            for pattern in patterns:
                if pattern in mx_lower:
                    return provider

    return "SMTP"  # default: unknown / custom mail server


class InfraLayer(BaseLayer):
    layer_id = "infra"

    async def run(self, row: dict, context: dict) -> LayerResult:
        try:
            email = row.get("email", "").lower().strip()
            mx_records = context.get("mx_records", {}).get(email, [])
            provider = detect_infra(mx_records)

            return LayerResult(
                layer_id=self.layer_id,
                success=True,
                email_infra=provider,
            )
        except Exception as e:
            log.error("layer.infra.failed", error=str(e)[:200])
            return LayerResult(
                layer_id=self.layer_id, success=False,
                error=str(e)[:200],
            )
