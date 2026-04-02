"""
Processing Pipeline Orchestrator
Two-phase execution model per LAYERS.md spec:
  Phase 1 (sequential per batch): Layer 1 → bulk lookups for layers 4, 5, 6, 8
  Phase 2 (parallel per email): Layers 2-8 via asyncio.gather()
"""
import asyncio
from typing import Any
from dataclasses import asdict

from .layers.syntax import SyntaxLayer
from .layers.spam_filter import SpamFilterLayer
from .layers.infra import InfraLayer
from .layers.catchall import CatchallLayer
from .layers.bounce_score import BounceScoreLayer
from .layers.domain_age import DomainAgeLayer
from .layers.spam_copy import SpamCopyLayer
from .layers.burn_score import BurnScoreLayer
from .layers.domain_blacklist import DomainBlacklistLayer
from .layers.base import LayerResult
from app.features.burn.service import hash_email
import structlog

log = structlog.get_logger()


def _extract_domain(email: str) -> str:
    """Extract base domain, handling subdomains."""
    if "@" not in email:
        return ""
    domain = email.rsplit("@", 1)[1]
    parts = domain.split(".")
    if len(parts) > 2:
        return ".".join(parts[-2:])
    return domain


def _result_to_dict(result: LayerResult) -> dict[str, Any]:
    """Convert LayerResult to flat dict, skipping None values and meta fields."""
    d = asdict(result)
    # Remove meta fields — caller already handles errors separately
    d.pop("layer_id", None)
    d.pop("success", None)
    d.pop("error", None)
    # Remove None values — only include fields this layer actually populated
    return {k: v for k, v in d.items() if v is not None}


async def process_batch(rows: list[dict], context: dict[str, Any] | None = None) -> list[dict]:
    """
    Process a batch of email rows through the 8+1 layer pipeline.
    rows: list of dicts, each with at least {"email": "..."}
    context: optional shared context (e.g. from job metadata)
    Returns: list of enriched dicts with all layer output fields merged.
    """
    if context is None:
        context = {}

    emails = [r.get("email", "").lower().strip() for r in rows]

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # PHASE 1: Sequential per-batch pre-computation
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    # Step 1a: Run Layer 1 (Syntax + MX) for every email
    syntax_layer = SyntaxLayer()
    syntax_results = {}
    mx_records_map = {}  # email -> [mx_hosts]

    syntax_tasks = [syntax_layer.run({"email": e}, {}) for e in emails]
    syntax_outputs = await asyncio.gather(*syntax_tasks, return_exceptions=True)

    for email, result in zip(emails, syntax_outputs):
        if isinstance(result, LayerResult):
            syntax_results[email] = _result_to_dict(result)
            if result.mx_records:
                mx_records_map[email] = result.mx_records
        elif isinstance(result, Exception):
            log.error("pipeline.syntax_failed", email_hash=hash_email(email), error=str(result)[:200])
            syntax_results[email] = {"syntax_valid": False, "syntax_tag": "invalid", "mx_valid": False, "mx_records": []}

    context["mx_records"] = mx_records_map
    context["syntax_results"] = syntax_results

    # Step 1b: Extract unique domains for domain-level bulk lookups
    unique_domains = set()
    domain_mx_map = {}  # domain -> [mx_hosts]
    for email in emails:
        domain = _extract_domain(email)
        if domain:
            unique_domains.add(domain)
            if email in mx_records_map and domain not in domain_mx_map:
                domain_mx_map[domain] = mx_records_map[email]

    # Step 1c: Compute email hashes for email-level bulk lookups
    email_hashes = [hash_email(e) for e in emails]

    # Step 1d: Run bulk lookups in parallel
    catchall_layer = CatchallLayer()
    bounce_layer = BounceScoreLayer()
    domain_age_layer = DomainAgeLayer()
    burn_layer = BurnScoreLayer()

    bulk_results = await asyncio.gather(
        catchall_layer.bulk_lookup(list(unique_domains), mx_records_map=domain_mx_map),
        bounce_layer.bulk_lookup(email_hashes),
        domain_age_layer.bulk_lookup(list(unique_domains)),
        burn_layer.bulk_lookup(email_hashes),
        return_exceptions=True,
    )

    # Store bulk results in context
    context["catchall_results"] = bulk_results[0] if not isinstance(bulk_results[0], Exception) else {}
    context["bounce_scores"] = bulk_results[1] if not isinstance(bulk_results[1], Exception) else {}
    context["domain_ages"] = bulk_results[2] if not isinstance(bulk_results[2], Exception) else {}
    context["burn_scores"] = bulk_results[3] if not isinstance(bulk_results[3], Exception) else {}

    for i, r in enumerate(bulk_results):
        if isinstance(r, Exception):
            log.error("pipeline.bulk_lookup_failed", phase=i, error=str(r)[:200])

    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
    # PHASE 2: Parallel per-email layer processing
    # ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

    per_email_layers = [
        SpamFilterLayer(),       # L2
        InfraLayer(),            # L3
        CatchallLayer(),         # L4 (reads from context)
        BounceScoreLayer(),      # L5 (reads from context)
        DomainAgeLayer(),        # L6 (reads from context)
        SpamCopyLayer(),         # L7 (conditional AI)
        BurnScoreLayer(),        # L8 (reads from context)
        DomainBlacklistLayer(),  # Bonus
    ]

    sem = asyncio.Semaphore(500)

    async def process_single(row: dict) -> dict:
        async with sem:
            email = row.get("email", "").lower().strip()

            # Start with syntax (L1) results + original row data
            merged = {**row, "email": email}
            merged.update(syntax_results.get(email, {}))

            # Run remaining layers in parallel
            layer_tasks = [layer.run(row, context) for layer in per_email_layers]
            results = await asyncio.gather(*layer_tasks, return_exceptions=True)

            for r in results:
                if isinstance(r, LayerResult):
                    merged.update(_result_to_dict(r))
                elif isinstance(r, Exception):
                    log.error("pipeline.layer_failed", email_hash=hash_email(email), error=str(r)[:200])

            return merged

    enriched = await asyncio.gather(*[process_single(r) for r in rows])
    return list(enriched)


async def process_email(email: str, context: dict[str, Any] | None = None) -> dict[str, Any]:
    """Convenience: process a single email through the full pipeline."""
    results = await process_batch([{"email": email}], context)
    return results[0] if results else {"email": email}
