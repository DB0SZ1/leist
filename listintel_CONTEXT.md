# List Intel — CONTEXT.md
> Current build state, active decisions, and open questions.
> Update this file as the build progresses. It reflects NOW, not the spec.

---

## Current Build Phase

**Week 1 — In Progress**
Scaffold + PostgreSQL models + Full auth system

---

## Decisions Made This Session

### Stack simplification
Original spec had Next.js (Vercel) + FastAPI (Railway) split.
**Decision:** Collapsed to FastAPI + Jinja2 on Railway only.
Reason: Solo dev, simpler deployment, handles 1k users easily, no frontend build step.

### python-whois over WhoisXML API
**Decision:** Use `python-whois` (free) at launch. Cache aggressively in Redis (30-day TTL per domain).
Switch to WhoisXML API when volume justifies (~$15-40/mo at 1M emails processed).
Reason: Zero cost at launch, acceptable speed with caching.

### Free launch period
**Decision:** `FREE_TIER_LAUNCH_MODE=True` in config = unlimited credits during free period.
Flip to `False` after 1–2 months to activate paid tiers.
Reason: Need burn pool volume before paid tiers are valuable. Hooked users won't leave for $10/mo.

### Pricing floor
**Decision:** Starter plan is $10/mo (not $19).
Reason: Cold emailers are cost-sensitive. $10 is noise to them. Lower barrier to first conversion.

### MessagePack
**Decision:** All Celery payloads and inter-service messages use MessagePack.
Reason: Smaller payloads, faster serialisation, typed binary. No raw JSON dicts between services.

### Two-product vision confirmed
**Decision:** List Source (Tool 2) is a separate future product.
Build the users table and auth system now to support both products on one account.
Do NOT mix list sourcing features into List Intel. Different product, different positioning.

### Additional features to build (from WhatsApp chat analysis)
Beyond the original spec, adding:
- AI spam copy checker (OpenRouter free model — Mistral 7B)
- Domain blacklist/reputation checker (MXToolbox API or Spamhaus DNS lookups)
These fit naturally into the pre-send intelligence positioning.

---

## Active Build Log

### Completed files
```
requirements.txt                          ✅
app/config.py                             ✅
app/core/responses.py                     ✅  Standard APIResponse envelope
app/core/exceptions.py                    ✅  Typed exception hierarchy + global handlers
app/core/database.py                      ✅  Async SQLAlchemy engine + get_db
app/core/redis.py                         ✅  Redis pool + get_redis
app/core/security.py                      ✅  JWT + bcrypt + hash helpers
app/core/msgpack.py                       ✅  MessagePack encode/decode
app/core/rate_limit.py                    ✅  Redis sliding window rate limiter
app/core/logging.py                       ✅  Structured logging (structlog)
app/core/dependencies.py                  ✅  get_current_user, require_plan, require_api_key
app/features/auth/models.py               ✅  User + RefreshToken ORM models
app/features/auth/schemas.py              ✅  All auth Pydantic schemas
app/features/auth/service.py              ✅  All auth business logic
app/features/auth/email.py                ✅  Resend transactional email templates
app/features/auth/router.py               ✅  API routes + Jinja page routes
app/templates/base.html                   ✅  Root layout + toast + modal
app/templates/auth/login.html             ✅  Login page with Alpine.js form
```

### Remaining Week 1 files
```
app/templates/auth/signup.html            ⏳
app/templates/auth/forgot_password.html   ⏳
app/templates/auth/reset_password.html    ⏳
app/templates/auth/verify_email.html      ⏳
app/static/js/app.js                      ⏳  Toast store, modal store, apiFetch helper
app/static/css/app.css                    ⏳  Custom styles on top of Tailwind
app/main.py                               ⏳  FastAPI app factory, router registration, lifespan
alembic.ini                               ⏳
migrations/env.py                         ⏳
migrations/versions/001_initial_schema.py ⏳
Dockerfile                                ⏳
railway.toml                              ⏳
.env.example                              ⏳
```

---

## Architecture Decisions — Quick Reference

### How auth tokens flow
```
1. User logs in → POST /api/v1/auth/login
2. Server returns: { access_token } in JSON body
                   li_refresh cookie (httpOnly, Secure, SameSite=Strict)
3. Frontend stores access_token in window.__li_token (memory only)
4. Every API call: Authorization: Bearer {access_token}
5. On 401: auto-call POST /api/v1/auth/refresh (sends cookie automatically)
6. Server issues new access_token + rotates refresh token
```

### How a job flows
```
1. User uploads CSV → POST /api/v1/jobs (multipart)
2. FastAPI: validate auth, check credits, store CSV, create Job record, push to Redis queue
3. Response: { job_id, status: "queued" }
4. Celery worker picks up job → runs pipeline.process_batch()
5. All 8 layers run concurrently via asyncio.gather
6. Results written to job_results table + enriched CSV generated
7. Job status → "complete", credits deducted
8. Frontend polls GET /api/v1/jobs/{id} every 3s
9. On complete: show results, enable download
```

### How burn score works
```
Upload: emails → SHA-256 hash → bulk INSERT into burn_pool
Lookup: SELECT COUNT(DISTINCT user_id) WHERE email_hash IN (...) AND uploaded_at > NOW()-90d
Score:  0-100 normalised, capped at 100
Tags:   0-20=Fresh, 21-50=Warm, 51-80=Burned, 81-100=Torched
GDPR:   Only hashes stored. Original emails never in burn pool.
```

### How Paystack webhook flow works
```
1. User clicks upgrade → POST /api/v1/billing/initialize → Paystack checkout URL
2. User pays on Paystack hosted page
3. Paystack fires webhook to POST /api/v1/billing/webhook
4. FastAPI verifies HMAC signature (sha512 of raw body using PAYSTACK_WEBHOOK_SECRET)
5. Event: charge.success → activate plan, set credits, create billing_event record
6. Event: subscription.disable → downgrade to free tier
7. Event: invoice.payment_failed → email alert, 3-day grace period
```

