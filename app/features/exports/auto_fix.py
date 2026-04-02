"""
Auto Fix My List — One-click cleaning, segmented export.
Removes bad emails and segments by infrastructure.
"""
from typing import Any
import csv
import os


def compute_auto_fix(results: list[dict[str, Any]]) -> dict[str, Any]:
    """
    Analyze results and compute what would be removed/kept by auto fix.
    Returns stats without writing files.
    """
    removed = {"invalid": 0, "disposable": 0, "high_bounce": 0, "torched": 0, "spam_trap": 0, "blacklisted": 0}
    kept = []

    for r in results:
        # Remove invalid syntax
        if not r.get("syntax_valid"):
            removed["invalid"] += 1
            continue
        # Remove disposable
        if r.get("syntax_tag") == "disposable":
            removed["disposable"] += 1
            continue
        # Remove high bounce score (≥7)
        if (r.get("bounce_score") or 0) >= 7:
            removed["high_bounce"] += 1
            continue
        # Remove torched
        if r.get("burn_tag") == "Torched":
            removed["torched"] += 1
            continue
        # Remove flagged spam traps
        if r.get("spam_copy_flagged"):
            removed["spam_trap"] += 1
            continue
        # Remove blacklisted domains
        if r.get("is_blacklisted"):
            removed["blacklisted"] += 1
            continue
        kept.append(r)

    # Segment by infra
    segments = {}
    for r in kept:
        infra = r.get("email_infra", "SMTP") or "SMTP"
        if infra not in segments:
            segments[infra] = 0
        segments[infra] += 1

    total_removed = sum(removed.values())

    return {
        "original_count": len(results),
        "cleaned_count": len(kept),
        "removed_count": total_removed,
        "removed_breakdown": removed,
        "segments": segments,
    }


def write_auto_fix_csvs(input_path: str, results: list[dict[str, Any]], output_dir: str) -> dict[str, str]:
    """
    Write segmented CSVs after auto-fix filtering.
    Returns: {segment_name: file_path}
    """
    os.makedirs(output_dir, exist_ok=True)

    # Filter
    kept = []
    for r in results:
        if not r.get("syntax_valid"):
            continue
        if r.get("syntax_tag") == "disposable":
            continue
        if (r.get("bounce_score") or 0) >= 7:
            continue
        if r.get("burn_tag") == "Torched":
            continue
        if r.get("spam_copy_flagged"):
            continue
        if r.get("is_blacklisted"):
            continue
        kept.append(r)

    # Group by infra
    by_infra: dict[str, list[dict]] = {}
    for r in kept:
        infra = (r.get("email_infra") or "SMTP").lower()
        if infra not in by_infra:
            by_infra[infra] = []
        by_infra[infra].append(r)

    # Write segment files
    files = {}
    base = os.path.splitext(os.path.basename(input_path))[0]

    # Also write a combined clean file
    all_clean_path = os.path.join(output_dir, f"{base}_clean.csv")
    _write_segment_csv(all_clean_path, kept)
    files["all_clean"] = all_clean_path

    for infra, rows in by_infra.items():
        path = os.path.join(output_dir, f"{base}_{infra}.csv")
        _write_segment_csv(path, rows)
        files[infra] = path

    return files


def _write_segment_csv(path: str, rows: list[dict]):
    if not rows:
        return
    fieldnames = list(rows[0].keys())
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)
