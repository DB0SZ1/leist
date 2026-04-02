---
name: listintel-product-vision
description: >
  Complete expanded product vision for List Intel beyond the core intelligence pipeline.
  Covers all recommended new features, the n8n/Make/Zapier native node strategy,
  the outreach automation and tracking layer, integration architecture, and
  the phased roadmap from tool → platform → infrastructure.
  Read this before designing any new feature, planning any sprint, or making
  any product decision. This is the north star document.
---

# List Intel — Expanded Product Vision

---

## The Repositioning

List Intel launched as a list intelligence tool.
The opportunity is to become the intelligence layer that sits underneath
every cold email workflow — not just before you send, but during and after.

```
TODAY:
  Upload list → enrich → download → go elsewhere to send

FUTURE:
  List Intel is where you prepare, launch, track, and improve
  every cold email campaign — without replacing the tools you already use
```

The moat isn't just the burn pool. The moat is becoming the layer
that every cold email workflow passes through.

---

## PRODUCT MAP — Full Vision

```
┌─────────────────────────────────────────────────────────────────────┐
│                         LIST INTEL PLATFORM                          │
│                                                                       │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │
│  │  LIST INTELLIGENCE│  │   OUTREACH HUB  │  │   DOMAIN HEALTH     │  │
│  │  (Core — built)  │  │   (New — Phase 3)│  │   (New — Phase 2)   │  │
│  │                  │  │                  │  │                      │  │
│  │ • 8-layer pipeline│  │ • Campaign builder│  │ • Sender reputation  │  │
│  │ • Burn score pool │  │ • Sequence editor │  │ • RBL checker        │  │
│  │ • Marketplace     │  │ • Send via SMTP   │  │ • SPF/DKIM/DMARC    │  │
│  │ • Fresh Only      │  │ • Open/click track│  │ • Inbox placement    │  │
│  │ • Bounce history  │  │ • Reply detection │  │ • Warmup advisor     │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────┘  │
│                                                                       │
│  ┌─────────────────┐  ┌─────────────────┐  ┌─────────────────────┐  │
│  │  INTEGRATIONS    │  │  AGENCY SUITE    │  │   DATA NETWORK      │  │
│  │  (New — Phase 2) │  │  (New — Phase 3) │  │   (Compound moat)   │  │
│  │                  │  │                  │  │                      │  │
│  │ • Native n8n node │  │ • Team workspaces │  │ • Niche benchmarks  │  │
│  │ • Make module    │  │ • Client reporting│  │ • Timing intel       │  │
│  │ • Zapier action  │  │ • White-label API │  │ • List aging monitor │  │
│  │ • Webhook engine │  │ • Audit logs      │  │ • Public score API   │  │
│  │ • REST API       │  │ • Suppression mgr │  │ • Community signals  │  │
│  └─────────────────┘  └─────────────────┘  └─────────────────────┘  │
└─────────────────────────────────────────────────────────────────────┘
```

---

# SECTION 1 — TIER 1 FEATURES (Build After Launch)

---

## 1.1 Sending Domain Reputation Checker

**What it is:**
User enters their sending domain (e.g. `agency.io`). List Intel checks it across
50+ real-time blacklists, verifies SPF/DKIM/DMARC configuration, tests MX health,
and returns a "sender score" with specific remediation advice.

**Why it matters:**
Every cold emailer worries about whether their domain is blacklisted.
The current tools that do this (MXToolbox, mail-tester.com) are ugly, slow,
free-with-ads, and don't give actionable advice. List Intel already understands
deliverability — this is the same intelligence applied to the sender side.

**How it works:**

```
Input: agency.io

Checks performed:
1. DNS blacklist lookups (async, parallel across all RBLs):
   - Spamhaus ZEN (SBL, XBL, PBL, DBL)
   - Barracuda Reputation Block List (BRBL)
   - SORBS (DUHL, SMTP, Web, Spam)
   - SpamCop BL (SCBL)
   - URIBL (Black, Red, Grey, Multi)
   - Invaluement ivmSIP, ivmSIP24, ivmURI
   - MXToolbox SuperBlacklist (aggregated)
   - ...50 total RBLs

2. DNS record verification:
   - SPF: exists? valid? too many lookups (>10 = broken)?
   - DKIM: selector probe (check common selectors: default, google, mail, k1, k2)
   - DMARC: exists? policy (none/quarantine/reject)?
   - MX: active? resolves? responds to SMTP greeting?
   - PTR: reverse DNS set? matches forward DNS?

3. Recent sending history signals (from our bounce pool):
   - How many bounces have we seen from @agency.io addresses?
   - Are domains receiving from agency.io increasingly rejecting?

Output: Sender Score 0–100 + specific issues + fix instructions
```

**Implementation — pure DNS, no paid APIs:**
```python
# All 50+ RBL checks are DNS lookups, not API calls
# Pattern: reverse IP octets + RBL domain
# e.g. for IP 1.2.3.4 checking zen.spamhaus.org:
# lookup: 4.3.2.1.zen.spamhaus.org
# Listed = exists, Not listed = NXDOMAIN

async def check_rbl(ip: str, rbl: str) -> RBLResult:
    reversed_ip = ".".join(reversed(ip.split(".")))
    query = f"{reversed_ip}.{rbl}"
    try:
        await resolver.query(query, "A")
        return RBLResult(listed=True, rbl=rbl)
    except aiodns.error.DNSError:
        return RBLResult(listed=False, rbl=rbl)
```

**Revenue angle:**
Free tier: check 1 domain/day, top 10 RBLs only.
Paid: unlimited checks, all 50+ RBLs, full DKIM discovery, PDF report.
Agencies will pay $10+/mo just for this feature alone.

