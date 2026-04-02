"""
Layer 7 — AI Spam Trap Detection
Conditional layer: only runs AI when ≥1 trigger condition fires.
Catches subtle spam traps and honeypots that static rules miss.
"""
import json
import os
import httpx
from .base import BaseLayer, LayerResult
import structlog

log = structlog.get_logger()

OPENROUTER_API_URL = "https://openrouter.ai/api/v1/chat/completions"

# ── Trigger conditions ──
# AI only runs when at least one trigger fires. In a typical 10k list,
# only 50-200 emails warrant AI analysis.
TRIGGER_CONDITIONS = [
    # Very new domain — highest risk
    lambda ctx: ctx.get("domain_age_days") is not None and ctx["domain_age_days"] < 30,

    # Explicit honeypot naming in local part
    lambda ctx: any(
        kw in ctx.get("email_local", "").lower()
        for kw in [
            "spamtrap", "honeypot", "trap", "probe", "poisoned",
            "verif", "test-email", "noreply-test", "abuse-check",
        ]
    ),

    # Suspicious domain keywords
    lambda ctx: any(
        kw in ctx.get("email_domain", "").lower()
        for kw in [
            "trap", "honeypot", "spam", "verify-mail", "email-check",
            "test-inbox", "catchspam",
        ]
    ),

    # Role address on very new domain (high risk combination)
    lambda ctx: (
        ctx.get("syntax_tag") == "role"
        and ctx.get("domain_age_days") is not None
        and ctx["domain_age_days"] < 90
    ),

    # No MX record but email was somehow given to us
    lambda ctx: ctx.get("mx_valid") is False,
]


def _build_prompt(email: str, ctx: dict) -> str:
    domain_age_str = (
        f"{ctx['domain_age_days']} days old"
        if ctx.get("domain_age_days") is not None
        else "unknown age"
    )
    return f"""You are a spam trap detection expert. Analyse this email address for spam trap or honeypot characteristics.

Email: {email}
Domain age: {domain_age_str}
Has MX records: {ctx.get("mx_valid", "unknown")}
Address type: {ctx.get("syntax_tag", "unknown")}

Spam traps are email addresses placed by ISPs, security researchers, or anti-spam organisations specifically to catch senders who use scraped or purchased lists. Honeypots are email addresses hidden in web pages to catch automated scrapers.

Indicators to check:
- Is the local part a common trap pattern (test, abuse, probe, spamtrap)?
- Does the domain name suggest a trap (trap, honeypot, spam-check)?
- Is the domain brand new (under 30 days) with a suspicious address?
- Is this a role address on a very new domain?

Respond ONLY with valid JSON, no other text:
{{"score": 0.0, "flagged": false, "reason": "brief explanation"}}

score: 0.0 = definitely legitimate, 1.0 = almost certainly a spam trap
flagged: true if score >= 0.7
reason: one sentence explaining the assessment"""


class SpamCopyLayer(BaseLayer):
    layer_id = "spam_copy"

    async def run(self, row: dict, context: dict) -> LayerResult:
        try:
            email = row.get("email", "").lower().strip()
            if "@" not in email:
                return LayerResult(layer_id=self.layer_id, success=True)

            local, domain = email.rsplit("@", 1)

            # Gather context from other layers
            ctx = {
                "email_local": local,
                "email_domain": domain,
                "domain_age_days": context.get("domain_ages", {}).get(domain, {}).get("age_days"),
                "syntax_tag": context.get("syntax_results", {}).get(email, {}).get("syntax_tag"),
                "mx_valid": context.get("mx_results", {}).get(email, {}).get("mx_valid"),
            }

            # Only run AI if at least one trigger fires
            if not any(trigger(ctx) for trigger in TRIGGER_CONDITIONS):
                return LayerResult(
                    layer_id=self.layer_id,
                    success=True,
                    spam_copy_score=None,
                    spam_copy_flagged=None,
                    spam_copy_reason=None,
                )

            return await self._run_ai_analysis(email, ctx)

        except Exception as e:
            log.error("layer.spam_copy.failed", error=str(e)[:200])
            return LayerResult(
                layer_id=self.layer_id, success=False,
                error=str(e)[:200],
            )

    async def _run_ai_analysis(self, email: str, ctx: dict) -> LayerResult:
        api_key = os.getenv("OPENROUTER_API_KEY")
        if not api_key:
            return LayerResult(layer_id=self.layer_id, success=True)

        try:
            prompt = _build_prompt(email, ctx)
            async with httpx.AsyncClient(timeout=15) as client:
                response = await client.post(
                    OPENROUTER_API_URL,
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                        "HTTP-Referer": "https://listintel.io",
                        "X-Title": "List Intel",
                    },
                    json={
                        "model": "mistralai/mistral-7b-instruct:free",
                        "messages": [{"role": "user", "content": prompt}],
                        "max_tokens": 120,
                        "temperature": 0.1,
                    },
                )
                response.raise_for_status()
                result = response.json()

            raw_text = result["choices"][0]["message"]["content"].strip()
            # Strip accidental markdown wrapping
            raw_text = raw_text.replace("```json", "").replace("```", "").strip()
            parsed = json.loads(raw_text)

            score = max(0.0, min(1.0, float(parsed.get("score", 0.0))))
            flagged = bool(parsed.get("flagged", score >= 0.7))
            reason = str(parsed.get("reason", ""))[:200]

            return LayerResult(
                layer_id=self.layer_id,
                success=True,
                spam_copy_score=round(score, 2),
                spam_copy_flagged=flagged,
                spam_copy_reason=reason if flagged else None,
            )

        except json.JSONDecodeError:
            return LayerResult(
                layer_id=self.layer_id, success=False,
                error="Model returned non-JSON response",
            )
        except Exception as e:
            return LayerResult(
                layer_id=self.layer_id, success=False,
                error=str(e)[:200],
            )
