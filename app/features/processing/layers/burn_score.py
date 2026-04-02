"""
Layer 8 — Burn Score Network
The flagship feature. Measures market saturation: how many distinct users
on the platform have uploaded this email in the last 90 days.
Privacy by design: stores SHA-256 hashes only, never plaintext.
"""
from typing import Any
from .base import BaseLayer, LayerResult
from app.features.burn.service import hash_email
from app.core.database import async_session_maker
from sqlalchemy import text
import structlog

log = structlog.get_logger()


def classify_tag(score: int) -> str:
    if score <= 20: return "Fresh"
    if score <= 50: return "Warm"
    if score <= 80: return "Burned"
    return "Torched"


class BurnScoreLayer(BaseLayer):
    layer_id = "burn_score"

    async def bulk_lookup(self, keys: list[str], **kwargs) -> dict[str, dict]:
        """
        keys: list of email_hash strings
        Returns: {email_hash: {"burn_score": int, "burn_tag": str, "burn_times_seen": int}}
        """
        if not keys:
            return {}

        result_map = {}
        try:
            async with async_session_maker() as db:
                # Single query for ALL hashes in the batch
                placeholders = ", ".join(f":h{i}" for i in range(len(keys)))
                params = {f"h{i}": h for i, h in enumerate(keys)}
                rows = await db.execute(text(f"""
                    SELECT
                        email_hash,
                        COUNT(DISTINCT user_id) AS unique_senders
                    FROM burn_pool
                    WHERE email_hash IN ({placeholders})
                    AND uploaded_at > NOW() - INTERVAL '90 days'
                    GROUP BY email_hash
                """), params)

                for row in rows:
                    raw = row.unique_senders
                    score = min(raw, 100)  # linear normalisation, cap at 100
                    result_map[row.email_hash] = {
                        "burn_score": score,
                        "burn_tag": classify_tag(score),
                        "burn_times_seen": raw,
                    }
        except Exception as e:
            log.error("burn_score.bulk_lookup_failed", error=str(e)[:200])

        # Emails not in pool = Fresh
        for h in keys:
            if h not in result_map:
                result_map[h] = {
                    "burn_score": 0,
                    "burn_tag": "Fresh",
                    "burn_times_seen": 0,
                }

        return result_map

    async def run(self, row: dict, context: dict) -> LayerResult:
        try:
            email = row.get("email", "").lower().strip()
            email_hash = hash_email(email)

            burn_scores = context.get("burn_scores", {})
            data = burn_scores.get(email_hash, {
                "burn_score": 0,
                "burn_tag": "Fresh",
                "burn_times_seen": 0,
            })

            return LayerResult(
                layer_id=self.layer_id,
                success=True,
                burn_score=data["burn_score"],
                burn_tag=data["burn_tag"],
                burn_times_seen=data["burn_times_seen"],
            )
        except Exception as e:
            log.error("layer.burn_score.failed", error=str(e)[:200])
            return LayerResult(
                layer_id=self.layer_id, success=False,
                error=str(e)[:200],
            )
