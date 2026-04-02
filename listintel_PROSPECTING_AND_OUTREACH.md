---
name: listintel-prospecting-outreach
description: >
  Complete specification for List Intel's two new pillars:
  (1) List Source — automated lead prospecting engine that finds, scrapes,
  enriches, and scores leads from the web with zero manual work.
  (2) Outreach Engine — end-to-end campaign automation with AI personalisation,
  multi-channel sequences, smart follow-up, real-time tracking, reply handling,
  and continuous refinement loops.
  Read this before building any feature in either pillar.
  This is the spec that transforms List Intel from a list tool into a
  full cold outreach operating system.
---

# List Intel — Prospecting Engine + Outreach Automation

---

## The New Product Architecture

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                        LIST INTEL — FULL PLATFORM                             │
│                                                                                │
│  PILLAR 1          PILLAR 2              PILLAR 3          PILLAR 4           │
│  ─────────────     ─────────────────     ──────────────    ─────────────────  │
│  LIST INTEL        LIST SOURCE           OUTREACH ENGINE   INTELLIGENCE HUB   │
│  (Built ✓)         (New — This doc)      (New — This doc)  (Built + expanding)│
│                                                                                │
│  Enrich lists      Find leads            Send campaigns     Burn scores        │
│  you already       from scratch          reply-detect       Domain health      │
│  have              using the web         track everything   Benchmarks         │
│                                                                                │
│  Upload CSV   →    Define ICP       →    Sequence →         Analytics loop    │
│  8 layers         Scrape + score        Track + reply       feeds back into    │
│  Burn scores       Auto-enrich           Follow up          future searches    │
│  Fresh Only        Dedupe                Refine             and sequences      │
└──────────────────────────────────────────────────────────────────────────────┘

The full loop:
  Define who you want → Find them → Verify + score them → Email them →
  Track responses → Feed results back → Find better leads → Repeat
```

Everything in one account. One credit system. One data layer.

---

# PILLAR 2 — LIST SOURCE (Prospecting Engine)

## What It Is

A "Jobs" tab on the dashboard where users define their Ideal Customer Profile (ICP)
and List Intel automatically searches the web, scrapes prospect data, extracts
contact information, enriches it through the 8-layer pipeline, scores it,
and delivers a ready-to-send list — with zero manual work.

**The user experience:**
```
"Find me 500 B2B SaaS founders in the UK with 10–50 employees
 who use HubSpot and have raised Series A funding."

→ [Start Prospecting Job]

List Intel:
  Searches LinkedIn, Apollo data, company databases, news sources
  Finds 847 matching profiles
  Extracts emails via multiple discovery methods
  Runs all 8 intelligence layers on every email
  Scores and ranks by likelihood to convert
  Delivers: 623 verified, fresh, scored leads

→ [One-click: Launch outreach campaign]
```

---

## 2.1 Prospecting Job Interface

### New Tab: "Prospects" (alongside existing "Jobs")

```
Dashboard
├── Jobs          ← existing (enrichment jobs)
├── Prospects     ← new (prospecting/scraping jobs)
├── Campaigns     ← new (outreach engine)
├── Marketplace
└── ...
```

### ICP Builder — The Search Form

```
┌─────────────────────────────────────────────────────────┐
│  New Prospecting Job                                      │
│                                                           │
│  Job type: ○ Company-based  ● Contact-based  ○ Domain   │
│                                                           │
│  COMPANY FILTERS                                          │
│  Industry:    [B2B SaaS ▼] [+Add]                        │
│  Company size: [10] to [200] employees                    │
│  Location:    [United Kingdom ▼] [Nigeria ▼] [+Add]      │
│  Revenue:     [$1M ▼] to [$50M ▼]                        │
│  Founded:     [2018 ▼] to [2024 ▼]                       │
│  Tech stack:  [HubSpot] [Salesforce] [Intercom] [+Add]   │
│  Funding:     [Seed ▼] [Series A ▼] [+Add]               │
│  Keywords:    [cold email] [sales automation] [+Add]     │
│                                                           │
│  CONTACT FILTERS                                          │
│  Job title:   [Founder] [CEO] [Head of Sales] [+Add]     │
│  Seniority:   [C-Suite ▼] [VP ▼] [Director ▼]            │
│  Department:  [Sales ▼] [Marketing ▼]                    │
│                                                           │
│  QUALITY FILTERS (auto-applied)                           │
│  ✓ Only emails that pass syntax + MX validation           │
│  ✓ Exclude burn score > 40                                │
│  ✓ Exclude Mimecast + Barracuda by default                │
│  ✓ Exclude domains < 180 days old                         │
│                                                           │
│  Target count: [500] leads                                │
│  Est. credits: ~750 (1.5x for enrichment)                 │
│                                                           │
│  [Preview sources]  [Start job — 750 credits]            │
└─────────────────────────────────────────────────────────┘
```

---

## 2.2 Data Sources — The Scraping Stack

Multiple sources are queried in parallel. Each has different strengths.
No single source is relied on exclusively.

### Source 1: Apollo.io API (Primary)
Apollo has the best B2B contact database. Their API is available on
paid plans but also has a limited free tier.

```python
# app/features/prospects/sources/apollo.py

async def search_apollo(filters: ICPFilters, limit: int) -> list[RawProspect]:
    """
    Apollo People Search API.
    Returns contacts matching ICP filters.
    """
    payload = {
        "q_organization_industries": filters.industries,
        "q_organization_num_employees_ranges": [
            f"{filters.employee_min},{filters.employee_max}"
        ],
        "person_titles": filters.job_titles,
        "person_seniorities": filters.seniorities,
        "q_organization_locations": filters.locations,
        "contact_email_status": ["verified"],  # Apollo's own verification
        "per_page": min(limit, 100),
        "page": 1,
    }

    response = await httpx_client.post(
        "https://api.apollo.io/v1/mixed_people/search",
        headers={"X-Api-Key": settings.APOLLO_API_KEY},
        json=payload,
    )
    return parse_apollo_contacts(response.json())
```

**Cost:** Apollo API starts at $49/mo. List Intel uses its own key and
charges users credits that cover the API cost. At scale, negotiate wholesale.

### Source 2: LinkedIn via Scraping (Secondary)
LinkedIn doesn't have a public API for lead generation. Scraping requires
care — rotating proxies, rate limiting, human-like patterns.

```python
# app/features/prospects/sources/linkedin.py

async def search_linkedin(filters: ICPFilters, limit: int) -> list[RawProspect]:
    """
    LinkedIn People Search via headless browser or proxy service.

    Options (in order of preference):
    1. Proxycurl API — clean LinkedIn data via their scraping infra ($0.01/person)
    2. PhantomBuster — LinkedIn automation tool with API
    3. In-house scraping via Playwright + rotating proxies (highest risk)
    """
    if settings.PROXYCURL_API_KEY:
        return await _search_via_proxycurl(filters, limit)
    elif settings.PHANTOMBUSTER_API_KEY:
        return await _search_via_phantombuster(filters, limit)
    else:
        return []  # LinkedIn scraping disabled if no service configured