---

## Open Questions / To Decide

- [ ] **File storage:** Local filesystem (UPLOAD_DIR) works fine on Railway but files lost on redeploy.
  Options: (a) Railway Volume (persistent), (b) Cloudflare R2 (cheap S3-compatible).
  Decision needed before Week 2. Leaning toward Railway Volume for simplicity.

- [ ] **Job result storage:** Store full enriched rows in `job_results` table OR just store the CSV?
  Current design stores both (DB rows for querying + CSV for download).
  May be expensive at scale. Revisit at 500+ active users.

- [ ] **Domain blacklist checker:** MXToolbox API (rate limited free tier) vs Spamhaus DNS queries.
  Spamhaus DNS is free and fast — preferred. Need to test at scale.

- [ ] **Marketplace listing expiry:** Currently set to 7 days. Too short? Too long?
  Community trades happen fast. 7 days feels right but confirm after launch.

- [ ] **Admin dashboard:** Basic stats view needed before launch (user count, job count, revenue).
  Simple Jinja page, no fancy framework. When to build — Week 4 or Month 2?

---

## Key Numbers to Remember

- 1 credit = 1 email processed (all layers)
- Free tier: 500 credits/mo
- Burn score pool: 90-day rolling window
- WHOIS cache TTL: 30 days per domain
- Celery marketplace matcher: runs every 15 minutes
- Job files auto-deleted: uploads after 24h, outputs after 72h
- Refresh token expiry: 30 days
- Access token expiry: 15 minutes
- Password reset token expiry: 1 hour
- Email verification token expiry: 24 hours

---

## Next Action

Continue Week 1. Next files to write in order:
1. `app/static/js/app.js` — global Alpine stores, toast, modal, apiFetch
2. `app/static/css/app.css` — base styles
3. `app/templates/auth/signup.html`
4. `app/templates/auth/forgot_password.html`
5. `app/templates/auth/reset_password.html`
6. `app/templates/auth/verify_email.html`
7. `app/main.py`
8. `alembic.ini` + `migrations/env.py` + `001_initial_schema.py`
9. `Dockerfile` + `railway.toml` + `.env.example`

---

## UI Flows — Fully Designed (Reference for Template Writing)

All screens have been fully designed and are ready to be written as Jinja2 templates.
See SKILL.md → "UI Screens & Flow Specifications" for the complete per-screen spec.

### Screens designed (ready to write as Jinja2 templates):

**Auth:**
- login.html ✅ (written in Week 1 build)
- signup.html — needs confirm password + live strength validator + live match validator
- verify_email.html
- forgot_password.html
- reset_password.html (3 states: form / success / expired)

**Post-auth:**
- onboarding.html — 5-step checklist, auto-dismisses when steps 1-3 done
- dashboard.html — stats, 6-state upload zone, recent jobs, processing progress
- job_list.html — full history table, auto-polls active jobs every 5s
- job_detail.html — 2-col layout: breakdown + Fresh Only panel + trade prompt
- marketplace.html — plan-gated, active listings, completed trades, submit modal
- billing.html — plan grid, credit packs, Paystack checkout flow
- api_keys.html — plan-gated, key list, create modal (raw key shown once)
- notifications.html — list with unread states, preferences sidebar
- settings.html — 4 sections in 2-col grid
- profile.html — initials avatar, sidebar, account status

**Errors:**
- 404.html, 500.html, 403.html, session_expired.html

### Key JS behaviours to implement in app.js:

```javascript
// Password strength (signup page)
checkPw(val) — checks 4 rules, fills bars, updates label + input class

// Confirm password (signup page)
checkMatch(val) — compares to pw field, shows match/no-match

// Auth guard (dashboard layout)
Runs on every protected page — attempts silent refresh via httpOnly cookie
Redirects to /auth/login if refresh fails

// Upload zone
Drag events: dragover, dragleave, drop
States: default → drag → uploading (progress) → complete / error
Credit preflight: check row count vs user credits before submitting

// Job polling (job_list.html, dashboard.html)
If any job has status queued/processing: poll GET /api/v1/jobs every 5s
Update DOM in-place (status pill, progress bar, row stats)
Stop polling when all jobs are complete/failed

// Fresh Only live preview (job_detail.html)
On toggle change: recalculate filtered count from job summary JSON
Show "After filtering: X,XXX emails — removed Y,YYY (Z%)"
Uses data already on the page (no extra API call)

// Paystack checkout
POST /api/v1/billing/initialize → get checkout_url → window.location.href = checkout_url
Callback: GET /billing/callback?reference=xxx → server verifies → redirect to /billing
```

### Next files to write in template order:
1. app/static/js/app.js — toast store, modal store, apiFetch, auth guard, poll helper
2. app/static/css/app.css — base overrides, pill classes, form states
3. app/templates/auth/signup.html — with full password validator
4. app/templates/auth/forgot_password.html
5. app/templates/auth/reset_password.html
6. app/templates/auth/verify_email.html
7. app/templates/dashboard_layout.html — authenticated shell with sidebar
8. app/templates/dashboard/dashboard.html
9. app/templates/dashboard/job_list.html
10. app/templates/dashboard/job_detail.html
11. app/templates/marketplace/marketplace.html
12. app/templates/billing/billing.html
13. app/templates/api_keys/api_keys.html
14. app/templates/notifications/notifications.html
15. app/templates/settings/settings.html
16. app/templates/profile/profile.html
17. app/templates/errors/404.html, 500.html, 403.html
18. app/templates/onboarding/onboarding.html
