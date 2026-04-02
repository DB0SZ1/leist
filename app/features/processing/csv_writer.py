import csv
from typing import Any


# All enrichment columns in the enriched CSV output
ENRICHMENT_COLUMNS = [
    # Layer 1: Syntax + MX
    "syntax_valid", "syntax_tag", "mx_valid",
    # Layer 2: Spam Filter
    "spam_filter",
    # Layer 3: Infrastructure
    "email_infra",
    # Layer 4: Catch-All
    "is_catchall", "catchall_confidence",
    # Layer 5: Bounce History
    "bounce_score", "bounce_type",
    # Layer 6: Domain Age
    "domain_age_days", "domain_risk",
    # Layer 7: AI Spam Trap
    "spam_copy_score", "spam_copy_flagged", "spam_copy_reason",
    # Layer 8: Burn Score
    "burn_score", "burn_tag", "burn_times_seen",
    # Bonus: Domain Blacklist
    "is_blacklisted", "blacklist_reason",
]


def write_enriched_csv(input_path: str, output_path: str, results: list[dict[str, Any]]):
    """
    Merge enrichment results with original CSV, adding enrichment columns.
    """
    results_map = {r.get("email", "").lower().strip(): r for r in results if r.get("email")}

    with open(input_path, 'r', encoding='utf-8') as fin, \
         open(output_path, 'w', encoding='utf-8', newline='') as fout:
        reader = csv.reader(fin)
        header = next(reader, None)
        if not header:
            return

        email_col = next((i for i, h in enumerate(header) if 'email' in h.lower()), 0)

        writer = csv.writer(fout)
        writer.writerow(header + ENRICHMENT_COLUMNS)

        for row in reader:
            if len(row) > email_col:
                email = row[email_col].strip().lower()
                res = results_map.get(email, {})
                extra = [_format_value(res.get(c)) for c in ENRICHMENT_COLUMNS]
                writer.writerow(row + extra)
            else:
                writer.writerow(row + [""] * len(ENRICHMENT_COLUMNS))


def _format_value(value: Any) -> str:
    """Convert enrichment value to CSV-safe string."""
    if value is None:
        return ""
    if isinstance(value, bool):
        return str(value).lower()
    if isinstance(value, float):
        return str(round(value, 2))
    if isinstance(value, list):
        return "; ".join(str(v) for v in value)
    return str(value)
