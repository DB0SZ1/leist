from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


@dataclass
class LayerResult:
    """
    Returned by every layer's .run() method.
    Fields not populated by this layer remain None — never use 0 or "" as "unknown".
    None means "this layer did not produce a value for this field".
    """
    # Layer identification
    layer_id: str
    success: bool
    error: str | None = None

    # ── Layer 1: Syntax + MX ──
    syntax_valid: bool | None = None
    syntax_tag: str | None = None          # valid/role/disposable/invalid
    mx_valid: bool | None = None
    mx_records: list[str] | None = None    # raw MX hostnames, used by layers 2+3

    # ── Layer 2: Spam Filter ──
    spam_filter: str | None = None         # Mimecast/Proofpoint/Barracuda/null

    # ── Layer 3: Infrastructure ──
    email_infra: str | None = None         # GWS/M365/Exchange/Zoho/Yahoo/SMTP

    # ── Layer 4: Catch-All ──
    is_catchall: bool | None = None
    catchall_confidence: str | None = None  # high/medium/low/unknown

    # ── Layer 5: Bounce History ──
    bounce_score: int | None = None         # 0–10
    bounce_type: str | None = None          # hard/soft/none

    # ── Layer 6: Domain Age ──
    domain_age_days: int | None = None
    domain_risk: str | None = None          # Safe/Medium/High/VeryHigh/Unknown

    # ── Layer 7: AI Spam Trap ──
    spam_copy_score: float | None = None    # 0.0–1.0
    spam_copy_flagged: bool | None = None
    spam_copy_reason: str | None = None

    # ── Layer 8: Burn Score ──
    burn_score: int | None = None           # 0–100
    burn_tag: str | None = None             # Fresh/Warm/Burned/Torched
    burn_times_seen: int | None = None

    # ── Bonus: Domain Blacklist ──
    is_blacklisted: bool | None = None
    blacklist_reason: str | None = None


class BaseLayer(ABC):
    """
    All processing layers inherit from this.
    Layers that benefit from bulk pre-computation also implement bulk_lookup().
    """
    layer_id: str = ""

    @abstractmethod
    async def run(self, row: dict, context: dict) -> LayerResult:
        """
        Process a single email row.
        row     — dict from the CSV: {"email": "...", ...original_columns}
        context — pre-computed bulk data: {"domain_ages": {...}, "burn_scores": {...}, etc.}
        Must NEVER raise — catch all exceptions, set success=False, populate error field.
        """
        ...

    async def bulk_lookup(self, keys: list[str], **kwargs) -> dict[str, Any]:
        """
        Override in layers that support bulk pre-computation.
        Returns a dict keyed by the lookup key (email_hash or domain).
        Called once per batch BEFORE per-row processing begins.
        Layers that don't override this return {} (no bulk pre-computation).
        """
        return {}