```

**Proxycurl cost:** ~$0.01 per profile = very low. For 500 leads, $5.
Build this into credit pricing.

### Source 3: Hunter.io (Email Discovery)
When we have a name + company but no email, Hunter finds the email.

```python
# app/features/prospects/sources/hunter.py

async def find_email(
    first_name: str,
    last_name: str,
    domain: str,
) -> EmailDiscoveryResult:
    """
    Hunter Email Finder API.
    Finds email address from name + company domain.
    Returns email + confidence score.
    """
    response = await httpx_client.get(
        "https://api.hunter.io/v2/email-finder",
        params={
            "first_name": first_name,
            "last_name": last_name,
            "domain": domain,
            "api_key": settings.HUNTER_API_KEY,
        }
    )
    data = response.json()
    return EmailDiscoveryResult(
        email=data["data"]["email"],
        confidence=data["data"]["score"],  # 0–100
        sources=data["data"]["sources"],
    )
```

**Hunter free tier:** 25 searches/mo. Paid from $49/mo.
Used as fallback when Apollo doesn't have an email.

### Source 4: Web Scraping — Company Websites
For domains we have but no contacts, scrape the company's About/Team page
and Contact page for email patterns and staff names.

```python
# app/features/prospects/sources/web_scraper.py

async def scrape_company_contacts(domain: str) -> list[RawContact]:
    """
    Crawls: /about, /team, /contact, /people pages
    Extracts: email addresses (regex), names (NLP), titles (heuristic)
    Infers: missing emails from name + domain pattern (john.smith@domain.com)
    """
    pages_to_try = [
        f"https://{domain}/about",
        f"https://{domain}/team",
        f"https://{domain}/contact",
        f"https://{domain}/people",
        f"https://{domain}/about-us",
        f"https://{domain}/our-team",
    ]

    for url in pages_to_try:
        try:
            html = await fetch_with_proxy(url)
            contacts = extract_contacts_from_html(html, domain)
            if contacts:
                return contacts
        except Exception:
            continue

    return []


EMAIL_PATTERN = re.compile(r'[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}')

def extract_contacts_from_html(html: str, domain: str) -> list[RawContact]:
    # Direct email extraction
    emails_found = EMAIL_PATTERN.findall(html)

    # Filter to only this domain's emails
    domain_emails = [e for e in emails_found if domain in e.lower()]

    # NLP name extraction (simple — no heavy model needed)
    names = extract_names_from_html(html)

    return build_contacts(domain_emails, names, domain)
```

### Source 5: Google News + Signals
Enrich with recent signals — funding rounds, product launches, hiring sprees,
tech stack changes — to identify "trigger events" that make a prospect
particularly relevant right now.

```python
# app/features/prospects/sources/signals.py

async def get_company_signals(company_name: str, domain: str) -> CompanySignals:
    """
    Searches for recent trigger events that indicate buying intent or relevance.
    Uses multiple free APIs and web search.
    """
    signals = []

    # Crunchbase funding data (free limited tier)
    funding = await check_crunchbase_funding(company_name)
    if funding and funding.date > datetime.now() - timedelta(days=90):
        signals.append(Signal(
            type="recent_funding",
            value=f"Raised {funding.amount} ({funding.round}) {funding.days_ago}d ago",
            score_boost=20,
        ))

    # Google News for company mentions
    news = await search_google_news(f'"{company_name}" site:techcrunch.com OR site:venturebeat.com')
    for article in news[:3]:
        signals.append(Signal(
            type="press_mention",
            value=article.title,
            url=article.url,
            score_boost=5,
        ))

    # Job postings = company is growing = good time to pitch
    jobs = await search_linkedin_jobs(company_name)
    if jobs.sales_open > 2:
        signals.append(Signal(
            type="hiring_sales",
            value=f"Currently hiring {jobs.sales_open} sales roles",
            score_boost=15,
        ))

    return CompanySignals(signals=signals, total_score_boost=sum(s.score_boost for s in signals))
```

### Source 6: BuiltWith / Wappalyzer — Tech Stack Detection
Identifies which companies use specific tech, enabling hyper-targeted outreach.
("Companies using Salesforce + HubSpot together = overinvested in CRM = ready for your pitch")

```python
async def detect_tech_stack(domain: str) -> TechStack:
    """
    Uses BuiltWith API or free Wappalyzer scraping to detect:
    - CRM: HubSpot, Salesforce, Pipedrive
    - Email: Instantly, Smartlead, Mailshake
    - Analytics: GA4, Mixpanel, Amplitude
    - Payment: Stripe, Paystack, Chargebee
    - Hosting: AWS, GCP, Vercel, Railway
    """
    ...
```

---

## 2.3 The Prospecting Job Lifecycle

```
State machine:

queued → sourcing → enriching → scoring → ready → archived
                    ↓
                  failed (partial results saved)

Detailed steps:

1. QUEUED
   Job created with ICP filters + target count
   Credits reserved (pre-flight check)
   Celery task pushed to queue

2. SOURCING (Celery worker)
   Apollo API queried → raw contacts
   LinkedIn/Proxycurl queried → raw contacts
   Web scraping for any domains without emails
   Hunter.io fills gaps (name+domain → email)
   Google News + BuiltWith for signals
   All results merged + deduplicated by email hash
   Typical: 2–5 minutes for 500 leads

3. ENRICHING
   All 8 intelligence layers run on every found email
   Same pipeline as manual upload — identical quality
   Typical: 30–60 seconds after sourcing completes

4. SCORING
   Each prospect gets a composite "prospect score" (0–100):
   - List Intel quality score (burn, domain age, infra): 40%
   - ICP match strength (how precisely they match filters): 30%
   - Signal score (recent funding, hiring, news): 20%
   - Email confidence (how certain we are the email is right): 10%

5. READY
   Results available in dashboard
   Sorted by prospect score descending
   User can: filter, preview, tag, export, launch campaign
   Credits deducted (only on completion)

6. ARCHIVED
   After 30 days, moved to archived
   Still downloadable, not auto-deleted
