---
name: listintel-layers
description: >
  Exhaustive reference for all 8 List Intel processing layers.
  Read this when building, modifying, debugging, or extending any intelligence layer.
  Covers every layer's purpose, exact inputs, exact outputs, internal algorithm,
  edge cases, failure modes, data contracts, performance characteristics,
  signature files, and how each layer interacts with shared infrastructure.
  This is the single source of truth for the processing pipeline's intelligence logic.
---

# List Intel — Processing Layers Reference

---

## Layer Architecture Overview

Every layer lives in `app/features/processing/layers/`. Every layer is a Python module
that exports a single async class conforming to the `BaseLayer` interface.

### `BaseLayer` — The Contract Every Layer Must Follow

```python
# app/features/processing/layers/base.py

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

@dataclass
class LayerResult:
    """
    Returned by every layer's .run() method.
    Fields not populated by this layer remain None — never use 0 or "" as "unknown".
    None means "this layer did not produce a value for this field".
    """
    # Layer identification
    layer_id: str        # e.g. "syntax", "burn_score"
    success: bool        # did the layer complete without error?
    error: str | None    # populated if success=False

    # Output fields — each layer populates its own subset
    # All other fields remain None
    syntax_valid: bool | None = None
    syntax_tag: str | None = None          # valid/role/disposable/invalid
    mx_valid: bool | None = None
    mx_records: list[str] | None = None    # raw MX hostnames, used by layers 2+3
    spam_filter: str | None = None         # Mimecast/Proofpoint/Barracuda/null
    email_infra: str | None = None         # GWS/M365/Exchange/SMTP
    domain_age_days: int | None = None
    domain_risk: str | None = None         # Safe/Medium/High/VeryHigh/Unknown
    is_catchall: bool | None = None
    catchall_confidence: str | None = None # high/medium/low/unknown
    burn_score: int | None = None          # 0–100
    burn_tag: str | None = None            # Fresh/Warm/Burned/Torched
    burn_times_seen: int | None = None
    bounce_score: int | None = None        # 0–10
    bounce_type: str | None = None         # hard/soft/none
    spam_copy_score: float | None = None   # 0.0–1.0
    spam_copy_flagged: bool | None = None
    spam_copy_reason: str | None = None


class BaseLayer(ABC):
    """
    All 8 layers inherit from this.
    Layers that benefit from bulk pre-computation also implement bulk_lookup().
    """
    layer_id: str = ""

    @abstractmethod
    async def run(self, row: dict, context: dict) -> LayerResult:
        """
        Process a single email row.
        row     — dict from the CSV: {"email": "...", ...original_columns}
        context — pre-computed bulk data: {"domain_ages": {...}, "burn_scores": {...}, "bounce_scores": {...}}
        Must NEVER raise — catch all exceptions, set success=False, populate error field.
        """
        ...

    async def bulk_lookup(self, keys: list[str]) -> dict[str, Any]:
        """
        Override in layers that support bulk pre-computation.
        Returns a dict keyed by the lookup key (email_hash or domain).
        Called once per batch BEFORE per-row processing begins.
        Layers that don't override this return {} (no bulk pre-computation).
        """
        return {}
```

### How Layers Share Data

Layers run in parallel via `asyncio.gather()`. They cannot call each other.
Pre-computed bulk data (burn scores, bounce scores, domain ages) is passed via
the `context` dict to every layer's `.run()` method. This prevents duplicate
DB queries across layers.

```python
# Before per-row processing:
context = {
    "domain_ages":   await layer_domain_age.bulk_lookup(unique_domains),
    "burn_scores":   await layer_burn_score.bulk_lookup(email_hashes),
    "bounce_scores": await layer_bounce_history.bulk_lookup(email_hashes),
    # Layers 2+3 share MX data pulled from Layer 1's output
}
```

### Layer Execution Order

Technically all layers run in parallel, but Layer 1 has a special role:
it produces the MX record data that Layers 2 and 3 need.
In practice this is handled by running Layer 1 first per-batch (it's always fast —
pure regex + DNS), then passing its MX output into the context for Layers 2 and 3.

```
Phase 1 (per batch, sequential):
  Layer 1 (Syntax + MX)     → produces mx_records per email
  Domain Age bulk_lookup     → produces domain_ages dict
  Burn Score bulk_lookup     → produces burn_scores dict
  Bounce History bulk_lookup → produces bounce_scores dict

Phase 2 (per email, all parallel):
  Layer 2 (Spam Filter)      ← reads mx_records from context
  Layer 3 (Infrastructure)   ← reads mx_records from context
  Layer 4 (Catch-All)        ← reads domain from email
  Layer 5 (Bounce History)   ← reads from context["bounce_scores"]
  Layer 6 (Domain Age)       ← reads from context["domain_ages"]
  Layer 7 (AI Spam Trap)     ← reads domain_age, syntax_tag from context
  Layer 8 (Burn Score)       ← reads from context["burn_scores"]
```

### Output Column Reference

Every column added to the enriched CSV output:

| Column | Type | Added by | Possible values |
|---|---|---|---|
| `syntax_valid` | bool | Layer 1 | true/false |
| `syntax_tag` | str | Layer 1 | valid/role/disposable/invalid |
| `mx_valid` | bool | Layer 1 | true/false |
| `spam_filter` | str/null | Layer 2 | Mimecast/Proofpoint/Barracuda/Ironscales/Sophos/Cisco/null |
| `email_infra` | str | Layer 3 | GWS/M365/Exchange/Zoho/Yahoo/SMTP |
| `is_catchall` | bool/null | Layer 4 | true/false/null |
| `catchall_confidence` | str | Layer 4 | high/medium/low/unknown |
| `bounce_score` | int | Layer 5 | 0–10 |
| `bounce_type` | str | Layer 5 | hard/soft/none |
| `domain_age_days` | int/null | Layer 6 | integer or null |
| `domain_risk` | str | Layer 6 | Safe/Medium/High/VeryHigh/Unknown |
| `burn_score` | int | Layer 8 | 0–100 |
| `burn_tag` | str | Layer 8 | Fresh/Warm/Burned/Torched |
| `burn_times_seen` | int | Layer 8 | 0–N |
| `spam_copy_score` | float/null | Layer 7 | 0.0–1.0/null |
| `spam_copy_flagged` | bool/null | Layer 7 | true/false/null |
| `spam_copy_reason` | str/null | Layer 7 | text description/null |

---

## LAYER 1 — Syntax & MX Validation

**File:** `app/features/processing/layers/syntax.py`
**Bulk pre-computation:** No (pure CPU + async DNS — fast enough per-row)
**External dependencies:** `aiodns`, `signatures/disposable_domains.txt`
**Cost:** $0 — DNS queries only
**Average latency:** 0.3–0.8s per batch (500 concurrent DNS queries)

---

### Purpose

Layer 1 is the foundation. It runs first, produces the `mx_records` list that
Layers 2 and 3 depend on, and eliminates structurally invalid emails before
the expensive layers waste compute on them.

It answers three questions:
1. Is this email address syntactically valid?
2. Is it a role address or disposable domain that will never convert?
3. Does the domain have active MX records pointing to a real mail server?

---

### Input