**Database:**
```sql
CREATE TABLE domain_reputation_checks (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    domain TEXT NOT NULL,
    sender_score INTEGER,        -- 0–100
    blacklists_hit INTEGER,
    spf_valid BOOLEAN,
    dkim_found BOOLEAN,
    dmarc_policy TEXT,
    full_results JSONB,
    checked_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## 1.2 Inbox Placement Predictor

**What it is:**
Before launching a campaign, user inputs: their sending domain + a sample email
template + the enriched recipient list. List Intel predicts inbox vs spam vs block
rates by combining sender reputation, recipient gateway detection, and template
analysis.

**Why it matters:**
Companies like GlockApps charge $50/mo just to test inbox placement.
Their approach: send seed emails to test inboxes. Our approach is different —
we predict based on structural signals we already have. No seed network needed.

**The prediction model:**

```
Inbox score = weighted combination of:

Sender factors (40% weight):
  + Sender score from domain reputation check
  + SPF/DKIM/DMARC alignment (each +/- points)
  + Domain age (older = safer)
  - RBL hits (heavy penalty)

Recipient factors (40% weight):
  - % of list behind Mimecast/Proofpoint/Barracuda
  - Average burn score of list
  - % of catch-all domains
  - % of role addresses

Content factors (20% weight):
  - Spam trigger word density (via Mistral 7B analysis)
  - Link count
  - HTML/text ratio
  - Subject line analysis (caps, punctuation, trigger words)

Output:
  Predicted inbox rate:   62%
  Predicted spam rate:    28%
  Predicted block rate:   10%

  "Your Mimecast coverage (34%) is your biggest risk. Consider
   segmenting those recipients to a dedicated warmed domain."
```

**Phase 1:** Rule-based scoring (no ML). Fast to build, explainable output.
**Phase 2:** Train a simple model on actual campaign outcomes users feed back.

---

## 1.3 List Deduplication + Multi-List Merge

**What it is:**
Upload 2–10 CSVs simultaneously. List Intel deduplicates by email hash,
shows cross-list overlap, and exports a clean merged master with provenance
(which original list each contact came from).

**Why it's valuable:**
Agencies receive lists from multiple sources — Apollo export, LinkedIn scrape,
purchased list, referral list. They have zero visibility into overlap.
Sending duplicates means burning contacts twice on the same campaign,
double-paying for enrichment credits, and wasting Instantly/Smartlead send quota.

**How it works:**
```python
# Multi-file upload — one job, multiple source files
POST /api/v1/jobs/merge
Content-Type: multipart/form-data

files: [file1.csv, file2.csv, file3.csv]
options: {
    "keep": "all" | "first" | "last",  # which version to keep on duplicate
    "enrich": true | false,             # run 8 layers on merged list
    "show_overlap": true
}

# Returns:
{
    "total_unique": 9840,
    "total_duplicates": 2104,
    "overlap_matrix": {
        "file1_file2": 840,   # emails in both file1 and file2
        "file1_file3": 210,
        "file2_file3": 1054,
        "all_three": 88
    },
    "merged_file_url": "...",
    "source_column": true  # merged CSV includes "source_file" column
}
```

**Output CSV includes:**
```
email, first_name, company, ..., source_file, appeared_in_n_lists, is_duplicate
john@company.com, John, Acme, ..., apollo_export.csv, 1, false
vp@corp.co, Sarah, Corp, ..., file1.csv|file2.csv, 2, true
```

**No new infrastructure.** Uses existing CSV parser, hashing utilities,
and job system. The merge step runs before the 8-layer pipeline.

---

## 1.4 List Health Score — Per Account Dashboard

**What it is:**
A persistent score (0–100) for each user's overall list quality,
computed from all their jobs. Visible on the dashboard. Emailed weekly.
Actionable: tells users specifically what to fix.

**Components:**
```
List Health Score = weighted average across all jobs in last 30 days:

  Burn score health:        jobs with avg burn < 30 score highest
  Spam filter exposure:     % of contacts behind aggressive gateways
  Domain risk distribution: % of contacts at VeryHigh/High risk domains
  Bounce rate trend:        improving, stable, or worsening
  List freshness:           how recently each list was re-checked

Score bands:
  90–100: Elite  — your lists are pristine
  70–89:  Good   — healthy with minor risks
  50–69:  Fair   — real exposure, needs attention
  30–49:  Poor   — significant burn, consider refreshing
  0–29:   Critical — your lists are hurting your sender reputation
```

**Weekly email digest:**
```
Subject: Your List Intel Health Report — Week of Mar 24

Your score this week: 67/100 (↓ 4 from last week)

What changed:
  • saas_leads_q1.csv: avg burn rose from 41 → 58 (18 new senders blasted it)
  • 847 contacts are now behind Mimecast — up from 612 last week

What to do:
  • Re-run saas_leads_q1.csv to get updated scores
  • Consider segmenting Mimecast contacts to a separate subdomain campaign
  • Trade your burned Ecom list in the Marketplace → 22,000 leads waiting

