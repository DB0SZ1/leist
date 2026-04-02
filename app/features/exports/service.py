import csv
from io import StringIO
from fastapi.responses import StreamingResponse

DEFAULT_FILTERS = {
    "max_burn_score": 50,
    "exclude_spam_filters": ["Mimecast", "Barracuda"],
    "min_domain_age_days": 180,
    "max_bounce_score": 5,
    "exclude_syntax_tags": ["disposable", "role"],
    "exclude_invalid_mx": True,
}

def apply_fresh_only(results: list[dict], filters: dict) -> tuple[list[dict], dict]:
    kept, removed = [], {"total": 0, "by_reason": {}}
    for row in results:
        reason = None
        if row.get("burn_score", 0) > filters.get("max_burn_score", 50): reason = "burn_score"
        elif row.get("spam_filter") in filters.get("exclude_spam_filters", []): reason = "spam_filter"
        elif row.get("domain_age_days", 999) < filters.get("min_domain_age_days", 180): reason = "domain_age"
        elif row.get("bounce_score", 0) > filters.get("max_bounce_score", 5): reason = "bounce_score"
        elif row.get("syntax_tag") in filters.get("exclude_syntax_tags", []): reason = "syntax"
        elif filters.get("exclude_invalid_mx") and not row.get("mx_valid"): reason = "invalid_mx"

        if reason:
            removed["total"] += 1
            removed["by_reason"][reason] = removed["by_reason"].get(reason, 0) + 1
        else:
            kept.append(row)
    return kept, removed
