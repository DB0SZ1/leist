# List Intel — MEMORY.md
> Persistent facts. Never override these without explicit instruction from Ahmad.
> Read this before writing any code, making any architectural decision, or suggesting any change.

---

## Who Is Building This

**Ahmad** — solo full-stack developer based in Nigeria. Building List Intel independently.
No team. No DevOps. Budget is near-zero at launch. Every decision must account for this.

---

## What List Intel Is

A cold email list intelligence SaaS. Users upload a CSV of email addresses.
The backend runs 8 intelligence layers in parallel and returns an enriched CSV.

**It is NOT just a verifier.** The verifier is Table Stakes.
The intelligence layer (burn score, spam filter detection, infra tagging, domain age, marketplace) is the product.

---

## The Two-Product Vision

**Tool 1 — List Intel** (building now)
Verify and enrich lists you already have.

**Tool 2 — List Source** (Month 4–5, not yet designed)
Find and build lists from scratch. Same audience, natural cross-sell.
Design the backend NOW with a shared `users` table so Tool 2 plugs in without migration pain.

---

## Stack — Locked In, Do Not Change

| Layer | Choice |
|---|---|
| Backend | Python FastAPI |
| Frontend | Jinja2 templates (server-rendered HTML) — NOT React, NOT Next.js |
| CSS | Tailwind CDN + custom CSS |
| JS | Alpine.js (CDN) + vanilla JS — NO build step |
| Database | PostgreSQL 15 on Railway |
| Cache + Queue | Redis 7 on Railway |
| Background workers | Celery 5 |
| Payments | Paystack — NOT Stripe. Paystack. USD + NGN. |
| Transactional email | Resend |
| WHOIS | python-whois (free) — NOT WhoisXML API at launch |
| DNS | aiodns + dnspython |
| ORM | SQLAlchemy 2.0 async |
| Migrations | Alembic |
| Auth | Custom JWT — NOT Auth0, NOT Supabase Auth, NOT Firebase |
| Serialisation (inter-service) | MessagePack — NOT JSON |
| Hosting | Railway (everything: FastAPI + PostgreSQL + Redis + Celery) |

**Rationale for Jinja2 over Next.js:** Ahmad is a solo dev. One codebase. One deployment.
No Vercel account needed. No frontend/backend split to manage. Handles 1k users easily.

**Rationale for Paystack over Stripe:** Ahmad is in Nigeria. Paystack works natively.
USD pricing is supported. Webhook delivery is reliable. No US entity required.

---

## Phase 1 Ships — Phase 2 Deferred

**Phase 1 (launch — everything ships):**
- Full auth (register, login, refresh, verify, reset)
- Paystack billing (subscriptions + credit packs + webhooks)
- Processing pipeline: syntax + MX + spam filter + infra + domain age + catchall + burn score + bounce history
- Burn score network (SHA-256 hash pool)
- Fresh Only export with filter presets
- Burned List Marketplace (server-side matching)
- REST API with key management
- AI spam copy checker (OpenRouter free model)
- Domain blacklist/reputation checker
- Full dashboard with Jinja2 templates

**Phase 2 (after $3k MRR):**
- SMTP deep verification (MillionVerifier wholesale API at ~$0.00008/email)
- Full catchall SMTP probe (Phase 1 uses heuristics only)

**SMTP is the ONLY deferred feature. Everything else is Phase 1.**

---

## Go-To-Market — The WhatsApp Strategy

Ahmad is a **member** (not owner) of two WhatsApp communities run by Jack (OmniVerifier founder):

1. **Omni Cold Email Chat** — general cold email operations
2. **Lead List Trading — POWERED BY OMNIVERIFIER** — active list trading

**Launch sequence:**
1. Drop List Intel as a free tool in both groups. Community member tone, not vendor pitch.
2. Free for 1–2 months to seed the burn score pool with uploads.
3. Flip to paid tiers. Free tier stays but capped at 500 credits/mo.
4. Approach Jack (OmniVerifier) for partnership/integration after 800+ users.