```

---

## 2.4 Prospect Score — The Full Formula

```python
def compute_prospect_score(prospect: RawProspect, enrichment: EnrichedRow) -> int:
    score = 0

    # ── Intelligence quality (40 points max) ──────────────────────────
    # Burn score (inverted — lower burn = better prospect)
    burn_quality = max(0, 40 - enrichment.burn_score) / 40 * 20
    score += burn_quality

    # No aggressive spam filter = easier to reach
    if enrichment.spam_filter is None:
        score += 8
    elif enrichment.spam_filter in ("Mimecast", "Barracuda"):
        score += 0   # hardest to reach
    else:
        score += 4

    # Domain age — older = more stable = better
    if enrichment.domain_risk == "Safe":
        score += 8
    elif enrichment.domain_risk == "Medium":
        score += 4
    elif enrichment.domain_risk in ("High", "VeryHigh"):
        score += 0

    # No bounce history
    score += max(0, 4 - enrichment.bounce_score)

    # ── ICP match (30 points max) ──────────────────────────────────────
    # Title match strength
    if prospect.title_match_score > 0.9:
        score += 15
    elif prospect.title_match_score > 0.7:
        score += 10
    elif prospect.title_match_score > 0.5:
        score += 5

    # Industry + size match
    if prospect.industry_match:
        score += 8
    if prospect.size_in_range:
        score += 7

    # ── Signal score (20 points max) ──────────────────────────────────
    score += min(20, prospect.signals.total_score_boost)

    # ── Email confidence (10 points max) ──────────────────────────────
    # From Hunter/Apollo confidence score
    score += int(prospect.email_confidence / 10)

    return min(100, int(score))
```

**Score bands:**
```
90–100: A-tier lead — verified, fresh, strong ICP match, recent signals
70–89:  B-tier — good quality, worth sequencing
50–69:  C-tier — borderline, maybe worth a shortened sequence
30–49:  D-tier — weak match or quality issues — skip or move to secondary campaign
0–29:   Skip — burn too high, wrong person, or low email confidence
```

---

## 2.5 Results View — The Prospects Table

```
Prospects: SaaS Founders UK (Q2 2026)
847 found · 623 scored A/B tier · 124 excluded by quality filters

[Filter: A-tier only] [Filter: No Mimecast] [Sort: Score ▼]
[Export to CSV] [Launch Campaign →]

┌──┬────────────────────────┬──────────────┬─────────┬──────┬────────┬────────────┬──────┐
│  │ Name                   │ Company      │ Title   │Score │ Burn   │ Infra      │Signals│
├──┼────────────────────────┼──────────────┼─────────┼──────┼────────┼────────────┼──────┤
│✓ │ Sarah Okonkwo          │ PayFlow Ltd  │ CEO     │  94  │ 4 Fresh│ GWS        │ 💰 🏢 │
│✓ │ James Whitfield        │ Leanstack    │ Founder │  91  │ 8 Fresh│ GWS        │ 📰    │
│✓ │ Marcus Reid            │ Trackably    │ CEO     │  87  │12 Fresh│ M365       │ 💰    │
│✓ │ Priya Sharma           │ Automator.io │ Founder │  84  │ 6 Fresh│ GWS        │       │
│  │ David Chen             │ Megacorp     │ VP Sales│  41  │72 Burnt│ Mimecast   │       │
└──┴────────────────────────┴──────────────┴─────────┴──────┴────────┴────────────┴──────┘

Signal legend:
💰 = Recent funding   🏢 = Hiring sales   📰 = Press mention   🔄 = Tech stack change
```

---

## 2.6 Credit Pricing for Prospecting Jobs

Prospecting jobs are more expensive than enrichment jobs because they consume
external API credits and more compute. Pricing is transparent:

```
1 enrichment credit   = verify + enrich 1 email you already have
1 prospecting credit  = find + verify + enrich 1 net new lead

Standard:    1.5x multiplier → 500 leads = 750 credits
Apollo data: 2x multiplier  → includes Apollo API cost
LinkedIn:    3x multiplier  → includes Proxycurl cost
Signals:     +0.5x          → adds news + funding data

Pre-flight estimate shown before job starts.
Credits reserved on start, deducted only on completion.
Failed finds don't cost credits.
```

---

# PILLAR 3 — OUTREACH ENGINE

## What It Is

A complete outreach automation system embedded in List Intel.
Users connect their email accounts, write or AI-generate sequences,
launch campaigns against enriched/prospected lists, and track every
interaction in real time — with the unique advantage that all actions
are informed by List Intel's intelligence data.

---

## 3.1 Email Account Management

### Connecting Accounts

```
Supported email providers:
  Gmail / Google Workspace → OAuth 2.0 (safest — no password stored)
  Microsoft 365 / Outlook  → OAuth 2.0
  Custom SMTP              → Encrypted SMTP credentials

Connection screen:
  [Connect Gmail] [Connect Outlook] [Add Custom SMTP]

Per-account configuration:
  Daily send limit: [50] (safe for new domains), up to [500]
  Sending hours:    [9:00 AM] to [5:00 PM]
  Timezone:         [GMT+1 ▼]
  Reply-to address: [optional override]
  Warmup mode:      [ON ▼] (gradually increases send volume)
```

### Gmail / Outlook OAuth Flow

```python
# app/features/outreach/accounts/gmail_oauth.py

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/gmail.readonly",  # for reply detection
]

async def initiate_gmail_oauth(user_id: str) -> str:
    """Returns OAuth URL for user to authorise Gmail access."""
    flow = google_auth_oauthlib.flow.Flow.from_client_config(
        settings.GOOGLE_OAUTH_CONFIG,
        scopes=GMAIL_SCOPES,
        redirect_uri=f"{settings.FRONTEND_URL}/outreach/accounts/callback/gmail"
    )
    auth_url, state = flow.authorization_url(
        access_type="offline",  # offline = get refresh token
        include_granted_scopes="true",
        state=user_id,
    )
    return auth_url

async def complete_gmail_oauth(code: str, user_id: str) -> SendingAccount:
    """Exchange code for tokens, store encrypted, return account."""
    flow = google_auth_oauthlib.flow.Flow.from_client_config(...)
    flow.fetch_token(code=code)

    credentials = flow.credentials
    # Encrypt tokens before storage
    encrypted_access = fernet.encrypt(credentials.token.encode())
    encrypted_refresh = fernet.encrypt(credentials.refresh_token.encode())

    account = SendingAccount(
        user_id=user_id,
        provider="gmail",
        email=get_email_from_token(credentials.token),
        encrypted_access_token=encrypted_access,
        encrypted_refresh_token=encrypted_refresh,
        token_expiry=credentials.expiry,
    )
    return account
```

### Per-Account Health Dashboard

```
account@agency.io (Gmail OAuth)

Health: ████████████████████ 84/100  Good

Today:    47/150 sent    ████████░░░░░░░░░░░░
This week: 312/750 sent

Performance (last 7 days):
  Bounce rate:  1.2%   ✓ Good  (threshold: 5%)
  Reply rate:   4.8%   ✓ Above average
  Spam rate:    0.0%   ✓ Perfect

Warmup status:
  Day 18 of warmup
  Current limit: 80/day
  Recommended: Increase to 100/day next week