See full report →
```

---

## 1.5 Webhook Engine

**What it is:**
User configures a webhook URL per event type. List Intel fires POST requests
to that URL when events happen. Enables native n8n/Make/Zapier automations.

**Event types:**
```
job.complete        — enrichment job finished
job.failed          — job encountered an error
trade.matched       — marketplace listing matched
trade.confirmed     — both parties confirmed, trade executing
credits.low         — credits below threshold (configurable)
credits.zero        — out of credits
report.ready        — weekly health report generated
domain_check.done   — sending domain reputation check complete
```

**Webhook payload (always same envelope):**
```json
{
  "event": "job.complete",
  "timestamp": "2026-03-24T14:32:11Z",
  "account_id": "usr_abc123",
  "data": {
    "job_id": "job_xyz789",
    "filename": "saas_leads_q1.csv",
    "total_emails": 12400,
    "fresh_count": 8210,
    "burned_count": 3105,
    "download_url": "https://listintel.io/api/v1/jobs/xyz789/download?token=..."
  }
}
```

**Reliability — delivery guarantees:**
```python
# Celery task — retries with exponential backoff
@celery_app.task(max_retries=5, default_retry_delay=30)
async def fire_webhook(webhook_id: str, event: str, payload: dict):
    webhook = await get_webhook(webhook_id)
    try:
        response = await httpx.post(
            webhook.url,
            json=payload,
            headers={
                "X-ListIntel-Signature": sign_payload(payload, webhook.secret),
                "X-ListIntel-Event": event,
                "Content-Type": "application/json",
            },
            timeout=10.0
        )
        if response.status_code not in (200, 201, 202):
            raise WebhookDeliveryError(f"Endpoint returned {response.status_code}")
        await log_delivery_success(webhook_id, event)
    except Exception as e:
        await log_delivery_failure(webhook_id, event, str(e))
        raise self.retry(exc=e, countdown=30 * (2 ** self.request.retries))
```

**Security — HMAC signature verification:**
```
X-ListIntel-Signature: sha256=abc123...

Verify with:
  expected = hmac.new(webhook_secret, raw_body, sha256).hexdigest()
  trusted = hmac.compare_digest(f"sha256={expected}", signature_header)