**Exact WhatsApp drop message:**
> "Built a tool after seeing the Mimecast conversation last week. Upload any list — it tags every
> email with which spam filter guards it (Mimecast, Proofpoint, Barracuda), whether it's on
> Google/Outlook/SMTP, and domain age risk. Free tier available, paid plans from $10/mo. [link]"

---

## Pricing — Final

| Plan | Price | Credits/mo |
|---|---|---|
| Free | $0 | 500 |
| Starter | $10/mo | 25,000 |
| Growth | $49/mo | 100,000 |
| Pro | $99/mo | 500,000 |
| Agency | $249/mo | Unlimited |

Credit packs (one-time, never expire): $9 / $35 / $129 / $389 / $1,499

**Free launch mode:** `FREE_TIER_LAUNCH_MODE=True` in config disables all credit limits
during the initial free period. Flip to False when going paid.

---

## Revenue Streams

1. Subscriptions (core)
2. Credit packs (one-time top-up)
3. Marketplace freshness fee (10% of list size in credits)
4. API subscriptions ($49/mo Starter, $149/mo Pro)
5. White-label licensing (OmniVerifier, Instantly, Smartlead) — Month 6+

---

## Infrastructure — Railway Topology

Three Railway services, one PostgreSQL, one Redis:

```
listintel-api      → uvicorn app.main:app
listintel-worker   → celery worker (queues: default, processing, marketplace)
listintel-beat     → celery beat (periodic: marketplace matching every 15min, credit reset monthly)
PostgreSQL         → Railway managed DB
Redis              → Railway managed Redis
```

Launch cost: ~$26–40/mo total. Gross margin: 95%+.

---

## Burn Score — The Moat

Every email uploaded is SHA-256 hashed (`hash_email(email.lower().strip())`).
Hashes are stored in `burn_pool` with `user_id`, `job_id`, `uploaded_at`.
Burn score = COUNT(DISTINCT user_id) WHERE uploaded_at > NOW() - INTERVAL '90 days'.
Normalised to 0–100. Tags: Fresh (0–20), Warm (21–50), Burned (51–80), Torched (81–100).

**GDPR compliant by design.** No plaintext emails ever stored in burn pool.
The pool is the network effect moat. It only grows. Competitors start from zero.

---

## Auth Flow — Exact Implementation

- **Access token**: JWT, 15-min expiry, stored in JS memory (`window.__li_token`), NOT localStorage
- **Refresh token**: opaque UUID, stored as httpOnly Secure SameSite=Strict cookie (`li_refresh`)
- **Email verification**: required before any dashboard access
- **Password reset**: 1-hour expiry token, single-use
- **On password reset / logout-all**: revoke ALL refresh tokens for that user

---

## Design System — List Intel Brand

```
Background:   #f2f1ec  (warm off-white)
Dark:         #172617  (near-black green)
Accent:       #2a5426  (forest green)
Accent2:      #3d7a36  (lighter green)
Yellow:       #cce836  (lime — used for underlines/CTAs)
Muted:        #6a796a  (muted green-grey)
Border:       #d8d8cf  (warm grey)
Font:         Bricolage Grotesque (Google Fonts)
Font weights: 400, 500, 600, 700, 800
```

Tags/pills — use these exact colours:
- `pg` (valid/safe/fresh): `bg-[#d4eecf] text-[#1b6015]`
- `pr` (invalid/burned/torched): `bg-[#fcd8d8] text-[#b31c1c]`
- `po` (role/warning/warm): `bg-[#fde3c0] text-[#964800]`
- `pb` (infra/info): `bg-[#d6e8fc] text-[#1a4c9a]`
- `py` (catchall/yellow): `bg-[#fdf5c0] text-[#786500]`

---

## Conventions — Never Deviate

- All UUIDs. No integer PKs for user-facing tables.
- All timestamps UTC, stored as TIMESTAMPTZ.
- Emails always `.lower().strip()` before any operation or storage.
- SHA-256 hashes always from `email.lower().strip()`.
- Never log plaintext emails in production. Log hashes only.
- Celery tasks are always idempotent — safe to retry on failure.
- Credits deducted ONLY on job completion, never on submission. Never deducted on failure.
- All monetary amounts stored as integers (cents). Never floats.
- API responses ALWAYS use the standard envelope: `APIResponse(success, message, data, errors, code)`.
- All exceptions are typed (`AppException` subclasses). Never raise raw `Exception`.
- Inter-service messages use MessagePack, not JSON dicts.
- CSRF tokens on all Jinja forms.
- Rate limiting on all API key routes via Redis sliding window.