⚠ Warning: 3 contacts marked "not interested" this week.
  Consider refreshing your email template.
```

---

## 3.2 AI-Powered Email Template Engine

### Template Builder

Three ways to create email templates:

**1. AI Generator — describe your offer, AI writes the sequence:**
```
Describe your offer: [  We help B2B SaaS companies reduce churn
                        through proactive customer success automation  ]

Target persona: [Founders and Head of Customer Success at B2B SaaS companies]

Tone: ○ Formal  ● Casual professional  ○ Very casual

Sequence length: [3 emails ▼]

Pain point to address: [  Manual customer success is breaking at scale.
                           Most teams are reactive, not proactive.        ]

[Generate sequence with AI →]
```

**2. Template Library — pre-built, battle-tested:**
```
Categories:
  Cold outreach starters (12 templates)
  Follow-up templates (8 templates)
  Breakup emails (5 templates)
  Meeting request templates (6 templates)
  Product demo request (4 templates)
  Partnership pitch (3 templates)
  Event/conference follow-up (4 templates)

Each template includes:
  - Subject line variants (A/B test built in)
  - Body with merge tag placeholders
  - Estimated open rate (from platform data)
  - Best performing niche (from platform data)
```

**3. Manual write — rich text editor with merge tags:**

---

### AI Template Generation — Full Implementation

```python
# app/features/outreach/templates/ai_generator.py

async def generate_sequence(
    offer_description: str,
    target_persona: str,
    tone: str,
    pain_point: str,
    sequence_length: int,
    niche: str,
) -> EmailSequence:

    system_prompt = """You are an expert cold email copywriter.
    You write high-converting B2B cold email sequences that feel personal,
    not spammy. You follow deliverability best practices:
    - Subject lines under 50 characters
    - No ALL CAPS
    - No spam trigger words
    - Personal, conversational tone
    - Clear single CTA
    - Short paragraphs (2–3 sentences max)
    - Always include a genuine reason to reach out

    Respond ONLY with valid JSON. No preamble or explanation."""

    user_prompt = f"""Write a {sequence_length}-email cold outreach sequence.

Offer: {offer_description}
Target: {target_persona}
Tone: {tone}
Pain point to address: {pain_point}
Industry niche: {niche}

For each email, provide:
- subject_line (under 50 chars, no spam words)
- subject_variants (2 A/B test alternatives)
- body (with {{{{first_name}}}}, {{{{company}}}}, {{{{role}}}} merge tags)
- send_on_day (day number from sequence start)
- stop_if_replied (always true)

JSON format:
{{
  "emails": [
    {{
      "step": 1,
      "subject_line": "...",
      "subject_variants": ["...", "..."],
      "body": "...",
      "send_on_day": 0,
      "stop_if_replied": true
    }}
  ]
}}"""

    response = await openrouter_client.chat(
        model="anthropic/claude-haiku",   # best quality for copywriting
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=2000,
        temperature=0.7,
    )

    return parse_sequence_json(response.choices[0].message.content)
```

### Merge Tags — Full List

Standard tags (from contact data):
```
{{first_name}}         John
{{last_name}}          Smith
{{full_name}}          John Smith
{{company}}            Acme Corp
{{company_domain}}     acme.com
{{role}}               Head of Sales
{{location}}           London, UK
{{linkedin_url}}       https://linkedin.com/in/...
```

Intelligence tags (from List Intel enrichment — unique to us):
```
{{email_infra}}        Google Workspace
{{domain_age}}         4 years old
{{recent_signal}}      "raised Series A 6 weeks ago"
{{niche}}              B2B SaaS
```

Custom tags (from user's CSV columns):
```
{{any_csv_column}}     Whatever the user uploaded
```

**AI personalisation tag (generates per-contact):**
```
{{ai_opener}}          Generates a unique opening line per contact
                       using their name, company, and signals.
                       "I saw Acme just expanded into the European market —
                        must be an exciting time to be scaling the sales team."
```

### The AI Opener — Per-Contact Personalisation at Scale

```python
# app/features/outreach/personalisation/ai_opener.py

async def generate_opener_batch(contacts: list[Contact]) -> dict[str, str]:
    """
    Generates a unique personalised opening line for each contact.
    Runs in batches of 20 to manage API rate limits.
    """
    openers = {}

    for batch in chunks(contacts, 20):
        prompt = f"""Generate a brief, natural-sounding personalised email opener
for each of these contacts. Max 1–2 sentences each.
Use their company signals, role, and industry to make it relevant.
Avoid generic openers. Sound like you did genuine research.

Contacts:
{json.dumps([{
    "id": c.id,
    "name": c.first_name,
    "company": c.company,
    "role": c.title,
    "signals": [s.value for s in c.signals[:2]],
    "industry": c.industry,
} for c in batch], indent=2)}

Respond ONLY with JSON:
{{"openers": {{"contact_id": "opener text", ...}}}}"""

        response = await openrouter_client.chat(
            model="anthropic/claude-haiku",
            messages=[{"role": "user", "content": prompt}],
            max_tokens=1000,
            temperature=0.8,
        )

        batch_openers = parse_opener_json(response)
        openers.update(batch_openers)

    return openers
```

---

## 3.3 Campaign Builder — The Full Flow

### Step 1: Setup

```
Campaign name:     [Q2 SaaS Founders UK]
Contact list:      [Prospects: SaaS Founders UK — 623 A/B tier] ▼
                   ○ or import new CSV
Sending accounts:  ✓ outreach@agency.io (150/day limit)
                   ○ outreach2@agency.io (add)
Schedule:          [Weekdays only] [9am–5pm] [Recipient timezone]
Start date:        [April 1, 2026]
Daily limit:       [50] contacts per day
```

### Step 2: Sequence Builder

```
SEQUENCE BUILDER

Step 1 — Day 0 (Initial)                          [Edit] [Delete]
─────────────────────────────────────────────────
From:    outreach@agency.io
Subject: {{first_name}}, quick question about {{company}}
         [+ A/B: "One question for {{company}} founders"]
Body:
  Hi {{first_name}},

  {{ai_opener}}

  I help B2B SaaS founders reduce churn without hiring a bigger CS team.

  Most teams we talk to are spending 15+ hours/week on manual check-ins that
  could be fully automated.

  Worth a 20-min call to see if it'd be relevant for {{company}}?

  Best,
  [sender name]

⏸ Wait: 3 days if no reply

──────────────────────────────────────────────────

Step 2 — Day 3 (Follow-up)                        [Edit] [Delete]
─────────────────────────────────────────────────
Subject: Re: [continuing thread]
Body:
  Hey {{first_name}} — just floating this back up in case it got buried.

  One question: does your CS team still handle onboarding check-ins manually?

  Happy to share what's working for similar SaaS teams.

⏸ Wait: 5 days if no reply

