"""
Layer 5 — Bounce History Score
Cross-references emails against a 90-day rolling database of known bounces.
Bulk pre-computation: one DB query for all email hashes in the batch.
"""
from typing import Any
from .base import BaseLayer, LayerResult
from app.features.burn.service import hash_email
from app.core.database import async_session_maker
from sqlalchemy import text
import structlog

log = structlog.get_logger()


class BounceScoreLayer(BaseLayer):
    layer_id = "bounce_history"

    async def bulk_lookup(self, keys: list[str], **kwargs) -> dict[str, dict]:
        """
        keys: list of email_hash strings
        Returns: {email_hash: {"bounce_score": int, "bounce_type": str, "total_events": int}}
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
                        COUNT(*) AS total,
                        SUM(CASE WHEN bounce_type = 'hard' THEN 1 ELSE 0 END) AS hard_count,
                        SUM(CASE WHEN bounce_type = 'soft' THEN 1 ELSE 0 END) AS soft_count
                    FROM bounce_events
                    WHERE email_hash IN ({placeholders})
                    AND bounced_at > NOW() - INTERVAL '90 days'
                    GROUP BY email_hash
                """), params)

                for row in rows:
                    # Scoring formula: hard × 3 + soft × 1, cap at 10
                    score = min(row.hard_count * 3 + row.soft_count * 1, 10)
                    bounce_type = (
                        "hard" if row.hard_count > 0 else
                        "soft" if row.soft_count > 0 else
                        "none"
                    )
                    result_map[row.email_hash] = {
                        "bounce_score": score,
                        "bounce_type": bounce_type,
                        "total_events": row.total,
                    }
        except Exception as e:
            log.error("bounce_history.bulk_lookup_failed", error=str(e)[:200])

        # Emails not in bounce_events = no known bounces
        for h in keys:
            if h not in result_map:
                result_map[h] = {
                    "bounce_score": 0,
                    "bounce_type": "none",
                    "total_events": 0,
                }

        return result_map

    async def run(self, row: dict, context: dict) -> LayerResult:
        try:
            email = row.get("email", "").lower().strip()
            email_hash = hash_email(email)

            bounce_scores = context.get("bounce_scores", {})
            data = bounce_scores.get(email_hash, {
                "bounce_score": 0,
                "bounce_type": "none",
                "total_events": 0,
            })

            return LayerResult(
                layer_id=self.layer_id,
                success=True,
                bounce_score=data["bounce_score"],
                bounce_type=data["bounce_type"],
            )
        except Exception as e:
            log.error("layer.bounce_history.failed", error=str(e)[:200])
            return LayerResult(
                layer_id=self.layer_id, success=False,
                error=str(e)[:200],
            )