---

## Community Intelligence (from WhatsApp chats, March 2026)

Pain points actively discussed — these validate List Intel's features:
- "How do I check whether inboxes are burned or the domains?" — burn score + domain check
- Two people same day asked for "AI spam checker with an API" — spam copy layer + API
- Mimecast silently inflating bounce rates — spam filter detector
- Copy fingerprinting vs infrastructure debate — infra detector
- Lead list requests: dental, law firms, Oil & Gas, HNI, senior living — validates Tool 2 (List Source)
- Manual list trading happening in the group — validates the Marketplace
- People using DeepSeek/Qwen/Mistral for personalization — OpenRouter free models viable

---

## What Has Been Built So Far

### Files completed (Week 1 in progress):
- `requirements.txt`
- `app/config.py`
- `app/core/responses.py`
- `app/core/exceptions.py`
- `app/core/database.py`
- `app/core/redis.py`
- `app/core/security.py`
- `app/core/msgpack.py`
- `app/core/rate_limit.py`
- `app/core/logging.py`
- `app/core/dependencies.py`
- `app/features/auth/models.py`
- `app/features/auth/schemas.py`
- `app/features/auth/service.py`
- `app/features/auth/email.py`
- `app/features/auth/router.py`
- `app/templates/base.html`
- `app/templates/auth/login.html`

### Still to write (Week 1):
- `app/templates/auth/signup.html`
- `app/templates/auth/forgot_password.html`
- `app/templates/auth/reset_password.html`
- `app/templates/auth/verify_email.html`
- `app/static/js/app.js`
- `app/static/css/app.css`
- `app/main.py`
- `alembic.ini`
- `migrations/env.py`
- `migrations/versions/001_initial_schema.py`
- `Dockerfile`
- `railway.toml`
- `.env.example`

### Week 2 (not started):
- Paystack billing full integration
- Job creation + CSV upload
- Processing layers
- Celery worker

### Week 3 (not started):
- Burn score pool
- Bounce history
- Dashboard templates
- Job result storage + polling

### Week 4 (not started):
- Fresh Only export
- API key management
- REST API routes

### Month 2 (not started):
- Marketplace
- AI spam copy checker
- Admin dashboard

---

## UI — All Screens & Their Routes

| Screen | Route | Template |
|---|---|---|
| Login | GET /auth/login | auth/login.html |
| Sign Up | GET /auth/signup | auth/signup.html |
| Verify Email | GET /auth/verify-email | auth/verify_email.html |
| Forgot Password | GET /auth/forgot-password | auth/forgot_password.html |
| Reset Password | GET /auth/reset-password | auth/reset_password.html |
| Onboarding | GET /onboarding | onboarding.html |
| Dashboard | GET /dashboard | dashboard/index.html |
| Job Detail | GET /jobs/{id} | dashboard/job_detail.html |
| Job History | GET /jobs | dashboard/job_list.html |
| Marketplace | GET /marketplace | marketplace/index.html |
| Billing | GET /billing | billing/index.html |
| API Keys | GET /api-keys | api_keys/index.html |
| Settings | GET /settings | settings/index.html |
| Profile | GET /profile | profile/index.html |
| Notifications | GET /notifications | notifications/index.html |
| 404 | — | errors/404.html |
| 500 | — | errors/500.html |
| Session expired | — | errors/401.html |

## UI — Key Flows

**Auth flow:**
Signup → Verify Email → Onboarding checklist → Dashboard

**Job flow:**
Dashboard upload zone → Job queued (polling) → Job detail → Fresh Only export / Marketplace trade

**Billing flow:**
Dashboard credits widget "Upgrade" → Billing page → Paystack checkout → Webhook activates plan → Dashboard refreshes

**Password reset flow:**
Login "Forgot password?" → Forgot Password page → Email sent → Reset Password page (token in URL) → Success → Login