──────────────────────────────────────────────────

Step 3 — Day 8 (Breakup)
─────────────────────────────────────────────────
Subject: Re: [continuing thread]
Body:
  Last one, I promise, {{first_name}}.

  If reducing manual CS overhead isn't a priority right now, totally understood.

  I'll stop following up — but feel free to reach out when the timing is better.

  [Your name]

[+ Add step] [Generate with AI]

──────────────────────────────────────────────────
STOP CONDITIONS (apply to all steps):
  ✓ Stop if replied
  ✓ Stop if unsubscribed
  ✓ Stop if bounced (auto-submits to bounce pool)
  □ Stop if opened but not replied after 3 days
```

### Step 3: Conditional Branching

Advanced feature — different sequences based on enrichment signals:

```
SMART BRANCHING                                    [Enable ▼]

IF spam_filter == "Mimecast"
  → Use: Mimecast-safe sequence (shorter, simpler, no links)
  → From: warmed dedicated domain (mimecast-safe@altdomain.io)

IF email_infra == "GWS"
  → Use: Standard sequence

IF email_infra == "M365"
  → Use: M365-optimised sequence (fewer images, plain text)

IF prospect_score >= 90
  → Use: High-value sequence (more personalisation steps)
  → Also: Notify me via Slack when they reply

IF signals.has_recent_funding
  → Insert Step 1 variant: "Congrats on the recent funding round..."
```

### Step 4: Review + Launch

```
Campaign summary:
  Total contacts:    623
  Estimated reaches: 601 (after quality filters applied)
  Sequence steps:    3 emails over 8 days
  Sending accounts:  1 (outreach@agency.io — 150/day limit)
  Expected duration: ~13 days to contact everyone
  Credits for AI:    623 × {{ai_opener}} = ~3,115 tokens ≈ 31 credits

  [Edit] [Schedule for April 1] [Launch now]
```

---

## 3.4 Sending Engine

### How Emails Actually Go Out

```python
# app/features/outreach/engine/sender.py

@celery_app.task(name="tasks.process_send_queue")
async def process_send_queue():
    """
    Runs every 5 minutes via Celery beat.
    Processes pending sends for all active campaigns.
    """
    pending = await get_pending_sends()   # sends due now, within sending hours

    for send in pending:
        try:
            # Respect daily limit per sending account
            if await is_account_at_daily_limit(send.account_id):
                await reschedule_send(send.id, delay_hours=1)
                continue

            # Build the personalised email
            email_html = await render_email(send)  # fills merge tags + AI opener

            # Add tracking pixel + redirect links
            email_html = await inject_tracking(email_html, send.id)

            # Send via appropriate provider
            if send.account.provider == "gmail":
                await send_via_gmail(send.account, email_html, send)
            elif send.account.provider == "outlook":
                await send_via_outlook(send.account, email_html, send)
            else:
                await send_via_smtp(send.account, email_html, send)

            # Record success
            await mark_sent(send.id)
            await increment_account_daily_count(send.account_id)

        except Exception as e:
            await mark_failed(send.id, str(e))
            if "bounce" in str(e).lower() or "550" in str(e):
                await handle_bounce(send.contact_id, send.job_id)
```

### Smart Send Timing

```python
async def calculate_send_time(contact: Contact, account: SendingAccount) -> datetime:
    """
    Schedules sends for optimal delivery time.

    Factors:
    1. Recipient timezone (inferred from domain country + email infra)
    2. User's configured sending hours (e.g. 9am–5pm)
    3. Day of week (avoid Monday morning and Friday afternoon)
    4. Random jitter (±30min) so emails don't all arrive at exactly 9:00am
    5. Spread across the day (not all at once)
    """
    recipient_tz = infer_timezone(contact.domain, contact.email_infra)
    target_hour = random.randint(9, 11)   # 9am–11am = best open rates
    jitter = timedelta(minutes=random.randint(-30, 30))

    send_time = next_business_day_at(
        hour=target_hour,
        timezone=recipient_tz,
    ) + jitter

    return send_time
```

### Bounce Handling

```python
async def handle_bounce(contact_id: str, account_id: str, error_code: str):
    """
    When a send bounces:
    1. Stop the sequence for this contact
    2. Classify as hard or soft bounce
    3. Auto-submit to bounce pool (improving platform for everyone)
    4. Update contact status
    5. Notify user if bounce rate crosses threshold
    """
    bounce_type = classify_smtp_error(error_code)
    # 550, 551, 552, 553 = hard bounce (permanent)
    # 421, 450, 451 = soft bounce (temporary)

    await stop_contact_sequence(contact_id)
    await submit_to_bounce_pool(contact_id, bounce_type)  # free contribution
    await update_contact_status(contact_id, f"bounced_{bounce_type}")

    account = await get_account(account_id)
    if account.bounce_rate_7d > 0.05:
        await create_notification(account.user_id, "bounce_rate_warning", {
            "account": account.email,
            "rate": account.bounce_rate_7d,
        })
```

---

## 3.5 Real-Time Tracking

### Tracking Infrastructure

```python
# Dedicated tracking subdomain: t.listintel.io
# Handles all pixels and redirects

# Open tracking — 1x1 transparent GIF pixel
@app.get("/p/{pixel_id}")
async def track_open(pixel_id: str, request: Request, db=Depends(get_db)):
    event = await get_tracking_event(db, pixel_id)
    if not event:
        return pixel_response()   # return pixel anyway — don't error

    # Deduplicate: only count one open per contact per email
    if not await has_been_opened(db, pixel_id):
        await record_event(db, {
            "type": "open",
            "send_id": event.send_id,
            "contact_id": event.contact_id,
            "campaign_id": event.campaign_id,
            "ip": request.client.host,
            "user_agent": request.headers.get("user-agent"),
            "opened_at": datetime.now(UTC),
        })
        await update_sequence_trigger(event.send_id, "opened")

    return pixel_response()   # always return 200 + pixel


def pixel_response() -> Response:
    GIF_1X1 = b"GIF89a\x01\x00\x01\x00\x80\x00\x00\xff\xff\xff\x00\x00\x00!\xf9\x04\x00\x00\x00\x00\x00,\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
    return Response(
        content=GIF_1X1,
        media_type="image/gif",
        headers={
            "Cache-Control": "no-store, no-cache, must-revalidate",
            "Pragma": "no-cache",
        }
    )


# Click tracking — redirect links
@app.get("/r/{tracking_id}")
async def track_click(tracking_id: str, db=Depends(get_db)):
    link = await get_tracked_link(db, tracking_id)
    if not link:
        raise HTTPException(404)

    await record_event(db, {
        "type": "click",
        "send_id": link.send_id,
        "contact_id": link.contact_id,
        "campaign_id": link.campaign_id,
        "original_url": link.original_url,
        "clicked_at": datetime.now(UTC),
    })

    return RedirectResponse(link.original_url, status_code=302)