```

Same pattern as Paystack webhooks — familiar to developers.

**Database:**
```sql
CREATE TABLE webhooks (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    url TEXT NOT NULL,
    secret TEXT NOT NULL,  -- HMAC signing secret (user-generated)
    events TEXT[],         -- which events trigger this webhook
    is_active BOOLEAN DEFAULT TRUE,
    last_fired_at TIMESTAMPTZ,
    failure_count INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE webhook_deliveries (
    id UUID PRIMARY KEY,
    webhook_id UUID REFERENCES webhooks(id),
    event TEXT,
    payload JSONB,
    status_code INTEGER,
    response_body TEXT,
    delivered_at TIMESTAMPTZ,
    error TEXT
);
```

---

# SECTION 2 — TIER 2 FEATURES (Differentiators)

---

## 2.1 List Aging Monitor

**What it is:**
User opts a completed job into monitoring. Every 30 days, List Intel
automatically re-scores the list in the background and notifies the user
if the burn score has significantly changed.

**Why nobody else has this:**
Every other tool is point-in-time. You verify today, you're flying blind next month.
List Intel's burn pool keeps growing — an email that was Fresh in January may be
Burned by April. This feature passively protects users without them doing anything.

**How it works:**
```python
# Celery beat — runs nightly, checks which monitored jobs are due for re-scoring
@celery_app.task(name="tasks.list_aging_monitor")
async def check_monitored_jobs():
    jobs_due = await get_jobs_due_for_rescore()  # monitored=True, last_checked > 30d ago

    for job in jobs_due:
        # Re-run burn score + bounce history ONLY (fast, no MX/DNS needed)
        # These are the only scores that change over time
        current_scores = await rescore_burn_and_bounce(job.id)
        previous_scores = job.summary

        delta = compute_delta(current_scores, previous_scores)

        if delta.burn_score_change > 10 or delta.burned_count_increase > 500:
            await create_notification(job.user_id, "list_aged", {
                "job_id": job.id,
                "filename": job.filename,
                "new_burned_count": current_scores.burned_count,
                "increase": delta.burned_count_increase,
                "burn_score_change": delta.burn_score_change,
            })
            await fire_webhook(job.user_id, "list.aged", delta)
```

**The key insight — only two layers need re-running:**
MX records, spam filter detection, infra, domain age, syntax — these don't change.
Only burn score and bounce history change over time. Re-scoring takes <5 seconds
per list regardless of size. The entire monthly monitoring run is cheap.

**Plan gating:**
Free: no monitoring (point-in-time only)
Starter+: monitor up to 3 active lists
Growth+: unlimited monitoring, configurable re-score frequency (30d/14d/7d)

---

## 2.2 Niche Burn Benchmarks

**What it is:**
When a user sees their list's average burn score, they also see how that compares
to all other lists in the same niche uploaded to the platform.

**The display:**
```
Your SaaS list average burn score: 43

Platform benchmark (B2B SaaS):
  ████████████████░░░░░░░░  Platform avg: 58
  ██████████████████████░░  Your score:   43  ← Better than 71% of SaaS lists

Niche distribution:
  Fresh (0–20):    28%  ██████████████
  Warm (21–50):    34%  █████████████████
  Burned (51–80):  26%  █████████████
  Torched (81+):   12%  ██████
```

**How benchmarks are computed:**
```python
# Runs daily via Celery beat — cached in Redis
async def compute_niche_benchmarks():
    niches = ["SaaS", "Ecommerce", "Finance", "Healthcare", "Real Estate", "Agency"]

    for niche in niches:
        # Jobs tagged with this niche from last 90 days
        avg_burn = await db.execute(
            select(func.avg(job_results.c.burn_score))
            .join(jobs, jobs.c.id == job_results.c.job_id)
            .where(
                jobs.c.niche == niche,
                jobs.c.completed_at > datetime.now() - timedelta(days=90)
            )
        )
        percentile_distribution = await compute_percentiles(niche)
        await redis.setex(
            f"benchmark:{niche}",
            86400,  # cache 24 hours
            json.dumps({"avg": avg_burn, "distribution": percentile_distribution})
        )
```

**Zero new infrastructure.** Purely derived from existing `job_results` and
`jobs` tables. The only addition: a `niche` field on jobs (user tags their upload).

---

## 2.3 Suppression List Manager

**What it is:**
User uploads their permanent suppression list — all-time unsubscribes, hard bounces,
DNC contacts, competitors, investors to never email. List Intel hashes and stores them.
Every future job output automatically has suppressed contacts removed before download.

**Why it's critical:**
GDPR Article 17 — right to erasure. CASL opt-out requirements. CAN-SPAM unsubscribe
compliance. Agencies maintain suppression lists manually in Excel and apply them
manually to every campaign. One missed step = GDPR fine. This automates it permanently.

**How it works:**
```python
# Upload endpoint
POST /api/v1/suppression/upload
# Accepts CSV of emails — stores only hashes, zero plaintext

# On every job download (Fresh Only or full):
async def apply_suppression(
    user_id: str,
    rows: list[JobResult],
    db: AsyncSession,
) -> list[JobResult]:
    # Get all suppressed hashes for this user
    suppressed = await get_suppressed_hashes(db, user_id)

    # Filter in one pass
    return [
        row for row in rows
        if row.email_hash not in suppressed
    ]
```

**Database:**
```sql
CREATE TABLE suppression_list (
    id BIGSERIAL PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    email_hash VARCHAR(64) NOT NULL,
    reason TEXT,        -- unsubscribe/bounce/dnc/manual
    added_at TIMESTAMPTZ DEFAULT NOW(),
    UNIQUE(user_id, email_hash)
);

CREATE INDEX idx_suppression_user_hash ON suppression_list(user_id, email_hash);
```

**GDPR design:**
Zero plaintext emails stored. If a data subject requests erasure, their email
is already not stored — only its hash. The suppression remains active
(the hash still blocks future sends) but there's nothing to "delete" in terms
of PII.

**Plan gating:**
Free: up to 1,000 suppressed contacts
Starter: 10,000
Growth+: Unlimited

---

## 2.4 Campaign Timing Intelligence

**What it is:**
Derived from upload patterns across the platform — surfaces when your niche
is most competitive (most other senders uploading similar lists) so you can
time campaigns to avoid peak saturation.

**The insight:**
When many cold emailers are uploading B2B SaaS lists on Tuesday, it means
Tuesday is a popular campaign launch day for that niche. The inboxes are
receiving the most cold email on Thursday (2 days after upload/prep).
Launching on Wednesday or Friday beats the crowd.

**Display on job detail page:**
```
Campaign Timing for B2B SaaS lists this week:

Monday:     ░░░░░░░░░░░░░░░░░░░░  Low competition
Tuesday:    █████████████████░░░  High — 34 similar uploads today
Wednesday:  ████████░░░░░░░░░░░░  Medium
Thursday:   ██████████████████░░  Very High — peak competition day
Friday:     ███░░░░░░░░░░░░░░░░░  Low
Saturday:   ░░░░░░░░░░░░░░░░░░░░  Very Low
Sunday:     ░░░░░░░░░░░░░░░░░░░░  Very Low

Recommendation: Launch Monday or Friday for lowest inbox competition.
```

---

# SECTION 3 — n8n / MAKE / ZAPIER NATIVE INTEGRATION

This is not just a webhook. This is first-class workflow automation support.

---

## 3.1 n8n Native Node

**What it is:**
A custom n8n community node (`n8n-nodes-listintel`) that users install in their
n8n instance. Provides native drag-and-drop nodes for all List Intel operations.

**Why this matters:**
The cold email community uses n8n heavily for automation. Native nodes feel
official, are discoverable in the n8n marketplace, and work better than generic
webhook nodes. Users on n8n forums sharing their automations = free distribution.

**Node operations:**

```typescript
// n8n-nodes-listintel/nodes/ListIntel/ListIntel.node.ts

operations: [
  {
    name: "Check Email",
    value: "checkEmail",
    description: "Run all 8 layers on a single email address",
    // Input: email (string)
    // Output: full enrichment result
  },
  {
    name: "Upload List",
    value: "uploadList",
    description: "Upload a CSV for async bulk enrichment",
    // Input: CSV file or array of emails
    // Output: job_id for polling
  },
  {
    name: "Get Job Result",
    value: "getJobResult",
    description: "Poll a job and return results when complete",
    // Input: job_id
    // Output: enriched rows array
  },
  {
    name: "Get Burn Score",
    value: "getBurnScore",
    description: "Get burn score for an email address",
    // Input: email
    // Output: score, tag, times_seen
  },
  {
    name: "Check Sending Domain",
    value: "checkDomain",
    description: "Check sender domain reputation and blacklists",
    // Input: domain
    // Output: sender_score, issues, blacklists
  },
  {
    name: "Submit Bounces",
    value: "submitBounces",
    description: "Submit bounce data to improve the platform",
    // Input: array of {email, bounce_type}
    // Output: submitted count
  },
  {
    name: "Get Niche Benchmark",
    value: "getNicheBenchmark",
    description: "Compare a burn score against niche average",
    // Input: score, niche
    // Output: percentile, comparison
  }
]
```

**Example n8n workflow — full automation:**
```
[Trigger: New lead in HubSpot CRM]
    ↓
[ListIntel: Check Email]
    ↓
[IF: burn_score > 50]
  → [HubSpot: Tag contact "high-burn"]
  → [Slack: Alert "Burned lead added: {email}"]
[ELSE]
  → [Instantly: Add to campaign "fresh-leads-sequence"]
```

**Example workflow — post-campaign bounce submission:**
```
[Trigger: Campaign ended in Instantly]
    ↓
[HTTP: Get bounce report from Instantly API]
    ↓
[ListIntel: Submit Bounces]
    ↓
[ListIntel: Re-check burn scores on sent list]
    ↓
[Google Sheets: Update list health tracker]
```

**Publishing:**
1. Build as TypeScript n8n community node
2. Publish to npm as `n8n-nodes-listintel`
3. Submit to n8n Community Nodes marketplace
4. Write a tutorial: "How to automate cold email list verification with n8n + List Intel"
5. Post in n8n Discord + cold email subreddit

**Node implementation notes:**
The n8n node calls List Intel's existing REST API (`/api/v1/check`, `/api/v1/bulk`, etc.).
No new backend endpoints needed — the node is pure frontend/TypeScript.
Long-running operations (bulk jobs) use n8n's built-in polling mechanism.

---

## 3.2 Make (Integromat) Module

Same operations as n8n, built as a Make custom app.
Make has a formal App Partner Program — List Intel can apply once it has
500+ users for a verified badge.

**Trigger modules (Make-specific):**
- "Watch for completed jobs" (polling trigger every N minutes)
- "Watch for trade matches" (polling trigger)
- "Watch for low credits" (polling trigger)

**Action modules:**
- Check email (single)
- Upload and enrich list (async + polling)
- Get burn score
- Check sending domain
- Submit bounce data

---

## 3.3 Zapier Integration

**Published Zapier App:** Requires Zapier partner application (~500 users threshold)

**Triggers:**
- Job completed
- Credits below threshold
- Trade matched

**Actions:**
- Check single email
- Get burn score for email
- Submit bounce event

**Searches:**
- Find job by filename
- Get job results by job_id

---

## 3.4 Self-Hosted n8n via List Intel

**What it is:**
List Intel offers a managed n8n instance as part of Agency plan.
Users get an n8n workspace pre-configured with the List Intel node,
plus templates for common cold email automations.

**Why:**
Agencies don't want to manage their own n8n servers. List Intel already has
Railway infrastructure. Running a managed n8n for Agency users costs
~$15/mo on Railway (one Docker container). Charges $49/mo extra.
Margin: $34/mo per Agency user for essentially zero maintenance.

**Pre-built templates included:**
- "Instantly → List Intel → Instantly" (auto-verify before adding to campaign)
- "Bounce submission loop" (send campaign → submit bounces → re-verify)
- "List aging alert" (weekly re-check + Slack notification)
- "Domain health monitor" (daily sender domain check)

---

# SECTION 4 — OUTREACH AUTOMATION LAYER

The biggest expansion. List Intel becomes the place you not only prepare
your list but also send from.

**The positioning:**
Not replacing Instantly/Smartlead. Being the intelligence layer that sits
underneath them — and optionally handling sending for users who don't want
to pay for both tools.

---

## 4.1 SMTP Connection Manager

**What it is:**
Users connect their sending email accounts (Gmail, Outlook, custom SMTP)
to List Intel. The platform manages multiple sending accounts, rotates
between them, and monitors per-account send health.

**Why it matters:**
Cold emailers run 3–10 sending accounts per campaign. Managing them
separately across Instantly/Smartlead + Google Workspace + Outlook is
a constant operational headache. List Intel already understands their
recipient infrastructure — knowing the sender infrastructure too
unlocks the full deliverability picture.

**How SMTP connections work:**
```python
# User adds a sending account
POST /api/v1/sending-accounts
{
    "type": "gmail" | "outlook" | "custom_smtp",
    "email": "john@agency.io",
    "smtp_host": "smtp.gmail.com",   # for custom SMTP
    "smtp_port": 587,
    "smtp_user": "john@agency.io",
    "smtp_password": "app-password",  # encrypted at rest with Fernet
    "daily_send_limit": 150           # user-configured
}

# SMTP credentials encrypted before storage:
from cryptography.fernet import Fernet
encrypted_password = fernet.encrypt(smtp_password.encode())
```

**Account health monitoring:**
```
Per sending account, track:
  - Daily sends (vs limit)
  - Bounce rate (last 7 days)
  - Reply rate
  - Spam complaint rate (via SMTP error codes)
  - Days since last warmup activity

Health score: 0–100 per account
Warning thresholds:
  > 5% bounce rate → orange warning
  > 10% bounce rate → red — pause account
  > 0.3% spam complaint → immediate pause + alert
```

---

## 4.2 Campaign Builder

**What it is:**
Full sequence-based outreach campaign builder inside List Intel.
Create a campaign, attach an enriched list, write sequences,
send via connected SMTP accounts.

**The workflow — end-to-end inside List Intel:**
```
1. Upload list → enrich (8 layers) → applies Fresh Only preset
2. Create campaign → attach enriched list
3. Write email sequence (up to 5 steps, configurable delays)
4. Configure sending: which accounts, daily limit, timezone
5. Launch → List Intel schedules and sends via connected SMTP
6. Track opens, clicks, replies in real-time
7. Bounces automatically submitted back to burn pool
8. Re-score list after campaign — burn scores updated
```

**Sequence editor:**
```
Step 1 — Day 0
  Subject: {{first_name}}, quick question about {{company}}
  Body: [Rich text editor with merge tags]
  Send time: 9–11am recipient's timezone (inferred from domain/infra)

  Wait: 3 days — if no reply

Step 2 — Day 3
  Subject: Re: (continuing thread)
  Body: [Follow-up template]

  Wait: 5 days — if no reply

Step 3 — Day 8
  Subject: Last note, {{first_name}}
  Body: [Breakup email template]

  Stop: on reply / unsubscribe / bounce
```

**Merge tags available:**
`{{first_name}}`, `{{last_name}}`, `{{company}}`, `{{domain}}`,
`{{email_infra}}` (personalise by GWS vs M365),
`{{burn_tag}}` (internal — not for email body),
any column from original CSV.

**Conditional sending based on enrichment:**
```
IF email_infra == "GWS"   → use template_gws
IF email_infra == "M365"  → use template_m365
IF spam_filter == "Mimecast" → skip (or use dedicated domain)
IF burn_score > 50 → skip
```

This is the unique angle: no other sending tool knows the recipient's
infrastructure. List Intel can personalise at a level no other tool can.

---

## 4.3 Open & Click Tracking

**What it is:**
Invisible tracking pixels and redirect links embedded in outbound emails.
Tracks who opens, who clicks, and when — feeding back into campaign analytics.

**How tracking pixels work:**
```python
# On send — replace all links in email body with tracked redirects
# Replace: href="https://original.com/page"
# With:    href="https://t.listintel.io/r/{tracking_id}"

# Tracking pixel (1x1 transparent GIF):
# <img src="https://t.listintel.io/p/{pixel_id}" width="1" height="1">

# Tracking subdomain served by FastAPI:
@app.get("/p/{pixel_id}")
async def track_open(pixel_id: str, request: Request):
    await record_open(pixel_id, request.headers.get("user-agent"))
    return Response(content=PIXEL_GIF, media_type="image/gif")

@app.get("/r/{tracking_id}")
async def track_click(tracking_id: str):
    link = await get_tracked_link(tracking_id)
    await record_click(tracking_id)
    return RedirectResponse(link.original_url)
```

**Unsubscribe handling (required for CAN-SPAM):**
```python
# Footer of every email includes:
# <a href="https://t.listintel.io/u/{unsub_id}">Unsubscribe</a>

@app.get("/u/{unsub_id}")
async def handle_unsubscribe(unsub_id: str):
    contact = await get_contact_by_unsub_id(unsub_id)
    # Auto-add to user's suppression list
    await add_to_suppression(contact.user_id, contact.email_hash, reason="unsubscribe")
    return HTMLResponse("<html><body>You've been unsubscribed.</body></html>")
```

---

## 4.4 Reply Detection

**What it is:**
List Intel connects to the sending email account's inbox (IMAP) and
detects replies to tracked campaigns. Automatically stops follow-up
sequences when a reply is received.

```python
# IMAP polling (runs every 5 minutes via Celery beat)
@celery_app.task(name="tasks.check_replies")
async def check_replies():
    for account in await get_active_sending_accounts():
        async with IMAPClient(account) as imap:
            unread = await imap.get_unread_in_sent_thread()
            for message in unread:
                if is_reply_to_campaign(message):
                    await handle_campaign_reply(message)
                    # Mark sequence as "replied" — stop follow-ups
                    # Create notification for user
                    # Log in campaign analytics
```

**Reply classification:**
- Positive reply (interest expressed)
- Out of office (pause sequence, retry after return date)
- Not interested (mark as lost, add to suppression if requested)
- Bounce notification (capture as bounce, submit to pool)
- Unsubscribe request (auto-process via suppression manager)

---

## 4.5 Campaign Analytics Dashboard

**What it is:**
Full campaign performance analytics — all metrics in one view,
connected back to list intelligence signals.

**The unique insight only List Intel can provide:**
Standard analytics tools show you open rates and reply rates.
List Intel shows you open rate *by recipient infrastructure* and
reply rate *by burn score bracket* — connecting sending performance
back to the intelligence data.

```
Campaign: SaaS Outreach Q1 2026
Sent: 7,420 (Fresh Only filtered from 12,400)
Period: Mar 1 – Mar 15, 2026

Overall performance:
  Open rate:    42.1%   (industry avg: 31%)
  Click rate:    8.4%   (industry avg: 4%)
  Reply rate:    4.2%   (industry avg: 2%)
  Bounce rate:   1.1%   (warning threshold: 5%)

Performance by infrastructure:
  GWS recipients:     Open 48%, Reply 5.1%  ← highest
  M365 recipients:    Open 38%, Reply 3.8%
  Custom SMTP:        Open 31%, Reply 2.9%  ← lowest

Performance by burn score at send time:
  Burn 0–20 (Fresh):     Open 51%, Reply 5.8%  ← highest
  Burn 21–50 (Warm):     Open 39%, Reply 3.9%
  Burn 51–80 (Burned):   Open 22%, Reply 1.2%  ← should have excluded
  — (you had Fresh Only set to exclude >50, so no Torched contacts)

Insight: Your GWS + Fresh contacts are 2.3x more likely to reply
than your M365 + Warm contacts. Segment these next campaign.
```

This insight is only possible because List Intel has both the
enrichment data and the send/track data. No other tool can produce this.

---

## 4.6 Sending Account Warmup Advisor

**What it is:**
For new sending domains, List Intel tracks warmup progress and
advises on safe send volumes.

**Warmup schedule display:**
```
account: outreach@agency.io (added 14 days ago)

Week 1 target: 20/day   ████████████████████ 140 sent ✓
Week 2 target: 40/day   ████████████████░░░░ 200/280 sent (in progress)
Week 3 target: 80/day   ░░░░░░░░░░░░░░░░░░░░ not started
Week 4 target: 150/day  ░░░░░░░░░░░░░░░░░░░░ not started

Current health:
  Bounce rate: 0.8%   ✓ Good
  Spam rate:   0.0%   ✓ Perfect
  Open rate:   38%    ✓ Above average (signals positive engagement)

Recommendation: Safe to increase to 60/day this week.
  Note: Avoid sending to Mimecast addresses until week 4.
```

---

# SECTION 5 — AGENCY SUITE

---

## 5.1 Team Workspaces

**Database additions:**
```sql
CREATE TABLE workspaces (
    id UUID PRIMARY KEY,
    name TEXT NOT NULL,
    owner_id UUID REFERENCES users(id),
    plan TEXT,  -- workspace-level plan (overrides member plans)
    created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE workspace_members (
    id UUID PRIMARY KEY,
    workspace_id UUID REFERENCES workspaces(id),
    user_id UUID REFERENCES users(id),
    role TEXT CHECK (role IN ('owner', 'admin', 'analyst', 'viewer')),
    invited_at TIMESTAMPTZ,
    joined_at TIMESTAMPTZ
);
```

**Permission matrix:**
| Action | Owner | Admin | Analyst | Viewer |
|---|---|---|---|---|
| Run jobs | ✓ | ✓ | ✓ | ✗ |
| View all jobs | ✓ | ✓ | ✓ | ✓ |
| Download exports | ✓ | ✓ | ✓ | ✗ |
| Manage suppression | ✓ | ✓ | ✗ | ✗ |
| Manage webhooks | ✓ | ✓ | ✗ | ✗ |
| Manage billing | ✓ | ✗ | ✗ | ✗ |
| Invite members | ✓ | ✓ | ✗ | ✗ |
| Delete workspace | ✓ | ✗ | ✗ | ✗ |

**Shared pool contribution:**
All workspace members' uploads contribute to the same burn pool quota.
A workspace on Growth (100k credits/mo) shares credits across all analysts.
The workspace admin sees who used how many credits.

---

## 5.2 Client Reporting — Branded PDFs

**What it is:**
One-click PDF report generation for a completed job.
Agency-branded with their logo and colours. Delivered to their client
as a professional deliverable — "here's what we found on your list."

**Report contents:**
```
[Agency Logo]

List Intelligence Report
Prepared by: Growth Agency Co.
For: Acme Corporation
Date: March 24, 2026

━━━━━━━━━━━━━━━━━━━━━━━━━━━

EXECUTIVE SUMMARY
List analysed: uk_leads_q1.csv
Total contacts: 12,400

List Health Score: 67/100 (Good)

━━━━━━━━━━━━━━━━━━━━━━━━━━━

KEY FINDINGS

  8,210 contacts are Fresh and safe to email
  3,105 contacts show signs of over-saturation
    847 contacts are protected by Mimecast
    614 contacts are at very high domain risk

━━━━━━━━━━━━━━━━━━━━━━━━━━━

SPAM FILTER EXPOSURE
  Mimecast:     847  (6.8%)
  Proofpoint:   312  (2.5%)
  Barracuda:    198  (1.6%)
  No gateway: 11,043 (89.1%) ✓

INFRASTRUCTURE DISTRIBUTION
  Google Workspace: 5,840  (47.1%)
  Microsoft 365:    4,200  (33.9%)
  Custom SMTP:      2,360  (19.0%)

━━━━━━━━━━━━━━━━━━━━━━━━━━━

RECOMMENDED ACTION
Download the Fresh Only export (7,420 contacts) using the
preset configured for your campaign to maximise inbox placement.

Powered by List Intel · listintel.io
```

**Implementation:**
```python
# reportlab or weasyprint for PDF generation
# Agency branding stored in workspace settings:
# - logo URL
# - primary colour (hex)
# - company name
# - footer text
```

---

## 5.3 Audit Log

**What it is:**
Every significant action recorded in an immutable, append-only events table.
Enterprises need this for compliance. Agencies need it to bill clients
per-contact-processed.

**Events logged:**
```
job.created        job.started      job.completed     job.failed
job.downloaded     job.deleted
credits.deducted   credits.added    plan.upgraded      plan.downgraded
api_key.created    api_key.revoked  api_key.used
webhook.fired      webhook.failed
trade.submitted    trade.matched    trade.confirmed    trade.completed
member.invited     member.joined    member.removed
suppression.added  suppression.uploaded
report.generated   report.downloaded
```

**Database:**
```sql
CREATE TABLE audit_events (
    id BIGSERIAL PRIMARY KEY,
    workspace_id UUID,
    user_id UUID,
    event_type TEXT NOT NULL,
    resource_type TEXT,    -- "job", "api_key", "trade", etc.
    resource_id TEXT,
    metadata JSONB,
    ip_address INET,
    user_agent TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Append-only: no UPDATE or DELETE ever runs on this table
-- Retention: 2 years (Celery beat job purges records > 2yr old)
CREATE INDEX idx_audit_workspace ON audit_events(workspace_id, created_at DESC);
CREATE INDEX idx_audit_user ON audit_events(user_id, created_at DESC);
```

---

# SECTION 6 — DATA NETWORK FEATURES (Compound Moats)

---

## 6.1 Public Burn Score API (Free, Rate-Limited)

**What it is:**
A no-auth public endpoint that returns a burn score for any email address.
Rate-limited to 10 requests/hour per IP. Zero account needed.

```
GET https://api.listintel.io/v1/public/score?email=john@company.com

Response:
{
  "email_hash": "a3f8c91e...",
  "burn_score": 43,
  "burn_tag": "Warm",
  "times_seen": 43,
  "last_seen_bucket": "2026-Q1",  // privacy: quarter, not exact date
  "upgrade_url": "https://listintel.io/api-keys"
}
```

**Why this drives growth:**
1. Developer adds it to their n8n workflow → shares with community → 50 more signups
2. Blog post: "Check if your cold email list is burned for free" → 2,000 inbound links
3. Stack Overflow answer: "How to check email list quality" includes this → permanent SEO
4. Every response includes the upgrade CTA in the JSON

**Rate limiting:**
```python
# IP-based, 10/hour free
# API key: 100/hour on free plan, unlimited on Pro+
# The public endpoint is the top-of-funnel hook
```

---

## 6.2 Community Spam Filter Reports

**What it is:**
When a user's campaign bounces or gets flagged by a gateway that List Intel
didn't detect, they can submit a report: "I sent to xyz.com, it was blocked by
Mimecast, but your tool showed no gateway."

**Submission flow:**
```
POST /api/v1/community/report
{
    "domain": "xyz.com",
    "gateway_detected": "Mimecast",
    "evidence": "SMTP rejection message: 550 Blocked by Mimecast security",
    "job_id": "optional — for context"
}
```

**Review queue:**
Submissions go into a moderation queue. List Intel reviews (or eventually
auto-approves high-confidence reports from trusted users). Approved reports
update `spam_filters.json` with the new MX pattern.

**Incentive:**
Submitting an approved report earns 100 credits. Turns accuracy improvements
into user behaviour.

---

## 6.3 Bounce Pool Incentive Program

**What it is:**
Credits awarded for contributing bounce data to the pool.

**Reward structure:**
```
100 bounces submitted:    50 credits
1,000 bounces submitted:  500 credits
5,000 bounces submitted:  2,500 credits + "Data Contributor" badge
10,000+ per month:        Considered for "Data Partner" status
                          (custom arrangement for large agencies)
```

**Anti-gaming:**
```python
def validate_bounce_submission(rows: list[dict]) -> ValidationResult:
    # Reject if:
    # - More than 50% of submitted emails have never appeared in any job
    #   (fabricated bounces from nowhere = gaming attempt)
    # - Same email hash submitted >3 times by same user in 30 days
    # - Bounce rate > 95% (statistically implausible for real campaigns)
    # - All submitted domains are the same (suspicious pattern)
    ...
```

---

# SECTION 7 — FULL FEATURE × PHASE ROADMAP

```
PHASE 1 — Launch (NOW)
────────────────────────────────────────────────────
  ✓ 8-layer enrichment pipeline
  ✓ Burn score network
  ✓ Fresh Only export
  ✓ Burned list marketplace
  ✓ REST API + key management
  ✓ Full dashboard

PHASE 2 — After 200 users / $1k MRR (Month 2–3)
────────────────────────────────────────────────────
  → Sending Domain Reputation Checker
  → Webhook Engine
  → List Deduplication + Merge
  → Suppression List Manager
  → n8n Community Node (publish to npm)
  → Public Burn Score API
  → SMTP Connection Manager (accounts only — no sending yet)

PHASE 3 — After 500 users / $3k MRR (Month 4–6)
────────────────────────────────────────────────────
  → List Aging Monitor
  → Niche Burn Benchmarks
  → Deliverability Score dashboard widget
  → List Health Weekly Email Digest
  → Team Workspaces
  → Community Spam Filter Reports
  → Bounce Pool Incentive Program
  → Campaign Timing Intelligence
  → Make.com Module
  → Zapier Integration (apply for partner status)

PHASE 4 — After $5k MRR (Month 6–9)
────────────────────────────────────────────────────
  → Campaign Builder (sequences, sending)
  → Open & Click Tracking
  → Reply Detection (IMAP polling)
  → Campaign Analytics with infra breakdown
  → Client Reporting (branded PDFs)
  → Inbox Placement Predictor
  → Sending Account Warmup Advisor
  → Audit Log
  → White-Label API (first OmniVerifier partnership)

PHASE 5 — After $15k MRR (Month 9–12)
────────────────────────────────────────────────────
  → List Source (Tool 2 — find and build lists)
  → Self-hosted n8n workspace for Agency plan
  → Managed warmup service
  → Advanced ML inbox placement model
  → Enterprise SSO / SAML
  → Dedicated IP infrastructure for Pro+ senders
```

---

# SECTION 8 — REVISED PRICING WITH NEW FEATURES

Current pricing was designed for intelligence only.
With outreach automation, the value (and pricing) scales:

```
Free          $0/mo     500 credits · intelligence only · no campaigns
Starter       $10/mo    25k credits · intelligence · 1 campaign · webhooks
Growth        $49/mo    100k credits · intelligence · 5 campaigns · team (3)
              + suppression manager · list aging monitor · benchmarks
Pro           $99/mo    500k credits · intelligence · unlimited campaigns
              + API access · client reporting · audit log · team (10)
Agency        $249/mo   Unlimited credits · everything
              + white-label API · managed n8n · priority support · team (unlimited)
```

**Campaign add-on (for Starter+):**
Additional campaign slots: $5/mo each
Makes the campaign feature a natural upgrade path without forcing a full plan jump.

---

# SECTION 9 — THE PLATFORM NARRATIVE

At $10k MRR, the pitch changes from:
> "Upload your CSV and get burn scores"

To:
> "The intelligence layer for every cold email workflow.
>  Verify your list. Send your campaign. Track what works.
>  All connected. All in one place."

And the moat is triple-locked:
1. **Burn pool** — can't be replicated without the user base
2. **Send + track data** — creates a feedback loop competitors don't have
3. **Integrations** — the n8n node + webhooks make List Intel
   a permanent fixture in users' workflows, not a tab they open occasionally

Nobody in the cold email space owns the full loop from
**list quality → send → track → improve**.
Instantly/Smartlead own send and track.
Apollo/Clay own list building.
MillionVerifier/NeverBounce own basic verification.

List Intel owns the intelligence layer — and by adding outreach,
it owns the loop.