**Trade flow:**
Job detail "74% burned — trade?" → Marketplace submit modal → Celery matcher (15min) → Notification "Trade matched" → Marketplace confirm → Both users get enriched CSVs

## UI — Password Validator Rules

Password strength requires these 4 rules. Track all 4 client-side with JS:
1. At least 8 characters → `val.length >= 8`
2. One uppercase letter → `/[A-Z]/.test(val)`
3. One number → `/[0-9]/.test(val)`
4. One special character → `/[^a-zA-Z0-9]/.test(val)`

Strength level: 1 rule = Weak (red), 2 = Fair (amber), 3 = Good (green), 4 = Strong (dark green)
Minimum to submit: 3 rules met. Block form submission if fewer.

## UI — Upload Zone States (6 total)

1. Default — dashed border, upload icon, "Drop CSV here"
2. Drag over — solid accent border, green tint, "Drop to upload"
3. Uploading — solid border, filename + filesize + row count + progress bar
4. Error: no email column — red border, red tint, "No email column found"
5. Error: insufficient credits — amber border, amber tint, credits needed vs available
6. Complete — green border, green tint, checkmark, email counts, "View results →"

## UI — Empty States (all screens)

Every list/table screen has an empty state. Never show an empty table.
Empty state structure: icon (44px, rounded, green tint) + title + sub-text (max 240px) + optional CTA.
Plan-gated features show amber icon + upgrade CTA instead of the standard green.

## UI — Toast Rules

- success (green): 4s auto-dismiss
- info (blue): 4s auto-dismiss
- warning (amber): 6s auto-dismiss
- error (red): 8s auto-dismiss — stays until user dismisses
- Never duplicate toasts for the same event
- Field validation errors go inline under the field, NOT in toasts

---

## UI Screen Inventory — All Screens Built

### Auth screens
- `/auth/login` — email + password, forgot password link
- `/auth/signup` — name + email + password + confirm password, live strength validator, live match validator
- `/auth/verify-email` — post-signup holding screen, resend link
- `/auth/forgot-password` — single email field, always returns success message
- `/auth/reset-password?token=xxx` — 3 states: form / success / expired

### Post-auth screens
- `/onboarding` — 5-step checklist (create account, verify email, first upload, first bounce, marketplace)
- `/dashboard` — stats row, upload zone (6 states), recent jobs table, processing progress
- `/jobs` — full job history table with all status types, auto-polls if any job is active
- `/jobs/<id>` — job detail, intelligence breakdown, 5-row enriched preview, Fresh Only panel, trade prompt
- `/marketplace` — active listings, completed trades, submit modal, confirm/decline trade flow
- `/billing` — plan grid, credit packs, billing history, Paystack checkout flow
- `/api-keys` — key list, create key modal (raw key shown once), revoke flow
- `/notifications` — notification list with unread/read states, preferences toggles
- `/settings` — profile edit, password change, export preset defaults, danger zone
- `/profile` — initials avatar, sidebar nav, account status, danger zone

### Error / empty pages
- 404, 500, 403 (plan gate), 401 (session expired)
- Empty states for every major section (jobs, marketplace, api keys, notifications, billing history)

---

## Design Tokens (Pixel-Perfect Reference)

```
Background:       #f2f1ec
White surface:    #ffffff
Surface (subtle): #fafaf6
Dark:             #172617
Dark2:            #1c2e1c
Accent:           #2a5426
Accent2:          #3d7a36
Yellow:           #cce836
Text:             #172617
Muted:            #6a796a
Border:           #d8d8cf
```

Status pill colours:
```
Fresh/valid/complete: bg #d4eecf  text #1b6015
Burned/invalid/error: bg #fcd8d8  text #b31c1c
Warm/role/warning:    bg #fde3c0  text #964800
Infra/GWS/info:       bg #d6e8fc  text #1a4c9a
Catchall/yellow:      bg #fdf5c0  text #786500
Plan badge:           bg rgba(42,84,38,.1)  text #2a5426
```

Password strength bar colours:
```
weak   (1/4): #e24b4a
fair   (2/4): #f59e0b
good   (3/4): #3d7a36
strong (4/4): #1b6015
```