```python
row = {
    "email": "info@bigcorp.com",   # required — all other fields are original CSV columns
    "first_name": "...",           # optional — passed through unchanged
    # ...any other original columns
}
```

The layer always reads `row["email"]`. It normalises to `.lower().strip()` internally.
It never mutates the row — it returns a `LayerResult`.

---

### Syntax Validation Algorithm

```python
import re

# RFC 5322 simplified — covers 99.9% of real email addresses
# Deliberately NOT fully RFC 5322 compliant (the full spec allows quoted strings
# like `"john doe"@example.com` which are valid but never used in cold email)
EMAIL_REGEX = re.compile(
    r'^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$'
)

# These are the specific patterns checked
# Invalid: missing @, multiple @, spaces, invalid TLD
# Valid format: local@domain.tld
```

**Failure modes caught:**
- `john doe@company.com` — spaces in local part → `invalid`
- `john@@company.com` — double @ → `invalid`
- `@company.com` — empty local part → `invalid`
- `john@` — missing domain → `invalid`
- `john@company` — no TLD → `invalid`
- `john@company.c` — TLD too short (min 2 chars) → `invalid`
- `.john@company.com` — leading dot (strict mode) → `invalid`
- `john.@company.com` — trailing dot in local → `invalid`

---

### Role Address Detection

Role addresses are structurally valid emails but belong to a function or department,
not an individual. They almost never convert in cold email outreach.

```python
ROLE_PREFIXES = frozenset([
    # Primary roles — always flag
    "info", "admin", "noreply", "no-reply", "contact", "support",
    "help", "hello", "team", "sales", "billing", "accounts",
    # Marketing roles
    "marketing", "newsletter", "notifications", "alerts", "campaigns",
    "digest", "updates", "news", "promo", "deals",
    # Technical roles
    "webmaster", "postmaster", "abuse", "spam", "security",
    "bounce", "mailer-daemon", "mailerdaemon", "donotreply", "do-not-reply",
    # Service roles
    "careers", "jobs", "press", "media", "legal", "privacy",
    "feedback", "enquiries", "enquiry", "service",
])

def is_role_address(local_part: str) -> bool:
    local = local_part.lower().strip()
    # Exact match
    if local in ROLE_PREFIXES:
        return True
    # Partial match for hyphenated variants: "info-us", "no-reply-2024"
    for prefix in ROLE_PREFIXES:
        if local.startswith(prefix + "-") or local.startswith(prefix + "_"):
            return True
    return False
```

**Output:** `syntax_tag = "role"`, `syntax_valid = True`
Role addresses are flagged but not excluded — the Fresh Only export lets users
choose whether to remove them.

---

### Disposable Domain Detection

```python
# signatures/disposable_domains.txt
# One domain per line, ~8,000 known disposable providers
# Updated periodically — new domains added as they emerge
# Sources: public blocklists + community submissions

# Loading at startup (not per-request):
with open("signatures/disposable_domains.txt") as f:
    DISPOSABLE_DOMAINS = frozenset(line.strip().lower() for line in f if line.strip())

def is_disposable(domain: str) -> bool:
    return domain.lower() in DISPOSABLE_DOMAINS
```

**Known providers in the list (sample):**
mailinator.com, guerrillamail.com, tempmail.com, throwaway.email, yopmail.com,
sharklasers.com, guerrillamailblock.com, grr.la, spam4.me, trashmail.com,
getairmail.com, fakeinbox.com, mailnull.com, spamgourmet.com, spamspot.com,
trashmail.at, dispostable.com, maildrop.cc, nospam.ze.tc, spamfree24.org...

**Output:** `syntax_tag = "disposable"`, `syntax_valid = True`

---

### MX Record Verification

```python
import aiodns

# One resolver instance per batch — shared across all rows
async def create_resolver() -> aiodns.DNSResolver:
    return aiodns.DNSResolver(
        nameservers=["8.8.8.8", "8.8.4.4", "1.1.1.1"],  # Google + Cloudflare
        timeout=3.0,    # 3 second timeout per query
        tries=2,        # retry once on timeout
    )

async def check_mx(domain: str, resolver: aiodns.DNSResolver) -> tuple[bool, list[str]]:
    try:
        records = await resolver.query(domain, "MX")
        if not records:
            return False, []
        # Sort by priority (lowest = highest priority), return hostnames
        sorted_records = sorted(records, key=lambda r: r.priority)
        hostnames = [r.host.rstrip(".").lower() for r in sorted_records]
        return True, hostnames
    except aiodns.error.DNSError as e:
        if e.args[0] == aiodns.error.ARES_ENOTFOUND:
            return False, []   # NXDOMAIN — domain doesn't exist
        if e.args[0] == aiodns.error.ARES_ENODATA:
            return False, []   # No MX records
        return False, []       # Other DNS error
    except asyncio.TimeoutError:
        return False, []       # Timeout after 3s + 1 retry
```

**Why 8.8.8.8 and 1.1.1.1 as nameservers:**
Railway's default DNS resolver may have per-IP rate limits. Explicitly setting
Google and Cloudflare DNS guarantees fast, reliable resolution without hitting
Railway's resolver limits at high concurrency.

**What `mx_records` contains (passed to Layers 2 and 3):**
```
# Example for vp@enterprise.co:
mx_records = [
    "inbound-smtp.mimecast.com",
    "inbound-smtp.mimecast.com"
]

# Example for founder@startup.io:
mx_records = [
    "aspmx.l.google.com",
    "alt1.aspmx.l.google.com",
    "alt2.aspmx.l.google.com"
]
```

---

### Edge Cases

| Scenario | Handling |
|---|---|
| Email with unicode local part (`josé@domain.com`) | Regex rejects — `invalid` |
| IP address as domain (`john@192.168.1.1`) | Regex rejects — `invalid` |
| Subdomain email (`john@mail.company.com`) | Accepted — MX lookup on `mail.company.com` |
| Very long local part (>64 chars, RFC violation) | Accepted — RFC limit not enforced in Phase 1 |
| Domain with no MX but has A record (rare) | `mx_valid = False` — some very old mail servers |
| Internationalised domain names (IDN) | Punycoded in DNS — handled transparently by aiodns |
| DNS timeout after 3s + retry | `mx_valid = False`, `mx_records = []` |

---

### Full Output

```python
LayerResult(
    layer_id="syntax",
    success=True,
    error=None,
    syntax_valid=True,
    syntax_tag="valid",   # or role/disposable/invalid
    mx_valid=True,
    mx_records=["aspmx.l.google.com", "alt1.aspmx.l.google.com"],
)
```

---

## LAYER 2 — Spam Filter & Gateway Detection

