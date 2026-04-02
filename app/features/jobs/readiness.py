"""
Send Readiness Score — Composite score answering "should I send this right now?"
Computed from enrichment results of a completed job.
"""
from typing import Any


def compute_readiness(summary: dict[str, Any], total: int) -> dict[str, Any]:
    """
    Compute send readiness score from job summary.
    Returns: {score, label, safe_volume, factors[], action_items[], kill_switch}
    """
    if not summary or total == 0:
        return {"score": 0, "label": "Unknown", "safe_volume": 0, "factors": [], "action_items": [], "kill_switch": False}

    fresh = summary.get("fresh", 0)
    burned = summary.get("burned", 0)
    spam_filter_count = summary.get("spam_filter_count", 0)
    avg_burn = summary.get("avg_burn", 0)
    invalid_count = summary.get("invalid_count", 0)
    catchall_count = summary.get("catchall_count", 0)
    blacklisted_count = summary.get("blacklisted_count", 0)

    # ── Factor scores (each 0–100, higher = better) ──
    fresh_pct = (fresh / total) * 100 if total else 0
    filter_pct = (spam_filter_count / total) * 100 if total else 0
    invalid_pct = (invalid_count / total) * 100 if total else 0
    catchall_pct = (catchall_count / total) * 100 if total else 0
    blacklist_pct = (blacklisted_count / total) * 100 if total else 0

    # Fresh % factor (30% weight) — higher fresh = better
    fresh_score = min(fresh_pct * 1.2, 100)

    # Spam filter exposure factor (25% weight) — lower filter = better
    filter_score = max(100 - filter_pct * 3, 0)

    # Burn score factor (20% weight) — lower avg burn = better
    burn_factor = max(100 - avg_burn * 1.5, 0)

    # Domain risk factor (15% weight) — lower invalid/blacklisted = better
    risk_factor = max(100 - (invalid_pct + blacklist_pct) * 5, 0)

    # Catch-all factor (10% weight) — lower catchall = better
    catchall_factor = max(100 - catchall_pct * 2, 0)

    # Weighted composite
    score = int(
        fresh_score * 0.30 +
        filter_score * 0.25 +
        burn_factor * 0.20 +
        risk_factor * 0.15 +
        catchall_factor * 0.10
    )
    score = max(0, min(100, score))

    # Label
    if score >= 80:
        label = "Ready to Send"
    elif score >= 60:
        label = "Send with Caution"
    elif score >= 40:
        label = "Clean Before Sending"
    else:
        label = "Do Not Send"

    # Safe daily volume recommendation
    if score >= 80:
        safe_volume = 2000
    elif score >= 60:
        safe_volume = 500
    elif score >= 40:
        safe_volume = 200
    else:
        safe_volume = 0

    # Factors breakdown
    factors = [
        {"name": "Fresh contacts", "score": int(fresh_score), "weight": "30%", "detail": f"{fresh_pct:.0f}% of list is fresh"},
        {"name": "Spam filter exposure", "score": int(filter_score), "weight": "25%", "detail": f"{filter_pct:.0f}% behind enterprise gateways"},
        {"name": "Burn saturation", "score": int(burn_factor), "weight": "20%", "detail": f"Avg burn score: {avg_burn}"},
        {"name": "Domain health", "score": int(risk_factor), "weight": "15%", "detail": f"{invalid_pct:.0f}% invalid or blacklisted"},
        {"name": "Catch-all risk", "score": int(catchall_factor), "weight": "10%", "detail": f"{catchall_pct:.0f}% catch-all domains"},
    ]

    # Action items
    action_items = []
    if fresh_pct < 50:
        action_items.append("Over half your list is burned. Use Fresh Only export or source new leads.")
    if filter_pct > 30:
        action_items.append(f"{filter_pct:.0f}% behind enterprise gateways. Use a warmed dedicated domain.")
    if avg_burn > 60:
        action_items.append("High average burn. Your list is over-saturated. Consider trading in Marketplace.")
    if invalid_pct > 5:
        action_items.append(f"{invalid_pct:.0f}% invalid emails detected. Use Auto Fix to clean.")
    if blacklist_pct > 0:
        action_items.append(f"{blacklisted_count} emails on blacklisted domains. Remove before sending.")
    if catchall_pct > 20:
        action_items.append("High catch-all %. These may bounce — consider excluding.")
    if not action_items:
        action_items.append("Your list looks healthy. Safe to send with Fresh Only preset.")

    # Kill switch trigger
    kill_switch = (filter_pct > 30 or avg_burn > 60 or invalid_pct > 5 or blacklist_pct > 2)

    return {
        "score": score,
        "label": label,
        "safe_volume": safe_volume,
        "factors": factors,
        "action_items": action_items,
        "kill_switch": kill_switch,
        "kill_reason": _kill_reason(filter_pct, avg_burn, invalid_pct, blacklist_pct) if kill_switch else None,
    }


def _kill_reason(filter_pct, avg_burn, invalid_pct, blacklist_pct):
    reasons = []
    if filter_pct > 30:
        reasons.append(f"{filter_pct:.0f}% behind enterprise gateways")
    if avg_burn > 60:
        reasons.append(f"average burn score is {avg_burn}")
    if invalid_pct > 5:
        reasons.append(f"{invalid_pct:.0f}% invalid emails")
    if blacklist_pct > 2:
        reasons.append(f"blacklisted domains detected")
    return ". ".join(reasons).capitalize() + "."