```

### Events Tracked Per Contact

```
SEND EVENTS:
  queued      — email added to send queue
  sent        — successfully delivered to mail server
  failed      — send failed (with error code)
  bounced     — mail server rejected permanently

ENGAGEMENT EVENTS:
  opened      — tracking pixel fired
  clicked     — tracking link clicked (with URL)
  replied     — reply detected via IMAP

OUTCOME EVENTS:
  unsubscribed — unsubscribe link clicked
  interested   — user manually marked as interested
  not_interested — user manually marked or detected
  meeting_booked — Calendly/Cal.com link clicked
  ooo          — auto-reply indicating out of office
```

---

## 3.6 Reply Detection + Classification

### IMAP Polling (Celery beat every 5 minutes)

```python
@celery_app.task(name="tasks.detect_replies")
async def detect_replies():
    """
    For each active sending account, check inbox for replies to campaign emails.
    """
    for account in await get_accounts_with_active_campaigns():
        async with imap_connect(account) as imap:
            # Check for replies to sent emails
            # Match by Message-ID or In-Reply-To header
            recent_messages = await imap.fetch_recent(hours=6)

            for msg in recent_messages:
                if original_send := await match_to_campaign_send(msg):
                    reply_type = await classify_reply(msg.body, msg.subject)
                    await process_reply(original_send, msg, reply_type)


async def classify_reply(body: str, subject: str) -> ReplyClassification:
    """
    Classify reply type using Claude Haiku (fast + cheap).
    """
    response = await openrouter_client.chat(
        model="anthropic/claude-haiku",
        messages=[{
            "role": "user",
            "content": f"""Classify this email reply into ONE category:

Subject: {subject}
Body: {body[:500]}

Categories:
- POSITIVE_INTEREST: They want to learn more, book a call, etc.
- MEETING_BOOKED: They've scheduled or confirmed a meeting
- NOT_INTERESTED: They declined, not relevant, timing wrong
- OUT_OF_OFFICE: Auto-reply or OOO message
- UNSUBSCRIBE: They want to be removed from future emails
- REFERRAL: They're forwarding to someone else
- QUESTION: They have a question about your offer
- OTHER: Doesn't fit above categories

Respond with ONLY the category name, nothing else."""
        }],
        max_tokens=20,
        temperature=0,
    )
    return ReplyClassification(response.choices[0].message.content.strip())
```

### Automated Reply Actions

```python
REPLY_ACTIONS = {
    "POSITIVE_INTEREST": [
        stop_sequence,                          # no more follow-ups
        mark_contact_as_interested,             # update contact status
        notify_user_with_full_context,          # push notification + email
        add_to_crm_webhook,                     # fire webhook for CRM sync
    ],
    "MEETING_BOOKED": [
        stop_sequence,
        mark_contact_as_won,
        notify_user,
        log_to_audit,
    ],
    "NOT_INTERESTED": [
        stop_sequence,
        mark_contact_as_lost,
        add_to_suppression_list,                # never email again
    ],
    "OUT_OF_OFFICE": [
        pause_sequence_until_return_date,       # extract return date from OOO
        reschedule_next_step_after_return,
    ],
    "UNSUBSCRIBE": [
        stop_sequence,
        add_to_suppression_list,
        log_unsubscribe_for_compliance,
        send_confirmation_to_contact,
    ],
    "REFERRAL": [
        stop_sequence_for_original_contact,
        extract_referred_contact,               # who were they referred to?
        create_new_prospect_from_referral,      # auto-add to pipeline
        notify_user,
    ],
}
```

---

## 3.7 Campaign Analytics — Full Dashboard

### Overview Panel

```
Campaign: Q2 SaaS Founders UK          Status: Active   Day 6 of ~13
────────────────────────────────────────────────────────────────────

Contacts in sequence:    623    (601 sent so far · 22 queued)

           Sent    Opened  Clicked  Replied  Bounced  Unsubd
Step 1:    601     254     41       22       7        3
           100%    42.3%   6.8%    3.7%     1.2%     0.5%

Step 2:    289     118     18       11       2        1
(of non-replied)  40.8%   6.2%    3.8%     0.7%     0.3%

Step 3:    0       —       —        —        —        —
(not started yet)

TOTALS:
  Open rate:    42.3%  ████████████████████████░░   (avg: 31%)  ↑ 36% better
  Reply rate:    3.7%  █████░░░░░░░░░░░░░░░░░░░░░   (avg: 2%)   ↑ 85% better
  Bounce rate:   1.2%  ██░░░░░░░░░░░░░░░░░░░░░░░░   (threshold: 5%) ✓

Positive replies: 22   [View all →]
Meetings booked:  4    [View all →]
```

### Performance by List Intel Intelligence Signals

```
Performance by infrastructure:
  GWS contacts:        Open 48.1%   Reply 4.9%    ████████████████████
  M365 contacts:       Open 37.2%   Reply 3.1%    ███████████████░░░░░
  Custom SMTP:         Open 29.4%   Reply 2.2%    ████████████░░░░░░░░

Performance by burn score at send time:
  Fresh (0–20):        Open 53.2%   Reply 5.8%    ██████████████████████
  Warm (21–50):        Open 38.7%   Reply 3.6%    ████████████████░░░░░
  (Burned excluded by Fresh Only preset)

Performance by spam filter:
  No gateway:          Open 44.8%   Reply 4.2%    ██████████████████░░
  (Mimecast excluded by preset)

Insight: Your GWS + Fresh contacts are converting at 2.6x the rate
of your M365 + Warm contacts. Consider running your next campaign
exclusively on this segment for maximum efficiency.
```

### Subject Line A/B Test Results

```
Subject A/B Test — Step 1:

A: "{{first_name}}, quick question about {{company}}"
   Sent: 301   Opens: 142   Open rate: 47.2%   ← WINNER

B: "One question for {{company}} founders"
   Sent: 300   Opens: 112   Open rate: 37.3%

Winner declared: Version A (26% higher open rate)
→ Apply to remaining sends?  [Yes, apply winner]
```

### Contact-Level Activity Feed

```
Recent activity                                     [View all]

✓ Sarah Okonkwo (PayFlow Ltd) replied — POSITIVE INTEREST   2h ago
  "Thanks for reaching out! This actually sounds relevant..."
  [View reply] [Mark won] [Mark lost]

✉ James Whitfield (Leanstack) opened email            3h ago
  Step 2 — 2nd open in 24 hours

⚡ Marcus Reid (Trackably) clicked link               5h ago
  Clicked: https://calendly.com/your-calendar

✓ Priya Sharma (Automator.io) replied — OUT OF OFFICE  6h ago
  Returns April 8 — sequence paused, resumes April 9