**File:** `app/features/processing/layers/spam_filter.py`
**Bulk pre-computation:** No (reads from Layer 1's mx_records in context)
**External dependencies:** `signatures/spam_filters.json`
**Cost:** $0 — pattern matching on data already fetched in Layer 1
**Average latency:** < 1ms per email (pure dictionary lookup)

---

### Purpose

Identifies which enterprise email security gateway sits in front of the recipient's
inbox. Gateways like Mimecast are specifically designed to block cold email.
Knowing which emails sit behind aggressive gateways before sending allows senders
to exclude them, segment by gateway type, or adjust sending strategies.

---

### How Gateways Work (and Why MX Records Expose Them)

When a company deploys an email security gateway, they change their DNS MX records
to route all inbound email through the gateway's servers first. The gateway scans
for spam, strips malicious attachments, and only forwards clean email to the actual
mail server.

```
Standard setup:      Sender → company.com MX (Microsoft/Google server)
With Mimecast:       Sender → inbound-smtp.mimecast.com → company.com mail server

MX record for company.com:
  BEFORE: mail.protection.outlook.com   (M365 direct)
  AFTER:  inbound-smtp.mimecast.com     (Mimecast)
```

The MX record is publicly readable by anyone — no authentication required.
This is how List Intel knows about the gateway before the sender ever sends a message.

---

### Signature File: `signatures/spam_filters.json`

```json
{
  "Mimecast": [
    "mimecast.com",
    "mimecastprotect.com"
  ],
  "Proofpoint": [
    "pphosted.com",
    "proofpoint.com",
    "ppe-hosted.com",
    "proofpointessentials.com",
    "messagelabs.com"
  ],
  "Barracuda": [
    "barracudanetworks.com",
    "bbarracuda.com",
    "cudamail.com",
    "barracudacentral.org"
  ],
  "Ironscales": [
    "ironscales.com",
    "ironport.com"
  ],
  "Sophos": [
    "sophos.com",
    "reflexion.net",
    "soph.us"
  ],
  "Cisco": [
    "ciscoemail.com",
    "iphmx.com",
    "amp.cisco.com"
  ],
  "Forcepoint": [
    "forcepoint.com",
    "websense.com"
  ],
  "Avanan": [
    "avanan.com"
  ],
  "Microsoft Defender": [
    "eo.outlook.com"
  ]
}
```

**Updating signatures:**
When a new gateway provider is discovered, add its MX hostname patterns here.
No code changes needed — the layer loads this file at startup.

---

### Detection Algorithm

```python
# Load once at startup
with open("signatures/spam_filters.json") as f:
    SPAM_FILTER_SIGNATURES: dict[str, list[str]] = json.load(f)

def detect_spam_filter(mx_records: list[str]) -> str | None:
    if not mx_records:
        return None

    for mx_hostname in mx_records:
        mx_lower = mx_hostname.lower()
        for provider, patterns in SPAM_FILTER_SIGNATURES.items():
            for pattern in patterns:
                if pattern in mx_lower:
                    return provider   # return first match

    return None  # no gateway detected — clean send path


async def run(self, row: dict, context: dict) -> LayerResult:
    mx_records = context.get("mx_records", {}).get(row["email"], [])
    provider = detect_spam_filter(mx_records)
    return LayerResult(
        layer_id="spam_filter",
        success=True,
        error=None,
        spam_filter=provider,  # None if no gateway
    )
```

---

### What Each Provider Means for Cold Email

| Provider | Aggressiveness | Notes |
|---|---|---|
| Mimecast | Very High | Blocks most cold email, especially from new sending domains. Hard to reach. |
| Proofpoint | High | Strict spam scoring. Works against generic outreach templates. |
| Barracuda | High | Pattern-matching focused. Keyword and volume sensitive. |
| Ironscales | Medium-High | AI-based filtering. Adapts to new patterns quickly. |
| Sophos | Medium | Older architecture. More permissive than modern alternatives. |
| Cisco | Medium | Enterprise-grade but more config-dependent than Mimecast. |
| Microsoft Defender | Variable | Depends on org's policy. Can range from permissive to extremely strict. |
| `null` | Low | No detectable gateway — mail goes directly to GWS/M365 native filters. |

---

### Edge Cases

| Scenario | Handling |
|---|---|
| Multiple MX records, first matches Mimecast | Returns "Mimecast" — first match wins |
| Company uses two gateways (rare) | Returns first match only — one column per email |
| Unknown gateway with non-matching MX | Returns null — treated as no gateway |
| MX record is empty (Layer 1 found no MX) | Returns null immediately, no iteration |
| Gateway provider acquired/renamed | Update `spam_filters.json` — no code change |

---

### Full Output

```python
LayerResult(
    layer_id="spam_filter",
    success=True,
    error=None,
    spam_filter="Mimecast",   # or null if no gateway detected
)
```

---

## LAYER 3 — Infrastructure Detection

**File:** `app/features/processing/layers/infra.py`
**Bulk pre-computation:** No (reads mx_records from context)
**External dependencies:** `signatures/infra_providers.json`
**Cost:** $0 — pattern matching on Layer 1's already-fetched MX data
**Average latency:** < 1ms per email (pure dictionary lookup)

---

### Purpose

Identifies what email hosting platform the recipient's domain uses. Different
platforms have different spam tolerance, DKIM/DMARC enforcement levels, and
sending volume limits that affect cold email deliverability.

Agencies use this to segment campaigns — send GWS recipients with one configuration,
M365 recipients with another, and handle custom SMTP domains manually.

---

### Signature File: `signatures/infra_providers.json`

```json
{
  "GWS": [
    "google.com",
    "googlemail.com",
    "aspmx.l.google.com",
    "smtp.google.com",
    "googlehosted.com"
  ],
  "M365": [
    "mail.protection.outlook.com",
    "outlook.com",
    "microsoft.com",
    "hotmail.com",
    "onmicrosoft.com"
  ],
  "Exchange": [
    "exchangelabs.com",
    "exchange.microsoft.com",
    "msexchange.com"
  ],
  "Zoho": [
    "zoho.com",
    "zohomail.com",
    "zohocorp.com"
  ],
  "Yahoo": [
    "yahoodns.net",
    "yahoo.com",
    "yahoomail.com",
    "yahoosmallbusiness.com"
  ],
  "Fastmail": [
    "fastmail.com",
    "messagingengine.com"
  ],
  "Proton": [
    "protonmail.ch",
    "protonmail.com"
  ],
  "iCloud": [
    "icloud.com",
    "me.com",
    "mac.com"
  ],
  "Rackspace": [
    "emailsrvr.com",
    "rackspace.com"
  ]
}
```

---

### Detection Algorithm

```python
def detect_infra(mx_records: list[str]) -> str:
    if not mx_records:
        return "SMTP"   # no MX = assume custom SMTP

    for mx in mx_records:
        mx_lower = mx.lower()
        for provider, patterns in INFRA_SIGNATURES.items():
            for pattern in patterns:
                if pattern in mx_lower:
                    return provider

    return "SMTP"   # default: unknown / custom mail server
```

**Important difference from Layer 2:**
Layer 2 returns `None` when no gateway is found (absence has meaning — it means
there's a clean path). Layer 3 returns `"SMTP"` when no known provider matches,
because every email has *some* infrastructure — we just don't recognise it.
`"SMTP"` means "custom or unknown mail server."

---

### Infrastructure Characteristics for Senders

| Infra | Spam Tolerance | DKIM/DMARC | Notes |
|---|---|---|---|
| GWS | Medium | Enforced | Most common for modern startups/SMBs. Generally good deliverability if sending infra is warm. |
| M365 | Low-Medium | Strict | Large enterprises. Strict DMARC. Benefits from SPF alignment. |
| Exchange | Low | Varies | On-premise. Often IT-managed with custom rules. Unpredictable. |
| Zoho | Medium-High | Soft | Smaller businesses. Less aggressive filtering. Good for cold email. |
| Yahoo | Low | Strict | Consumer email. Poor fit for cold email. |
| SMTP | Variable | Unknown | Custom servers. Could be permissive or highly restrictive. |
| Proton | Low | Strict | Privacy-focused. Near-impossible for cold email. |

---

### Interaction with Layer 2

Layers 2 and 3 read from the same `mx_records` data but answer different questions:
- Layer 2: "What security gateway is in front of this inbox?"
- Layer 3: "What platform hosts this inbox?"

They can return conflicting signals. For example:
```
mx_records = ["inbound-smtp.mimecast.com"]
Layer 2: spam_filter = "Mimecast"
Layer 3: email_infra = "SMTP"   # Mimecast doesn't reveal the underlying infra
```

When Mimecast (or any gateway) is deployed, it replaces the MX records entirely,
so Layer 3 cannot see the underlying email platform anymore. In this case,
`email_infra = "SMTP"` means "we can't tell — it's behind a gateway."

---

### Full Output

```python
LayerResult(
    layer_id="infra",
    success=True,
    error=None,
    email_infra="GWS",   # or M365/Exchange/Zoho/Yahoo/SMTP
)
```

---

## LAYER 4 — Catch-All Detection

**File:** `app/features/processing/layers/catchall.py`
**Bulk pre-computation:** No (SMTP probe per domain, deduplicated within batch)
**External dependencies:** None — raw SMTP connections
**Cost:** $0 — direct SMTP handshake
**Average latency:** 0.5–2s per unique domain (SMTP connection overhead)

---

### Purpose

A catch-all domain is configured to accept email to any address — real or invented.
Standard email verifiers send a VRFY or RCPT TO command and mark the email "valid"
because the server responds positively. The email bounces upon actual delivery
because the specific mailbox doesn't exist.

This is one of the leading causes of surprise bounce rates.

---

### Why Standard Verifiers Miss This

```
Standard verifier flow:
  1. Check MX record → exists ✓
  2. Connect to SMTP server
  3. Send RCPT TO: john@company.com
  4. Server responds: 250 OK
  5. Report: "valid"

Reality:
  The server responds 250 OK to EVERYTHING.
  Even RCPT TO: xxxxrandomxxxx@company.com gets 250 OK.
  john@company.com may not exist — it will bounce on delivery.
```

---

### Phase 1 Detection — Heuristic SMTP Probe

```python
import asyncio
import random
import string

async def probe_catchall(domain: str, mx_host: str) -> tuple[bool | None, str]:
    """
    Returns (is_catchall, confidence).
    is_catchall = True  → domain accepts everything → catch-all
    is_catchall = False → domain rejected probe → probably not catch-all
    is_catchall = None  → could not determine
    """
    # Generate a random local part that virtually cannot exist as a real mailbox
    random_local = "zzz" + "".join(random.choices(string.ascii_lowercase + string.digits, k=10))
    probe_email = f"{random_local}@{domain}"

    try:
        result = await smtp_rcpt_probe(probe_email, mx_host)

        if result.accepted:
            # Domain said 250 OK to a random probe → almost certainly catch-all
            return True, "high"
        elif result.rejected:
            # Domain explicitly rejected the random probe
            # This means it checks mailbox existence → not a catch-all
            return False, "low"
        else:
            # Ambiguous response (451 temporary, 421 etc.)
            return None, "medium"

    except SMTPConnectionError:
        return None, "unknown"
    except asyncio.TimeoutError:
        return None, "unknown"


async def smtp_rcpt_probe(email: str, mx_host: str) -> SMTPProbeResult:
    """
    Establishes SMTP connection and checks RCPT TO response.
    NEVER sends an actual email — disconnects after RCPT TO check.

    SMTP handshake:
      Client: EHLO listintel.io
      Server: 250 OK + capabilities
      Client: MAIL FROM: <verify@listintel.io>
      Server: 250 OK
      Client: RCPT TO: <probe@target.domain>
      Server: 250 OK (accepted) or 550 (rejected) or 4xx (temp fail)
      Client: QUIT
    """
    reader, writer = await asyncio.wait_for(
        asyncio.open_connection(mx_host, 25),
        timeout=5.0
    )
    try:
        await _read_response(reader)                    # 220 greeting
        writer.write(b"EHLO listintel-verify.io\r\n")
        await writer.drain()
        await _read_response(reader)                    # 250 capabilities
        writer.write(f"MAIL FROM: <noreply@listintel-verify.io>\r\n".encode())
        await writer.drain()
        await _read_response(reader)                    # 250 OK
        writer.write(f"RCPT TO: <{email}>\r\n".encode())
        await writer.drain()
        response = await _read_response(reader)         # 250 or 550
        code = int(response[:3])
        return SMTPProbeResult(
            accepted=code == 250,
            rejected=code in (550, 551, 552, 553, 554),
        )
    finally:
        writer.write(b"QUIT\r\n")
        await writer.drain()
        writer.close()
        await writer.wait_closed()
```

---

### Domain Deduplication

The catch-all check is expensive (SMTP connection) and the result applies to the
entire domain, not individual emails. Before per-row processing:

```python
# All 12,400 emails might have only 2,800 unique domains
unique_domains = {}
for row in rows:
    domain = extract_domain(row["email"])
    mx = context.get("mx_records", {}).get(row["email"], [""])[0]
    if domain not in unique_domains:
        unique_domains[domain] = mx

# Run probes once per domain, not once per email
catchall_results = {}
for domain, mx_host in unique_domains.items():
    is_catchall, confidence = await probe_catchall(domain, mx_host)
    catchall_results[domain] = (is_catchall, confidence)

# Per-row: just look up the pre-computed result
for row in rows:
    domain = extract_domain(row["email"])
    row_result = catchall_results.get(domain, (None, "unknown"))
```

This converts O(N emails) SMTP connections to O(N unique domains) connections —
often a 4–10x reduction in connections and total probe time.

---

### Phase 2 — Deep Verification (Post-Revenue)

Phase 2 adds MillionVerifier or ZeroBounce wholesale API calls for definitive
catch-all verification. These services maintain persistent SMTP infrastructure,
warm IPs, and more sophisticated probing. Cost: ~$0.00008 per email.

Phase 2 is gated behind revenue milestone. Phase 1 heuristics are accurate
for ~80% of cases.

---

### Confidence Levels

| Confidence | Meaning | Action in Fresh Only export |
|---|---|---|
| `high` | Domain accepted random probe | Default: exclude from export |
| `medium` | Ambiguous SMTP response | Optional: user decides |
| `low` | Domain rejected random probe | Include — probably not catch-all |
| `unknown` | Could not reach SMTP server | Optional: conservative users exclude |

---

### Edge Cases

| Scenario | Handling |
|---|---|
| Port 25 blocked by Railway | Retry on port 587; if both blocked: `unknown` |
| SMTP greylisting (temporary 4xx) | Returns `unknown` — greylisting ≠ catch-all |
| MX host is down | Timeout → `unknown` |
| Domain exists but rejects all connections | `unknown` — can't distinguish from catch-all |
| Catch-all with rate limiting (rejects after N probes) | May return `low` incorrectly — Phase 2 handles this |
| Google Workspace always returns 250 for RCPT TO in some configs | May produce false positive for catch-all |

---

### Full Output

```python
LayerResult(
    layer_id="catchall",
    success=True,
    error=None,
    is_catchall=True,
    catchall_confidence="high",
)
```

---

## LAYER 5 — Bounce History Score

**File:** `app/features/processing/layers/bounce_history.py`
**Bulk pre-computation:** Yes — one DB query for all email hashes in the batch
**External dependencies:** PostgreSQL `bounce_events` table
**Cost:** $0 — internal database query
**Average latency:** < 50ms for bulk query across entire batch

---

### Purpose

Cross-references every email against a rolling 90-day database of known bounces.
An email can pass every other check (valid syntax, active MX, no catch-all, fresh
burn score) and still have bounced 8 times in the last month on other users' lists.

This layer catches the "walking dead" — emails that look valid but are functionally
dead.

---

### How Bounce Data Gets Into the System

Users contribute bounced emails after their campaigns via:
```
POST /api/v1/bounces
Content-Type: multipart/form-data

file: <CSV with bounced email addresses>
```

```python
# app/features/bounces/service.py
async def submit_bounces(db: AsyncSession, user_id: str, rows: list[dict]):
    # Normalise, hash, and bulk-insert
    inserts = []
    for row in rows:
        email = row.get("email", "").lower().strip()
        if not email:
            continue
        inserts.append({
            "email_hash": hash_email(email),
            "user_id": user_id,
            "bounce_type": normalise_bounce_type(row.get("bounce_type", "hard")),
            "bounced_at": parse_date(row.get("bounced_at")) or datetime.now(UTC),
        })

    # Idempotent — duplicate hash+user_id+bounced_at combos are ignored
    await db.execute(
        insert(BounceEvent)
        .values(inserts)
        .on_conflict_do_nothing(
            index_elements=["email_hash", "user_id", "bounced_at"]
        )
    )
```

**Bounce type mapping from common ESP exports:**

| Input string | Normalised to |
|---|---|
| "hard", "permanent", "5xx", "user unknown", "invalid" | `hard` |
| "soft", "temporary", "4xx", "mailbox full", "quota" | `soft` |
| anything else | `hard` (conservative default) |

---

### Bulk Lookup Algorithm

```python
async def bulk_lookup(
    self,
    db: AsyncSession,
    email_hashes: list[str],
) -> dict[str, BounceResult]:

    if not email_hashes:
        return {}

    # Single query for all emails in the batch
    # Uses the idx_bounce_hash index on email_hash column
    rows = await db.execute(
        select(
            bounce_events.c.email_hash,
            func.count().label("total"),
            func.sum(
                case((bounce_events.c.bounce_type == "hard", 1), else_=0)
            ).label("hard_count"),
            func.sum(
                case((bounce_events.c.bounce_type == "soft", 1), else_=0)
            ).label("soft_count"),
        )
        .where(
            bounce_events.c.email_hash.in_(email_hashes),
            bounce_events.c.bounced_at > datetime.now(UTC) - timedelta(days=90),
        )
        .group_by(bounce_events.c.email_hash)
    )

    result_map = {}
    for row in rows:
        score = min(row.hard_count * 3 + row.soft_count * 1, 10)
        bounce_type = (
            "hard" if row.hard_count > 0 else
            "soft" if row.soft_count > 0 else
            "none"
        )
        result_map[row.email_hash] = BounceResult(
            bounce_score=score,
            bounce_type=bounce_type,
            total_events=row.total,
        )

    # Emails not in bounce_events = no known bounces
    for h in email_hashes:
        if h not in result_map:
            result_map[h] = BounceResult(bounce_score=0, bounce_type="none", total_events=0)

    return result_map
```

---

### Scoring Formula

```
bounce_score = min(hard_bounces * 3 + soft_bounces * 1, 10)
```

| Score | Meaning |
|---|---|
| 0 | No known bounces in last 90 days |
| 1–2 | One or two soft bounces — marginal risk |
| 3 | One hard bounce — address almost certainly dead |
| 4–6 | Multiple bounce events — high risk |
| 7–9 | Bounced many times for many users |
| 10 | Maximum — this address has been bouncing repeatedly |

**Why hard bounces score 3x:**
A hard bounce (550 User Unknown, 551 User Not Local, etc.) means the mailbox
definitively does not exist. A soft bounce (421 Temporarily Unavailable, 452 Mailbox Full)
might resolve. Hard bounces almost never recover — they carry 3x the weight.

---

### The 90-Day Rolling Window

Bounce status is time-sensitive. An email that bounced 18 months ago may be:
- A re-created mailbox (company rehired the person)
- A domain that changed ownership
- A mailbox that was temporarily disabled

The 90-day window reflects current deliverability reality. Older data is automatically
excluded from the query — no manual cleanup required.

**Index design for the window:**
```sql
-- idx_bounce_hash covers the WHERE clause hash lookup
CREATE INDEX idx_bounce_hash ON bounce_events(email_hash);

-- A composite index on (email_hash, bounced_at) would be faster but
-- is unnecessary at current scale — simple hash index is sufficient up to ~50M rows
```

---

### Full Output

```python
LayerResult(
    layer_id="bounce_history",
    success=True,
    error=None,
    bounce_score=3,
    bounce_type="hard",
)
```

---

## LAYER 6 — Domain Age & Risk Analysis

**File:** `app/features/processing/layers/domain_age.py`
**Bulk pre-computation:** Yes — deduplicated domains, Redis-first lookup
**External dependencies:** `python-whois`, Redis cache
**Cost:** $0 — WHOIS is free; Redis cache minimises live lookups
**Average latency:** < 10ms (cache hit); 1–3s (cache miss, live WHOIS)

---

### Purpose

Determines how old the domain of each email address is. Very new domains
(under 60 days) are strong candidates for spam traps, honeypots, or low-quality
lead acquisition. Spam trap operators frequently register fresh domains and place
addresses on lists to identify spammers.

---

### Why Domain Age Is a Spam Signal

Spam trap operators need fresh, uncirculated addresses. If a domain appears on
a cold email list within 30 days of registration, it almost certainly came from
a scraped or purchased list — legitimate opt-in subscribers don't appear on lists
within weeks of a domain's registration.

Cold email best practice: never send to any email whose domain is under 90 days old.
List Intel flags at 60 days (High) and 180 days (Medium) as conservative thresholds.

---

### Bulk Lookup with Redis-First Strategy

```python
async def bulk_lookup(
    self,
    redis: aioredis.Redis,
    domains: set[str],
) -> dict[str, DomainAgeResult]:

    result = {}
    uncached = []

    # 1. Check Redis for all domains at once (O(1) per domain)
    cache_keys = [f"whois:{domain}" for domain in domains]
    cached_values = await redis.mget(*cache_keys)

    for domain, cached in zip(domains, cached_values):
        if cached is not None:
            if cached == "unknown":
                result[domain] = DomainAgeResult(age_days=None, risk="Unknown")
            else:
                try:
                    age_days = int(cached)
                    result[domain] = DomainAgeResult(
                        age_days=age_days,
                        risk=classify_risk(age_days),
                    )
                except ValueError:
                    uncached.append(domain)
        else:
            uncached.append(domain)

    # 2. Live WHOIS only for uncached domains
    if uncached:
        # Run WHOIS lookups concurrently (in thread pool — python-whois is sync)
        tasks = [self._whois_lookup(domain) for domain in uncached]
        whois_results = await asyncio.gather(*tasks, return_exceptions=True)

        for domain, whois_result in zip(uncached, whois_results):
            if isinstance(whois_result, Exception):
                # Cache the failure briefly (7 days) — WHOIS servers have rate limits
                await redis.setex(f"whois:{domain}", 86400 * 7, "unknown")
                result[domain] = DomainAgeResult(age_days=None, risk="Unknown")
            else:
                await redis.setex(
                    f"whois:{domain}",
                    86400 * 30,  # 30-day TTL
                    str(whois_result.age_days),
                )
                result[domain] = whois_result

    return result


async def _whois_lookup(self, domain: str) -> DomainAgeResult:
    """Run python-whois in a thread pool (it's a sync library)."""
    try:
        info = await asyncio.to_thread(whois.whois, domain)
        creation_date = self._parse_creation_date(info)
        if not creation_date:
            return DomainAgeResult(age_days=None, risk="Unknown")
        age_days = (datetime.now() - creation_date.replace(tzinfo=None)).days
        return DomainAgeResult(age_days=max(0, age_days), risk=classify_risk(age_days))
    except Exception:
        return DomainAgeResult(age_days=None, risk="Unknown")


def _parse_creation_date(self, info) -> datetime | None:
    """
    python-whois returns creation_date as datetime, list[datetime], or None.
    Different registrars return different formats — handle all.
    """
    cd = info.creation_date
    if not cd:
        return None
    if isinstance(cd, list):
        # Some registrars return multiple dates — take the earliest
        valid_dates = [d for d in cd if isinstance(d, datetime)]
        return min(valid_dates) if valid_dates else None
    if isinstance(cd, datetime):
        return cd
    return None
```

---

### Risk Classification

```python
def classify_risk(age_days: int | None) -> str:
    if age_days is None:
        return "Unknown"
    if age_days >= 365:
        return "Safe"
    if age_days >= 180:
        return "Medium"
    if age_days >= 60:
        return "High"
    return "VeryHigh"   # under 60 days — extreme caution
```

| Risk | Age | Cold email guidance |
|---|---|---|
| Safe | 365+ days | Send normally |
| Medium | 180–365 days | Send with monitoring — watch bounce rate |
| High | 60–180 days | Exclude by default in Fresh Only presets |
| VeryHigh | < 60 days | Almost always spam trap or low-quality — exclude |
| Unknown | WHOIS unavailable | Conservative: treat as Medium |

---

### Cache TTL Rationale

**30 days for known ages:**
A domain's age increases by 1 day per day. A domain that was 847 days old today
will be 877 days old in 30 days — still "Safe." The risk classification won't
change for Safe and Medium domains within a 30-day window. For High/VeryHigh
domains, they'll age into a lower risk tier over weeks — the 30-day TTL
is conservative but acceptable.

**7 days for failed lookups:**
WHOIS servers are often rate-limited. A failed lookup today may succeed in 3 days
once the rate limit resets. 7 days prevents hammering the WHOIS server while
giving failed lookups a chance to refresh.

---

### Edge Cases

| Scenario | Handling |
|---|---|
| Domain registered but WHOIS privacy enabled | `python-whois` returns redacted info — try to parse anyway, fall back to `unknown` |
| Newly registered domain (<1 day old) | `age_days = 0` → `VeryHigh` |
| WHOIS server timeout | Treated as exception → `Unknown`, cached 7 days |
| Domain with multiple creation dates (re-registered) | Take the earliest date |
| ccTLD domains (`.co.uk`, `.com.au`) | `python-whois` supports most — fall back to `unknown` if unsupported |
| Subdomain (`john@mail.company.com`) | WHOIS lookup is on `company.com`, not `mail.company.com` |

---

### Full Output

```python
LayerResult(
    layer_id="domain_age",
    success=True,
    error=None,
    domain_age_days=847,
    domain_risk="Safe",
)
```

---

## LAYER 7 — AI Spam Trap Detection

**File:** `app/features/processing/layers/spam_copy.py`
**Bulk pre-computation:** No (conditional — only runs on flagged emails)
**External dependencies:** OpenRouter API (`mistralai/mistral-7b-instruct:free`)
**Cost:** $0 for free-tier volume; ~$0.0002/1k tokens at scale
**Average latency:** 800ms–2s per flagged email (LLM inference)

---

### Purpose

Detects spam traps and honeypot addresses using AI pattern recognition.
Static rules (Layer 1's disposable list, Layer 6's domain age) catch the obvious
cases. This layer catches the subtle ones — addresses crafted to look legitimate
but placed specifically to identify spammers.

---

### What a Spam Trap Looks Like

**Classic spam traps:**
- Addresses that were once real but abandoned — the ISP recycles them as traps
- Dictionary attacks: `abuse@domain.com`, `test@domain.com`, `user@domain.com`

**Honeypot traps:**
- Addresses embedded invisibly in web pages — only scrapers find them
- Patterns: `contact-form-7@newsite.io`, `noreply-verify@domain.ai`

**Typo trap patterns:**
- `ceo@googel.com` (misspelled Google)
- `admin@maicrosoft.com` (misspelled Microsoft)

Static regex can catch some patterns but AI catches emerging variations and
context-dependent signals that rules miss.

---

### Trigger Conditions — AI Layer Is Conditional

Running Mistral 7B on every email is wasteful. In a typical 10,000-email list,
maybe 50–200 emails warrant AI analysis. The layer triggers only when at least
one condition is met:

```python
TRIGGER_CONDITIONS = [
    # Very new domain — highest risk
    lambda ctx: ctx.get("domain_age_days") is not None and ctx["domain_age_days"] < 30,

    # Explicit honeypot naming in local part
    lambda ctx: any(
        kw in ctx["email_local"].lower()
        for kw in [
            "spamtrap", "honeypot", "trap", "probe", "poisoned",
            "verif", "test-email", "noreply-test", "abuse-check",
        ]
    ),

    # Suspicious domain keywords
    lambda ctx: any(
        kw in ctx["email_domain"].lower()
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

async def run(self, row: dict, context: dict) -> LayerResult:
    email = row["email"].lower().strip()
    local, domain = email.split("@", 1)

    ctx = {
        "email_local": local,
        "email_domain": domain,
        "domain_age_days": context.get("domain_ages", {}).get(domain, {}).age_days,
        "syntax_tag": context.get("syntax_results", {}).get(email, {}).syntax_tag,
        "mx_valid": context.get("mx_results", {}).get(email, {}).mx_valid,
    }

    # Only run AI if at least one trigger fires
    if not any(trigger(ctx) for trigger in TRIGGER_CONDITIONS):
        return LayerResult(
            layer_id="spam_copy",
            success=True,
            error=None,
            spam_copy_score=None,   # null = not analysed, not flagged
            spam_copy_flagged=None,
            spam_copy_reason=None,
        )

    return await self._run_ai_analysis(email, ctx)
```

---

### AI Analysis Prompt

```python
async def _run_ai_analysis(self, email: str, ctx: dict) -> LayerResult:
    domain_age_str = (
        f"{ctx['domain_age_days']} days old"
        if ctx.get("domain_age_days") is not None
        else "unknown age"
    )

    prompt = f"""You are a spam trap detection expert. Analyse this email address for spam trap or honeypot characteristics.

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

    try:
        response = await self.openrouter_client.chat(
            model="mistralai/mistral-7b-instruct:free",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=120,
            temperature=0.1,   # low temperature = consistent, deterministic output
        )

        raw_text = response.choices[0].message.content.strip()

        # Strip any accidental markdown wrapping
        raw_text = raw_text.replace("```json", "").replace("```", "").strip()
        parsed = json.loads(raw_text)

        score = max(0.0, min(1.0, float(parsed.get("score", 0.0))))
        flagged = bool(parsed.get("flagged", score >= 0.7))
        reason = str(parsed.get("reason", ""))[:200]   # cap reason length

        return LayerResult(
            layer_id="spam_copy",
            success=True,
            error=None,
            spam_copy_score=round(score, 2),
            spam_copy_flagged=flagged,
            spam_copy_reason=reason if flagged else None,
        )

    except json.JSONDecodeError:
        # Model returned non-JSON — skip gracefully
        return LayerResult(
            layer_id="spam_copy", success=False,
            error="Model returned non-JSON response",
            spam_copy_score=None, spam_copy_flagged=None,
        )
    except Exception as e:
        return LayerResult(
            layer_id="spam_copy", success=False,
            error=str(e),
            spam_copy_score=None, spam_copy_flagged=None,
        )
```

---

### Score Interpretation

| Score | Meaning | Recommended action |
|---|---|---|
| null | AI layer did not run (no triggers fired) | No action — treat as clean |
| 0.0–0.3 | Very likely legitimate | Include in all exports |
| 0.3–0.5 | Some suspicious signals | Include with caution |
| 0.5–0.7 | Suspicious — worth reviewing | Flag in UI, user decides |
| 0.7–0.9 | Likely spam trap | Exclude from Fresh Only export |
| 0.9–1.0 | Almost certainly spam trap | Exclude from all exports |

Threshold for `flagged = true`: score >= 0.7

---

### Why Mistral 7B (Free Tier)

At List Intel's current scale, AI analysis runs on perhaps 2–5% of emails.
For a 10,000-email job with 200 triggered emails, at ~500 tokens per prompt+response,
that's 100,000 tokens. Mistral 7B free tier supports this comfortably.

When volume justifies it, the model string in config switches to
`mistralai/mistral-7b-instruct` (paid) or `anthropic/claude-haiku` for
better accuracy on edge cases.

---

### Full Output

```python
# When triggered and flagged:
LayerResult(
    layer_id="spam_copy",
    success=True,
    error=None,
    spam_copy_score=0.92,
    spam_copy_flagged=True,
    spam_copy_reason="Domain registered 8 days ago, local part matches honeypot naming convention",
)

# When not triggered:
LayerResult(
    layer_id="spam_copy",
    success=True,
    error=None,
    spam_copy_score=None,
    spam_copy_flagged=None,
    spam_copy_reason=None,
)
```

---

## LAYER 8 — Burn Score Network

**File:** `app/features/burn/service.py`
**Bulk pre-computation:** Yes — one DB query for all email hashes in the batch
**External dependencies:** PostgreSQL `burn_pool` table
**Cost:** $0 — internal database
**Average latency:** < 50ms for bulk query across entire batch

---

### Purpose

The flagship feature. Measures how "burned" an email address is — how many
distinct users on the platform have already uploaded it and presumably sent to it.
A score of 0 means nobody else on the platform has this address. A score of 100
means 100+ different senders have been blasting it in the last 90 days.

This is a proxy for market saturation — how many cold emailers are competing
for this inbox right now.

---

### The Privacy Architecture — GDPR by Design

The burn pool stores zero plaintext email addresses. Ever.

```
User uploads: john@company.com
System stores: a3f8c91e4d2b7... (SHA-256 hash)

Process:
1. email.lower().strip()
2. SHA-256 hash
3. Store hash only

Reversal is cryptographically infeasible:
SHA-256 is a one-way function.
The hash database cannot be reverse-engineered into email addresses.
A GDPR audit of the burn_pool table finds only anonymous hashes.
```

---

### How Emails Enter the Burn Pool

After the Celery worker parses the uploaded CSV and extracts all syntactically
valid emails, they are hashed and bulk-inserted into the burn pool immediately
— before per-email layer processing even starts:

```python
async def bulk_insert_to_burn_pool(
    db: AsyncSession,
    rows: list[dict],
    user_id: str,
    job_id: str,
):
    # Only insert valid emails — skip syntax failures
    valid_rows = [r for r in rows if r.get("syntax_valid") is not False]

    now = datetime.now(UTC)
    inserts = [
        {
            "email_hash": hash_email(r["email"]),
            "domain_hash": hash_domain(extract_domain(r["email"])),
            "user_id": user_id,
            "job_id": job_id,
            "uploaded_at": now,
        }
        for r in valid_rows
    ]

    # Bulk insert — one query regardless of list size
    # No uniqueness constraint on burn_pool — same user uploading same list
    # twice creates duplicate rows, but COUNT(DISTINCT user_id) handles this
    await db.execute(insert(BurnPool).values(inserts))
    await db.commit()
```

**Why no deduplication on insert:**
The burn score query uses `COUNT(DISTINCT user_id)`, not `COUNT(*)`.
If user A uploads the same list 10 times, all those rows have user_id=A.
The distinct count still returns 1 for that user. Deduplication at insert time
would add complexity and slow down the bulk insert for no benefit.

---

### Bulk Score Lookup

```python
async def bulk_lookup(
    self,
    db: AsyncSession,
    email_hashes: list[str],
) -> dict[str, BurnScoreResult]:

    if not email_hashes:
        return {}

    # THE core query — runs once for the entire batch
    # Uses idx_burn_email_hash index + idx_burn_uploaded_at filter
    rows = await db.execute(
        select(
            burn_pool.c.email_hash,
            func.count(func.distinct(burn_pool.c.user_id)).label("unique_senders"),
        )
        .where(
            burn_pool.c.email_hash.in_(email_hashes),
            burn_pool.c.uploaded_at > datetime.now(UTC) - timedelta(days=90),
        )
        .group_by(burn_pool.c.email_hash)
    )

    result_map: dict[str, BurnScoreResult] = {}

    for row in rows:
        raw = row.unique_senders
        score = min(int((raw / 100) * 100), 100)  # normalise to 0–100, cap at 100
        result_map[row.email_hash] = BurnScoreResult(
            burn_score=score,
            burn_times_seen=raw,
            burn_tag=self._classify_tag(score),
        )

    # Emails not found in pool = score 0 = Fresh
    for h in email_hashes:
        if h not in result_map:
            result_map[h] = BurnScoreResult(
                burn_score=0,
                burn_times_seen=0,
                burn_tag="Fresh",
            )

    return result_map


def _classify_tag(self, score: int) -> str:
    if score <= 20:  return "Fresh"
    if score <= 50:  return "Warm"
    if score <= 80:  return "Burned"
    return "Torched"
```

---

### Score Normalisation

```
raw_unique_senders  →  normalised_score

1  → 1
5  → 5
10 → 10
25 → 25
50 → 50
75 → 75
100+ → 100 (cap)
```

The normalisation is currently linear (1 sender = 1 point). At scale,
this may shift to logarithmic (to spread scores more evenly):
```python
# Future: logarithmic normalisation
import math
score = min(int(math.log1p(raw) / math.log1p(100) * 100), 100)
```

---

### Tag Classification

| Tag | Score | Interpretation |
|---|---|---|
| **Fresh** | 0–20 | Few or no senders have this address. Likely a good target. |
| **Warm** | 21–50 | Multiple senders have it. Still worth sending — not oversaturated. |
| **Burned** | 51–80 | Many senders have blasted this. Inbox likely fatigued. |
| **Torched** | 81–100 | 80+ distinct senders in 90 days. Abandon this address. |

---

### The Network Effect Moat — How It Grows

```
Day 1:   10 users,  50k unique emails in pool → most scores = 0 (Fresh)
Month 1: 100 users, 500k emails               → scores start reflecting reality
Month 3: 500 users, 2.5M emails               → meaningful burn signals on popular lists
Month 6: 2k users,  10M emails                → high confidence on enterprise and niche lists
Year 1:  10k users, 50M emails                → network effect fully realised
```

Each new user who uploads a list contributes their email hashes to the pool.
Every existing user's future uploads immediately benefit from that new data.
The pool's value compounds. A competitor launching today starts with 0 hashes —
they cannot buy, steal, or reconstruct this pool without the user base that
generated it. This is the moat.

---

### Index Design for Performance

```sql
-- Primary lookup index
CREATE INDEX idx_burn_email_hash ON burn_pool(email_hash);

-- Date filter — enables the 90-day window to use index scan
CREATE INDEX idx_burn_uploaded ON burn_pool(uploaded_at);

-- Composite for the full query pattern
CREATE INDEX idx_burn_hash_date ON burn_pool(email_hash, uploaded_at);
-- This index directly serves:
-- WHERE email_hash IN (...) AND uploaded_at > (now - 90d)
-- GROUP BY email_hash
```

At 50M rows, the composite index keeps the bulk lookup query under 100ms
for a 1,000-email batch.

---

### Maintenance — Periodic Pool Cleanup

Old data past 90 days adds no value (outside the window) but does consume storage.
Celery beat runs a cleanup task weekly:

```python
@celery_app.task(name="tasks.cleanup_burn_pool")
async def cleanup_burn_pool():
    """
    Delete burn_pool entries older than 180 days.
    We keep 180 days instead of 90 to allow some buffer —
    the query already filters to 90 days, but we don't want
    to delete data that's borderline on slow-running jobs.
    """
    cutoff = datetime.now(UTC) - timedelta(days=180)
    await db.execute(
        delete(BurnPool).where(BurnPool.uploaded_at < cutoff)
    )
    await db.commit()
    log.info("Burn pool cleanup complete", cutoff=cutoff.isoformat())
```

---

### Full Output

```python
LayerResult(
    layer_id="burn_score",
    success=True,
    error=None,
    burn_score=72,
    burn_tag="Burned",
    burn_times_seen=72,
)
```

---

## LAYER INTERACTION MAP

How all 8 layers relate to each other:

```
Layer 1 (Syntax + MX)
├── Produces: mx_records → used by Layers 2 and 3
├── Produces: syntax_tag → used by Layer 7 trigger
├── Produces: mx_valid   → used by Layer 7 trigger
└── Guards: invalid/disposable emails → no further processing cost

Layer 2 (Spam Filter)
└── Reads: mx_records from Layer 1 context
    [Pure pattern match — no new network calls]

Layer 3 (Infrastructure)
└── Reads: mx_records from Layer 1 context
    [Pure pattern match — no new network calls]

Layer 4 (Catch-All)
└── Reads: domain from email
└── Reads: mx_records[0] for SMTP connection target
    [Own SMTP connections — deduplicated by domain]

Layer 5 (Bounce History)
└── Reads: email_hash (from pre-computed bulk_lookup)
    [Pure DB lookup — no network calls]

Layer 6 (Domain Age)
└── Reads: domain from email
└── Produces: domain_age_days → used by Layer 7 trigger
    [Redis-first, WHOIS fallback — deduplicated by domain]

Layer 7 (AI Spam Trap)
└── Reads: domain_age_days from Layer 6 context
└── Reads: syntax_tag from Layer 1 context
└── Reads: mx_valid from Layer 1 context
    [Conditional — only fires when trigger conditions met]

Layer 8 (Burn Score)
└── Reads: email_hash (from pre-computed bulk_lookup)
    [Pure DB lookup — no network calls]
```

---

## FAILURE BEHAVIOUR — EVERY LAYER

Every layer's `.run()` method must NEVER raise an exception.
All exceptions are caught internally and returned as a failed `LayerResult`.
The orchestrator treats a failed result as null values for that layer's columns
and continues processing the remaining layers.

```python
# Pattern every layer follows:
async def run(self, row: dict, context: dict) -> LayerResult:
    try:
        # ... layer logic ...
        return LayerResult(layer_id=self.layer_id, success=True, ...)
    except Exception as e:
        log.error(
            "Layer failed",
            layer=self.layer_id,
            email_hash=hash_email(row.get("email", "")),
            error=str(e)[:200],
        )
        return LayerResult(
            layer_id=self.layer_id,
            success=False,
            error=str(e)[:200],
            # All output fields remain None — "not determined"
        )
```

**What happens in the enriched CSV when a layer fails:**
Each column from that layer is left blank (empty string in CSV).
The user can see in the UI that the layer encountered an error for that row.

---

## ADDING A NEW LAYER

If a new intelligence layer needs to be added (e.g. LinkedIn presence check,
DMARC policy verification, phone number extraction):

1. Create `app/features/processing/layers/new_layer.py`
2. Import and subclass `BaseLayer`
3. Implement `run()` — must be async, must not raise, must return `LayerResult`
4. If batch pre-computation is needed: implement `bulk_lookup()`
5. Add new fields to `LayerResult` dataclass in `base.py`
6. Add the new fields to `JobResult` SQLAlchemy model and Alembic migration
7. Add the new layer instance to the `process_batch()` orchestrator in `pipeline.py`
8. Add the new column to the enriched CSV writer in `exports/service.py`
9. Add the column to the Fresh Only filter panel if it's filterable
10. Update `signatures/` with any pattern files the layer needs
11. Document the layer in this file (listintel_LAYERS.md)

**What you never need to change:**
- The `BaseLayer` contract (unless adding new fields to `LayerResult`)
- The authentication system
- The credit system
- The job lifecycle
- The Celery task structure
- Any other existing layer

Self-contained by design.