❌ David Chen (Megacorp) bounced                       8h ago
  Hard bounce — submitted to bounce pool
```

---

## 3.8 Smart Follow-Up Engine

### Automated Refinement Based on Campaign Data

After Step 1 completes for a significant sample (100+ sends), List Intel
analyses performance and suggests refinements:

```
Campaign Health Alert — Step 1 completed for 200 contacts

Your open rate is 29% (below platform avg of 38%)

Possible causes:
  ⚠ Subject line may contain a spam trigger word
    Detected: "quick" — flagged by some spam filters
    Suggestion: Try "{{first_name}}, had a thought about {{company}}"

  ⚠ 34% of your list is behind Microsoft 365
    M365 has stricter spam filtering for images
    Suggestion: Switch to plain text version for M365 contacts

  ⚠ Sending account domain is 8 months old — still building reputation
    Suggestion: Lower daily send limit to 40 while reputation builds

[Apply suggestions] [Dismiss] [Learn more]
```

### Dynamic Sequence Adaptation

Based on real-time engagement, the sequence adapts:

```python
ADAPTATION_RULES = [
    # If contact opened 3+ times but never replied — they're interested but hesitant
    # Insert a softer, more casual follow-up instead of standard step 2
    {
        "condition": lambda e: e.open_count >= 3 and e.reply_count == 0,
        "action": "insert_soft_followup",
        "template": "soft_curiosity_followup",
    },

    # If domain is showing high open rates but low reply rates across contacts
    # The domain's email culture might prefer a different CTA
    {
        "condition": lambda e: e.domain_open_rate > 0.5 and e.domain_reply_rate < 0.02,
        "action": "switch_cta",
        "from": "book_a_call",
        "to": "reply_with_interest",
    },

    # If contact clicked the calendly link but didn't book
    # Send a specific "did the link work?" follow-up
    {
        "condition": lambda e: e.clicked_calendly and not e.meeting_booked,
        "action": "send_calendly_rescue",
        "delay_hours": 4,
    },
]
```

---

## 3.9 LinkedIn Outreach (Phase 4+)

Beyond email — connecting the dots to LinkedIn for true multi-channel sequences:

```
MULTI-CHANNEL SEQUENCE (future)

Day 0:  Send email (Step 1)
Day 1:  LinkedIn connection request (if not already connected)
Day 3:  LinkedIn message (if email not opened and connection accepted)
Day 5:  Email follow-up (Step 2)
Day 8:  LinkedIn follow-up message (if email still no reply)
Day 10: Final email (breakup)

Rules:
  - Never LinkedIn + email on same day
  - Stop all channels on any positive signal
  - LinkedIn via Proxycurl or PhantomBuster API
```

---

## 3.10 CRM & Tool Sync

### Native integrations (no webhook needed):

**HubSpot:**
```python
async def sync_to_hubspot(contact: Contact, outcome: str, user: User):
    """
    When a contact replies positively, create/update in HubSpot.
    """
    hubspot_contact = await hubspot_client.create_or_update_contact(
        user.hubspot_api_key,
        {
            "email": contact.email,
            "firstname": contact.first_name,
            "lastname": contact.last_name,
            "company": contact.company,
            "jobtitle": contact.title,
            "list_intel_score": contact.prospect_score,
            "list_intel_burn": contact.burn_score,
            "list_intel_infra": contact.email_infra,
            "hs_lead_status": "IN_PROGRESS" if outcome == "positive" else "OPEN",
        }
    )
```

**Instantly / Smartlead:**
Push enriched contacts directly into Instantly/Smartlead campaigns via their APIs.
Lets users who prefer those tools for sending still benefit from List Intel's
enrichment, scoring, and prospecting.

```python
# Export directly to Instantly campaign
POST /api/v1/campaigns/{campaign_id}/export/instantly
{
    "instantly_campaign_id": "abc123",
    "instantly_api_key": "...",
    "filter": "a_tier_only"   // only send top prospects
}
```

---

## 3.11 Database Schema — New Tables

```sql
-- Sending accounts
CREATE TABLE sending_accounts (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    provider TEXT NOT NULL,  -- gmail/outlook/smtp
    email TEXT NOT NULL,
    display_name TEXT,
    encrypted_access_token BYTEA,
    encrypted_refresh_token BYTEA,
    token_expiry TIMESTAMPTZ,
    smtp_host TEXT,
    smtp_port INTEGER,
    daily_send_limit INTEGER DEFAULT 50,
    sending_hours_start INTEGER DEFAULT 9,
    sending_hours_end INTEGER DEFAULT 17,
    timezone TEXT DEFAULT 'UTC',
    warmup_mode BOOLEAN DEFAULT TRUE,
    health_score INTEGER DEFAULT 100,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Email templates
CREATE TABLE email_templates (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    name TEXT NOT NULL,
    subject_line TEXT NOT NULL,
    subject_variants TEXT[],
    body_html TEXT NOT NULL,
    body_text TEXT,
    merge_tags_used TEXT[],
    is_ai_generated BOOLEAN DEFAULT FALSE,
    category TEXT,  -- opener/followup/breakup
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Campaigns
CREATE TABLE campaigns (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    workspace_id UUID,
    name TEXT NOT NULL,
    status TEXT DEFAULT 'draft',  -- draft/scheduled/active/paused/complete
    contact_list_id UUID,  -- refers to job or prospect job
    sending_account_id UUID REFERENCES sending_accounts(id),
    daily_limit INTEGER DEFAULT 50,
    schedule_start TIMESTAMPTZ,
    timezone TEXT DEFAULT 'UTC',
    send_on_weekdays_only BOOLEAN DEFAULT TRUE,
    settings JSONB,  -- conditional branching rules etc.
    created_at TIMESTAMPTZ DEFAULT NOW(),
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ
);

-- Sequence steps
CREATE TABLE sequence_steps (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID REFERENCES campaigns(id) ON DELETE CASCADE,
    step_number INTEGER NOT NULL,
    template_id UUID REFERENCES email_templates(id),
    send_on_day INTEGER NOT NULL,  -- days from sequence start
    wait_for_reply BOOLEAN DEFAULT TRUE,
    conditions JSONB,  -- conditional branching
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Individual sends
CREATE TABLE campaign_sends (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    campaign_id UUID REFERENCES campaigns(id),
    step_id UUID REFERENCES sequence_steps(id),
    contact_id UUID,
    sending_account_id UUID REFERENCES sending_accounts(id),
    status TEXT DEFAULT 'queued',
    scheduled_at TIMESTAMPTZ,
    sent_at TIMESTAMPTZ,
    subject TEXT,
    body_html TEXT,  -- rendered with merge tags (stored for reference)
    message_id TEXT,  -- SMTP Message-ID for reply matching
    error TEXT,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Tracking events
CREATE TABLE tracking_events (
    id BIGSERIAL PRIMARY KEY,
    send_id UUID REFERENCES campaign_sends(id),
    campaign_id UUID,
    contact_id UUID,
    event_type TEXT NOT NULL,  -- open/click/reply/bounce/unsubscribe
    metadata JSONB,
    ip_address INET,
    user_agent TEXT,
    occurred_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_tracking_send ON tracking_events(send_id);
CREATE INDEX idx_tracking_campaign ON tracking_events(campaign_id, occurred_at DESC);

-- Tracked links (for click tracking)
CREATE TABLE tracked_links (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    send_id UUID REFERENCES campaign_sends(id),
    contact_id UUID,
    campaign_id UUID,
    original_url TEXT NOT NULL,
    created_at TIMESTAMPTZ DEFAULT NOW()
);

-- Prospect jobs (List Source)
CREATE TABLE prospect_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id),
    name TEXT NOT NULL,
    status TEXT DEFAULT 'queued',
    icp_filters JSONB NOT NULL,
    target_count INTEGER DEFAULT 500,
    found_count INTEGER DEFAULT 0,
    qualified_count INTEGER DEFAULT 0,
    sources_used TEXT[],
    credits_used INTEGER DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    completed_at TIMESTAMPTZ
);

-- Prospects (results of prospect jobs)
CREATE TABLE prospects (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    prospect_job_id UUID REFERENCES prospect_jobs(id),
    user_id UUID REFERENCES users(id),
    email TEXT NOT NULL,
    email_hash VARCHAR(64),
    first_name TEXT,
    last_name TEXT,
    full_name TEXT,
    company TEXT,
    company_domain TEXT,
    title TEXT,
    linkedin_url TEXT,
    location TEXT,
    industry TEXT,
    company_size TEXT,
    tech_stack TEXT[],
    funding_stage TEXT,
    signals JSONB,
    prospect_score INTEGER,
    email_confidence INTEGER,
    -- Enrichment columns (same as job_results)
    syntax_valid BOOLEAN,
    mx_valid BOOLEAN,
    spam_filter TEXT,
    email_infra TEXT,
    domain_age_days INTEGER,
    domain_risk TEXT,
    burn_score INTEGER,
    burn_tag TEXT,
    bounce_score INTEGER,
    -- Status
    status TEXT DEFAULT 'new',  -- new/contacted/replied/won/lost/suppressed
    campaign_id UUID,
    created_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_prospects_job ON prospects(prospect_job_id);
CREATE INDEX idx_prospects_score ON prospects(prospect_job_id, prospect_score DESC);
```

---

## 3.12 Revised Full Credit System

With prospecting and outreach, credits cover everything:

```
ENRICHMENT CREDITS (existing):
  1 credit = enrich 1 email you already have (all 8 layers)

PROSPECTING CREDITS (new):
  1.5 credits = find + enrich 1 lead from public sources (Apollo data)
  2.0 credits = find + enrich 1 lead with LinkedIn profile data
  3.0 credits = find + enrich + get signals (funding, news, jobs)

OUTREACH CREDITS (new):
  0.5 credits = send 1 email via connected account
  2.0 credits = generate AI opener for 1 contact (per campaign, cached)
  1.0 credit  = AI reply classification (per reply received)

DOMAIN HEALTH CREDITS (new):
  5 credits = full sending domain reputation check (50+ RBLs)
  1 credit  = quick check (top 10 RBLs only)

MARKETPLACE:
  10% of list size in credits = trade fee

EXAMPLE — Full campaign end-to-end:
  500 prospects found (Apollo):           1,000 credits (2.0 each)
  500 AI openers generated:               1,000 credits (2.0 each)
  1,200 emails sent (3-step sequence):      600 credits (0.5 each)
  45 reply classifications:                  45 credits (1.0 each)
  ──────────────────────────────────────────────────────────────────
  Total for full campaign:               2,645 credits ≈ $2.65 at Starter
```

---

## 3.13 The Full Loop — Everything Connected

```
1. DEFINE ICP
   "I want B2B SaaS founders, 10–200 employees, UK, using HubSpot"
   → ICP Builder in Prospects tab

2. FIND LEADS
   → Prospect job runs (Apollo + LinkedIn + web scraping + signals)
   → 847 contacts found, 623 A/B tier after quality filters

3. AUTO-ENRICH
   → All 8 List Intel layers run on every found email
   → Burn scores, spam filters, domain age, infra tags — all done

4. LAUNCH CAMPAIGN
   → Select A-tier contacts (score 70+)
   → AI generates personalised opener per contact
   → 3-step sequence over 8 days
   → Smart branching: Mimecast contacts → different template + domain

5. SEND + TRACK
   → Celery sends emails at optimal times per recipient timezone
   → Open pixels + click redirects track engagement in real time
   → IMAP polls for replies every 5 minutes

6. REPLY HANDLING
   → AI classifies each reply (interested/not/OOO/unsubscribe)
   → Sequences stop automatically on any signal
   → Interested replies push notification to user + CRM sync
   → Bounces auto-submit to burn pool (improving platform for everyone)
   → Unsubscribes auto-add to suppression list

7. REFINEMENT
   → Campaign analytics show performance by infra, burn score, gateway
   → A/B test winner applied automatically after 100 sends
   → Smart suggestions: "Switch M365 contacts to plain text"
   → After campaign: re-run burn scores on sent list (aging monitor)

8. REPEAT
   → Each campaign makes the platform smarter:
     Better burn scores (more data)
     Better bounce data (auto-submitted)
     Better AI personalisation (improving from feedback)
   → Next search finds better leads because the data is richer
```

---

## Phased Build Order

```
Phase 2 (after $1k MRR):
  → Sending account connection (Gmail/Outlook OAuth)
  → Basic campaign builder (no AI, no branching)
  → Email template editor
  → Open/click tracking infrastructure
  → Unsubscribe handling
  → Webhook engine

Phase 3 (after $3k MRR):
  → AI template generator
  → AI personalised openers
  → Reply detection (IMAP polling)
  → Reply classification (AI)
  → Campaign analytics dashboard
  → A/B subject line testing
  → Smart follow-up engine

Phase 4 (after $5k MRR):
  → List Source (prospecting engine)
  → Apollo API integration
  → Hunter.io email discovery
  → Proxycurl LinkedIn data
  → Prospect scoring
  → ICP builder interface
  → Signals (funding, news, hiring)
  → Conditional sequence branching

Phase 5 (after $10k MRR):
  → LinkedIn outreach (multi-channel sequences)
  → Web scraping engine (company pages)
  → BuiltWith tech stack detection
  → CRM native integrations (HubSpot, Salesforce)
  → Instantly/Smartlead direct push
  → Self-serve n8n workspace (Agency plan)
```
