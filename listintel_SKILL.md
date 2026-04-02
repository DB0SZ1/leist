---
name: listintel
description: >
  Full production-grade build skill for List Intel — a cold email list intelligence SaaS.
  Use this skill for ANY task related to building, extending, debugging, or deploying List Intel.
  Triggers on: "build the auth system", "add the burn score feature", "write the processing pipeline",
  "scaffold the project", "add a new route", "write the Paystack integration", "build the dashboard",
  "add a new Jinja template", "write the Celery task", "create a new model", or any feature/file
  reference that belongs to the List Intel codebase. This skill contains the complete architecture,
  design decisions, conventions, and build sequence. Always read this before writing any List Intel code.
---

# List Intel — Build Skill

## What Is List Intel

A cold email list intelligence SaaS. Users upload a CSV of email addresses. The system runs
8 intelligence layers in parallel server-side and returns an enriched CSV with additional columns.

Monetisation: free tier (500 credits/mo) → paid tiers ($10–$99/mo) via Paystack → paid API for
tool integrations. Launch strategy: free for 1–2 months to seed the burn score pool, then flip
to paid. Built in Nigeria, USD pricing, global audience.

**Phase 1 ships everything except SMTP verification.** SMTP is Phase 2, added when revenue supports
clean IP infrastructure or wholesale API (MillionVerifier at ~$0.00008/email).

---

## Stack — Non-Negotiable

| Layer | Choice | Reason |
|---|---|---|
| Language | Python 3.12 | FastAPI ecosystem |
| Web framework | FastAPI | async, auto-docs, typed |
| Templates | Jinja2 (server-rendered) | no frontend framework, ships faster |
| CSS | Tailwind CDN + custom | no build step |
| JS | Alpine.js (CDN) + vanilla | interactivity without React |
| Database | PostgreSQL 15 | Railway |
| Cache / Queue broker | Redis 7 | Railway |
| Background workers | Celery 5 | async job processing |
| Payments | Paystack | Nigerian-founded, USD+NGN, webhooks |
| Transactional email | Resend | simple API, free tier 3k/mo |
| WHOIS | python-whois | free, cached aggressively in Redis |
| DNS lookups | aiodns + dnspython | async batch MX resolution |
| ORM | SQLAlchemy 2.0 (async) | type-safe, async session |
| Migrations | Alembic | schema versioning |
| Auth | Custom JWT (python-jose) | no third-party auth cost |
| Password hashing | passlib[bcrypt] | industry standard |
| HTTP client | httpx | async, used for Paystack calls |
| Inter-LLM messaging | MessagePack (msgpack-python) | binary, typed, faster than JSON |
| Validation | Pydantic v2 | FastAPI native |
| Hosting | Railway | backend + PostgreSQL + Redis + Celery |
| Frontend hosting | Railway (same service) | Jinja templates served by FastAPI |

**MessagePack over JSON**: All internal service-to-service messages, Celery task payloads, and
LLM-to-LLM communication use MessagePack. Faster serialisation, smaller payloads, typed binary.
Never use raw JSON dicts for inter-service communication. Use `app/core/msgpack.py` helpers.

---

## Folder Structure

```
listintel/
├── app/
│   ├── main.py                  # FastAPI app factory, router registration, lifespan
│   ├── config.py                # Pydantic Settings, all env vars, single source of truth
│   │
│   ├── core/                    # Shared infrastructure — never feature-specific
│   │   ├── __init__.py
│   │   ├── database.py          # Async SQLAlchemy engine, get_db dependency
│   │   ├── redis.py             # Redis client, get_redis dependency
│   │   ├── security.py          # JWT encode/decode, bcrypt hash/verify, token refresh
│   │   ├── dependencies.py      # get_current_user, require_plan, require_api_key
│   │   ├── exceptions.py        # AppException base, all typed exceptions, global handlers
│   │   ├── responses.py         # Standardised API response envelope
│   │   ├── msgpack.py           # MessagePack encode/decode helpers, typed wrappers
│   │   ├── rate_limit.py        # Redis sliding-window rate limiter
│   │   └── logging.py           # Structured JSON logging config
│   │
│   ├── features/                # ONE folder per feature — fully self-contained
│   │   │
│   │   ├── auth/
│   │   │   ├── __init__.py
│   │   │   ├── router.py        # POST /api/v1/auth/*
│   │   │   ├── service.py       # register, login, logout, refresh, reset logic
│   │   │   ├── schemas.py       # RegisterRequest, LoginRequest, TokenPair, UserOut
│   │   │   ├── models.py        # User ORM model
│   │   │   └── templates/
│   │   │       ├── login.html
│   │   │       ├── signup.html
│   │   │       ├── forgot_password.html
│   │   │       └── reset_password.html
│   │   │
│   │   ├── billing/
│   │   │   ├── __init__.py
│   │   │   ├── router.py        # POST /api/v1/billing/*
│   │   │   ├── service.py       # Paystack API calls, plan activation, credit logic
│   │   │   ├── schemas.py       # PlanOut, CreditPurchaseRequest, WebhookPayload
│   │   │   ├── models.py        # Subscription, BillingEvent ORM models
│   │   │   ├── webhook.py       # Webhook handlers: charge.success, subscription.disable etc.
│   │   │   └── paystack/
│   │   │       ├── __init__.py
│   │   │       ├── client.py    # httpx async Paystack client, all API calls
│   │   │       └── plans.py     # Plan definitions: codes, amounts, credit allowances
│   │   │
│   │   ├── jobs/
│   │   │   ├── __init__.py
│   │   │   ├── router.py        # POST/GET /api/v1/jobs/*
│   │   │   ├── service.py       # Create job, poll status, fetch results, deduct credits
│   │   │   ├── schemas.py       # JobCreate, JobOut, JobStatus, JobSummary
│   │   │   ├── models.py        # Job, JobResult ORM models
│   │   │   └── templates/
│   │   │       ├── dashboard.html
│   │   │       ├── job_list.html
│   │   │       └── job_detail.html
│   │   │
│   │   ├── processing/          # Pure processing engine — no HTTP, no DB writes (Celery only)
│   │   │   ├── __init__.py
│   │   │   ├── pipeline.py      # Orchestrator: runs all layers concurrently via asyncio.gather
│   │   │   ├── csv_reader.py    # Parse CSV, detect email column, validate structure
│   │   │   ├── csv_writer.py    # Build enriched output CSV from results
│   │   │   └── layers/
│   │   │       ├── __init__.py
│   │   │       ├── base.py      # BaseLayer abstract class, standard result shape
│   │   │       ├── syntax.py    # Syntax + disposable + role detection
│   │   │       ├── mx_check.py  # Async DNS/MX lookup (aiodns)
│   │   │       ├── spam_filter.py  # MX pattern → filter provider (Mimecast etc.)
│   │   │       ├── infra.py     # MX pattern → infra provider (GWS/M365/SMTP)
│   │   │       ├── domain_age.py   # python-whois + Redis cache (30d TTL)
│   │   │       ├── catchall.py  # Catchall heuristic detection
│   │   │       ├── burn_score.py   # Bulk SHA-256 hash lookup in burn_pool
│   │   │       └── bounce_score.py # Bounce history lookup
│   │   │       └── spam_copy.py    # AI spam copy checker (OpenRouter free model)
│   │   │
│   │   ├── burn/
│   │   │   ├── __init__.py
│   │   │   ├── service.py       # Hash emails, bulk INSERT to pool, bulk score query
│   │   │   └── models.py        # BurnPool ORM model
│   │   │
│   │   ├── bounces/
│   │   │   ├── __init__.py
│   │   │   ├── router.py        # POST /api/v1/bounces
│   │   │   ├── service.py       # Accept bounce submissions, store against hash
│   │   │   ├── schemas.py       # BounceSubmit, BounceRow
│   │   │   └── models.py        # BounceEvent ORM model
│   │   │
│   │   ├── marketplace/
│   │   │   ├── __init__.py
│   │   │   ├── router.py        # POST/GET /api/v1/marketplace/*
│   │   │   ├── service.py       # Offer, accept, decline, withdraw, fee deduction
│   │   │   ├── matcher.py       # Matching algorithm — called by Celery beat task
│   │   │   ├── schemas.py       # ListingCreate, TradeOut, OfferOut
│   │   │   ├── models.py        # Listing, Trade, MarketplaceFee ORM models
│   │   │   └── templates/
│   │   │       └── marketplace.html
│   │   │
│   │   ├── api_keys/
│   │   │   ├── __init__.py
│   │   │   ├── router.py        # GET/POST/DELETE /api/v1/keys/*
│   │   │   ├── service.py       # Generate key, hash for storage, validate, revoke
│   │   │   ├── schemas.py       # KeyCreate, KeyOut, KeyUsageStats
│   │   │   ├── models.py        # APIKey ORM model
│   │   │   └── templates/
│   │   │       └── api_keys.html
│   │   │
│   │   └── exports/
│   │       ├── __init__.py
│   │       ├── router.py        # GET /api/v1/jobs/{id}/download
│   │       ├── service.py       # Apply Fresh Only filters server-side, stream CSV
│   │       ├── schemas.py       # ExportPreset, FilterConfig
│   │       └── models.py        # ExportPreset ORM model
│   │
│   ├── workers/
│   │   ├── __init__.py
│   │   ├── celery_app.py        # Celery instance — Redis broker + backend
│   │   └── tasks/
│   │       ├── process_job.py   # @celery_app.task — runs processing pipeline
│   │       └── marketplace_match.py  # @celery_app.on_after_finalize — 15min beat
│   │
│   ├── templates/               # Shared Jinja2 base templates
│   │   ├── base.html            # Root layout: head, nav, toast container, Alpine init
│   │   ├── dashboard_layout.html  # Authenticated layout with sidebar
│   │   └── components/
│   │       ├── toast.html       # Toast notification component
│   │       ├── modal.html       # Reusable modal component
│   │       ├── upload_zone.html # CSV drag-and-drop upload
│   │       └── progress_bar.html  # Job progress indicator
│   │
│   └── static/
│       ├── css/
│       │   └── app.css          # Custom CSS on top of Tailwind CDN
│       └── js/
│           ├── app.js           # Global Alpine.js store, toast manager
│           ├── upload.js        # Upload zone logic
│           └── poll.js          # Job status polling (SSE or setTimeout)
│
├── migrations/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── 001_initial_schema.py
│
├── tests/
│   ├── conftest.py              # Test DB, async test client, fixtures
│   ├── test_auth.py
│   ├── test_billing.py
│   ├── test_jobs.py
│   └── test_processing.py
│
├── scripts/
│   └── seed_signatures.py       # Populate spam_filter + infra JSON on first deploy
│
├── signatures/                  # Pattern databases — update without touching code
│   ├── spam_filters.json        # MX string patterns → filter provider mapping
│   ├── infra_providers.json     # MX string patterns → infra provider mapping
│   └── disposable_domains.txt   # One domain per line blocklist
│
├── .env                         # NEVER committed
├── .env.example                 # Committed — documents every required var
├── .env.test                    # Test environment overrides
├── alembic.ini
├── requirements.txt
├── Dockerfile
├── railway.toml                 # Two services: api + worker
├── Procfile                     # Alternative Railway start commands
└── .gitignore
```

---

## Core Design Principles

### 1. Standard API Response Envelope

Every API response — success or error — uses the same envelope. Never return raw dicts.

```python
# app/core/responses.py
from pydantic import BaseModel
from typing import Any, Optional

class APIResponse(BaseModel):
    success: bool
    message: str
    data: Optional[Any] = None
    errors: Optional[list[str]] = None
    code: Optional[str] = None  # machine-readable error code

def ok(data: Any = None, message: str = "Success") -> APIResponse:
    return APIResponse(success=True, message=message, data=data)

def fail(message: str, errors: list[str] = None, code: str = None) -> APIResponse:
    return APIResponse(success=False, message=message, errors=errors, code=code)
```

All routers return `JSONResponse(content=ok(data).model_dump(), status_code=200)` or
`JSONResponse(content=fail(...).model_dump(), status_code=4xx)`.

### 2. Typed Exception System

Never raise generic `Exception`. Every error has a typed class with HTTP status, message, and
machine-readable code. The global handler converts them to the standard envelope.

```python
# app/core/exceptions.py

class AppException(Exception):
    status_code: int = 500
    message: str = "Internal server error"
    code: str = "INTERNAL_ERROR"

    def __init__(self, message: str = None, code: str = None):
        self.message = message or self.__class__.message
        self.code = code or self.__class__.code

class AuthException(AppException):
    status_code = 401
    message = "Authentication required"
    code = "AUTH_REQUIRED"

class ForbiddenException(AppException):
    status_code = 403
    message = "Access denied"
    code = "FORBIDDEN"

class NotFoundException(AppException):
    status_code = 404
    message = "Resource not found"
    code = "NOT_FOUND"

class InsufficientCreditsException(AppException):
    status_code = 402
    message = "Insufficient credits"
    code = "INSUFFICIENT_CREDITS"

class PlanLimitException(AppException):
    status_code = 403
    message = "Plan limit reached"
    code = "PLAN_LIMIT"

class ValidationException(AppException):
    status_code = 422
    message = "Validation failed"
    code = "VALIDATION_ERROR"

class PaystackException(AppException):
    status_code = 502
    message = "Payment provider error"
    code = "PAYSTACK_ERROR"

# Register in main.py:
# @app.exception_handler(AppException)
# async def app_exception_handler(request, exc):
#     return JSONResponse(
#         status_code=exc.status_code,
#         content=fail(exc.message, code=exc.code).model_dump()
#     )
```

### 3. MessagePack for Inter-Service Communication

All Celery task payloads and any LLM-to-LLM messages use MessagePack, not JSON.

```python
# app/core/msgpack.py
import msgpack
from typing import Any

def encode(data: Any) -> bytes:
    return msgpack.packb(data, use_bin_type=True)

def decode(data: bytes) -> Any:
    return msgpack.unpackb(data, raw=False)

# Celery task example:
# process_job.apply_async(args=[encode({"job_id": str(job.id), "user_id": str(user.id)})])
# Inside task: payload = decode(raw_bytes)
```

Configure Celery to use MessagePack serialiser:
```python
# workers/celery_app.py
app.conf.update(
    task_serializer='msgpack',
    result_serializer='msgpack',
    accept_content=['msgpack'],
)
```

Register msgpack with Celery:
```python
from kombu.serialization import register
register('msgpack', encode, decode, content_type='application/x-msgpack')
```

### 4. Authentication — Full JWT Flow

**Access token**: JWT, 15 min expiry, stored in memory (JS variable), sent as `Authorization: Bearer`.
**Refresh token**: opaque UUID stored in PostgreSQL, sent as `httpOnly Secure SameSite=Strict` cookie.
**Never** store tokens in localStorage.

```python
# Dependency for protected routes:
async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    payload = decode_access_token(token)  # raises AuthException on failure
    user = await get_user_by_id(db, payload["sub"])
    if not user or not user.is_active:
        raise AuthException("User not found or inactive")
    if not user.email_verified:
        raise ForbiddenException("Email not verified", code="EMAIL_NOT_VERIFIED")
    return user

# Plan guard:
def require_plan(*plans: str):
    async def check(user: User = Depends(get_current_user)):
        if user.plan not in plans:
            raise PlanLimitException(f"This feature requires one of: {plans}")
        return user
    return check

# API key auth (for external integrations):
async def require_api_key(
    x_api_key: str = Header(...),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis)
) -> User:
    hashed = sha256(x_api_key)
    key = await get_key_by_hash(db, hashed)
    if not key or key.is_revoked:
        raise AuthException("Invalid API key", code="INVALID_API_KEY")
    await check_rate_limit(redis, f"apikey:{key.id}", key.user.plan)
    await update_key_last_used(db, key.id)
    return key.user
```

### 5. Toast + Modal System (Jinja + Alpine.js)

All user-facing feedback goes through a unified toast/modal system. Never use `alert()`.

```html
<!-- templates/base.html — Alpine global store -->
<div x-data="toastStore()" x-init="init()">
  <!-- Toast container (top-right) -->
  <div class="fixed top-4 right-4 z-50 flex flex-col gap-2" id="toast-container">
    <template x-for="toast in toasts" :key="toast.id">
      <div
        x-show="toast.visible"
        x-transition:enter="transition ease-out duration-200"
        x-transition:leave="transition ease-in duration-150"
        :class="toastClass(toast.type)"
        class="flex items-center gap-3 px-4 py-3 rounded-lg shadow-lg min-w-64 max-w-sm"
      >
        <span x-text="toast.icon" class="text-lg"></span>
        <div class="flex-1">
          <p class="font-semibold text-sm" x-text="toast.title"></p>
          <p class="text-xs opacity-80" x-text="toast.message" x-show="toast.message"></p>
        </div>
        <button @click="dismiss(toast.id)" class="opacity-60 hover:opacity-100">✕</button>
      </div>
    </template>
  </div>
</div>

<script>
function toastStore() {
  return {
    toasts: [],
    init() { window.$toast = this; },
    show(type, title, message = '', duration = 4000) {
      const id = Date.now();
      const icons = { success: '✅', error: '❌', warning: '⚠️', info: 'ℹ️' };
      this.toasts.push({ id, type, title, message, icon: icons[type], visible: true });
      setTimeout(() => this.dismiss(id), duration);
    },
    dismiss(id) {
      const t = this.toasts.find(t => t.id === id);
      if (t) { t.visible = false; setTimeout(() => this.toasts = this.toasts.filter(t => t.id !== id), 200); }
    },
    toastClass(type) {
      return { success: 'bg-green-50 border border-green-200 text-green-900',
               error: 'bg-red-50 border border-red-200 text-red-900',
               warning: 'bg-yellow-50 border border-yellow-200 text-yellow-900',
               info: 'bg-blue-50 border border-blue-200 text-blue-900' }[type];
    }
  };
}

// Usage anywhere in JS:
// $toast.show('success', 'Upload complete', '12,400 emails processed');
// $toast.show('error', 'Upload failed', 'Please check your CSV format');
// $toast.show('warning', 'Credits low', 'You have 50 credits remaining');

// After every fetch call:
async function apiFetch(url, options = {}) {
  const res = await fetch(url, {
    ...options,
    headers: { 'Authorization': `Bearer ${getAccessToken()}`, ...options.headers }
  });
  const data = await res.json();
  if (!data.success) {
    $toast.show('error', data.message || 'Something went wrong');
    throw new Error(data.code || 'API_ERROR');
  }
  return data;
}
</script>
```

Modal component for confirmations:
```html
<!-- templates/components/modal.html -->
<div x-show="$store.modal.open" x-transition class="fixed inset-0 z-50 flex items-center justify-center">
  <div class="absolute inset-0 bg-black/40" @click="$store.modal.close()"></div>
  <div class="relative bg-white rounded-2xl p-6 max-w-md w-full mx-4 shadow-xl">
    <h3 class="font-bold text-lg mb-2" x-text="$store.modal.title"></h3>
    <p class="text-gray-600 text-sm mb-6" x-text="$store.modal.message"></p>
    <div class="flex gap-3 justify-end">
      <button @click="$store.modal.close()" class="btn-ghost">Cancel</button>
      <button @click="$store.modal.confirm()" :class="$store.modal.danger ? 'btn-danger' : 'btn-primary'"
              x-text="$store.modal.confirmLabel"></button>
    </div>
  </div>
</div>
```

### 6. Database Schema

```sql
-- Core tables (Alembic manages these)

CREATE TABLE users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT UNIQUE NOT NULL,
  password_hash TEXT NOT NULL,
  full_name TEXT,
  email_verified BOOLEAN DEFAULT FALSE,
  is_active BOOLEAN DEFAULT TRUE,
  plan TEXT DEFAULT 'free' CHECK (plan IN ('free','starter','growth','pro','agency')),
  credits_remaining INTEGER DEFAULT 500,
  credits_monthly INTEGER DEFAULT 500,
  paystack_customer_id TEXT,
  paystack_subscription_code TEXT,
  billing_cycle_day INTEGER,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE refresh_tokens (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id) ON DELETE CASCADE,
  token_hash TEXT NOT NULL UNIQUE,
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  revoked BOOLEAN DEFAULT FALSE
);

CREATE TABLE jobs (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  status TEXT DEFAULT 'queued' CHECK (status IN ('queued','processing','enriching','complete','failed')),
  total_emails INTEGER,
  processed_emails INTEGER DEFAULT 0,
  input_file_path TEXT,
  output_file_path TEXT,
  summary JSONB,
  error_message TEXT,
  credits_charged INTEGER DEFAULT 0,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  completed_at TIMESTAMPTZ
);

CREATE TABLE job_results (
  id BIGSERIAL PRIMARY KEY,
  job_id UUID REFERENCES jobs(id) ON DELETE CASCADE,
  row_index INTEGER NOT NULL,
  email_hash VARCHAR(64),
  original_email TEXT,
  syntax_valid BOOLEAN,
  syntax_tag TEXT,
  mx_valid BOOLEAN,
  spam_filter TEXT,
  email_infra TEXT,
  domain_age_days INTEGER,
  domain_risk TEXT,
  is_catchall BOOLEAN,
  catchall_confidence TEXT,
  burn_score INTEGER,
  burn_tag TEXT,
  burn_times_seen INTEGER,
  bounce_score INTEGER,
  bounce_type TEXT,
  spam_copy_score REAL,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE burn_pool (
  id BIGSERIAL PRIMARY KEY,
  email_hash VARCHAR(64) NOT NULL,
  domain_hash VARCHAR(64) NOT NULL,
  user_id UUID REFERENCES users(id),
  job_id UUID REFERENCES jobs(id),
  uploaded_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_burn_email_hash ON burn_pool(email_hash);
CREATE INDEX idx_burn_uploaded ON burn_pool(uploaded_at);

CREATE TABLE bounce_events (
  id BIGSERIAL PRIMARY KEY,
  email_hash VARCHAR(64) NOT NULL,
  user_id UUID REFERENCES users(id),
  bounce_type TEXT CHECK (bounce_type IN ('soft','hard')),
  bounced_at TIMESTAMPTZ,
  submitted_at TIMESTAMPTZ DEFAULT NOW()
);
CREATE INDEX idx_bounce_hash ON bounce_events(email_hash);

CREATE TABLE api_keys (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  key_hash VARCHAR(64) UNIQUE NOT NULL,
  label TEXT,
  ip_whitelist TEXT[],
  last_used_at TIMESTAMPTZ,
  is_revoked BOOLEAN DEFAULT FALSE,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE export_presets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  name TEXT NOT NULL,
  filters JSONB NOT NULL,
  is_default BOOLEAN DEFAULT FALSE
);

CREATE TABLE marketplace_listings (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  niche TEXT NOT NULL,
  list_size INTEGER NOT NULL,
  avg_burn_score INTEGER NOT NULL,
  email_hashes JSONB NOT NULL,
  status TEXT DEFAULT 'open' CHECK (status IN ('open','matched','completed','expired')),
  created_at TIMESTAMPTZ DEFAULT NOW(),
  expires_at TIMESTAMPTZ
);

CREATE TABLE marketplace_trades (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  listing_a_id UUID REFERENCES marketplace_listings(id),
  listing_b_id UUID REFERENCES marketplace_listings(id),
  status TEXT DEFAULT 'pending' CHECK (status IN ('pending','confirmed','processing','complete','cancelled')),
  matched_at TIMESTAMPTZ DEFAULT NOW(),
  confirmed_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ
);

CREATE TABLE marketplace_fees (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  trade_id UUID REFERENCES marketplace_trades(id),
  user_id UUID REFERENCES users(id),
  credits_charged INTEGER NOT NULL,
  charged_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE billing_events (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID REFERENCES users(id),
  event_type TEXT NOT NULL,
  paystack_reference TEXT,
  amount INTEGER,
  currency TEXT DEFAULT 'USD',
  payload JSONB,
  created_at TIMESTAMPTZ DEFAULT NOW()
);

CREATE TABLE subscriptions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID UNIQUE REFERENCES users(id),
  plan TEXT NOT NULL,
  status TEXT NOT NULL,
  paystack_subscription_code TEXT,
  current_period_start TIMESTAMPTZ,
  current_period_end TIMESTAMPTZ,
  created_at TIMESTAMPTZ DEFAULT NOW(),
  updated_at TIMESTAMPTZ DEFAULT NOW()
);
```

---

## Processing Pipeline

### Layer Contract

Every layer extends `BaseLayer` and returns a `LayerResult`:

```python
# features/processing/layers/base.py
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any

@dataclass
class LayerResult:
    layer: str
    data: dict[str, Any]
    error: str | None = None

class BaseLayer(ABC):
    name: str

    @abstractmethod
    async def process(self, email: str, domain: str, mx_records: list[str]) -> LayerResult:
        ...
```

### Pipeline Orchestrator

```python
# features/processing/pipeline.py
import asyncio
from .layers import syntax, mx_check, spam_filter, infra, domain_age, catchall, burn_score, bounce_score

LAYERS = [syntax, mx_check, spam_filter, infra, domain_age, catchall, burn_score, bounce_score]

async def process_email(email: str, context: dict) -> dict:
    """Run all layers concurrently. MX results passed to dependent layers."""
    mx_result = await mx_check.MxCheckLayer().process(email, get_domain(email), [])
    mx_records = mx_result.data.get("mx_records", [])

    results = await asyncio.gather(*[
        layer_cls().process(email, get_domain(email), mx_records)
        for layer_cls in [spam_filter, infra, domain_age, catchall, burn_score, bounce_score]
    ], return_exceptions=True)

    merged = {"email": email, **mx_result.data}
    for r in results:
        if isinstance(r, LayerResult):
            merged.update(r.data)
        else:
            # layer failed — log, don't crash the whole row
            log.error(f"Layer error: {r}")
    return merged

async def process_batch(emails: list[str], context: dict) -> list[dict]:
    """Process up to 500 emails concurrently."""
    sem = asyncio.Semaphore(500)
    async def bounded(email):
        async with sem:
            return await process_email(email, context)
    return await asyncio.gather(*[bounded(e) for e in emails])
```

---

## Paystack Integration

```python
# features/billing/paystack/client.py
import httpx
from app.config import settings
from app.core.exceptions import PaystackException

BASE = "https://api.paystack.co"

class PaystackClient:
    def __init__(self):
        self.headers = {
            "Authorization": f"Bearer {settings.PAYSTACK_SECRET_KEY}",
            "Content-Type": "application/json"
        }

    async def initialize_transaction(self, email: str, amount_usd: float, metadata: dict) -> dict:
        amount_kobo = int(amount_usd * 100)  # Paystack uses smallest currency unit
        async with httpx.AsyncClient() as client:
            r = await client.post(f"{BASE}/transaction/initialize",
                headers=self.headers,
                json={"email": email, "amount": amount_kobo, "currency": "USD",
                      "metadata": metadata, "callback_url": settings.PAYSTACK_CALLBACK_URL})
            if r.status_code != 200:
                raise PaystackException(f"Paystack error: {r.text}")
            return r.json()["data"]

    async def verify_transaction(self, reference: str) -> dict:
        async with httpx.AsyncClient() as client:
            r = await client.get(f"{BASE}/transaction/verify/{reference}", headers=self.headers)
            if r.status_code != 200:
                raise PaystackException(f"Verification failed: {r.text}")
            return r.json()["data"]

    async def create_subscription(self, customer_code: str, plan_code: str) -> dict:
        async with httpx.AsyncClient() as client:
            r = await client.post(f"{BASE}/subscription",
                headers=self.headers,
                json={"customer": customer_code, "plan": plan_code})
            return r.json()["data"]

    async def disable_subscription(self, subscription_code: str, token: str) -> bool:
        async with httpx.AsyncClient() as client:
            r = await client.post(f"{BASE}/subscription/disable",
                headers=self.headers,
                json={"code": subscription_code, "token": token})
            return r.json()["status"]

# Webhook HMAC verification:
import hmac, hashlib
def verify_webhook(payload: bytes, signature: str) -> bool:
    expected = hmac.new(settings.PAYSTACK_WEBHOOK_SECRET.encode(), payload, hashlib.sha512).hexdigest()
    return hmac.compare_digest(expected, signature)
```

### Plan Definitions

```python
# features/billing/paystack/plans.py
from dataclasses import dataclass

@dataclass
class Plan:
    name: str
    paystack_plan_code: str
    monthly_usd: int
    credits_monthly: int
    features: list[str]

PLANS = {
    "free":    Plan("Free",    "",            0,   500,     ["syntax","mx","spam_filter","infra"]),
    "starter": Plan("Starter", "PLN_starter", 10,  25000,   ["burn_score","fresh_only"]),
    "growth":  Plan("Growth",  "PLN_growth",  49,  100000,  ["marketplace","bounce_history"]),
    "pro":     Plan("Pro",     "PLN_pro",     99,  500000,  ["api_access","10_seats"]),
    "agency":  Plan("Agency",  "PLN_agency",  249, 0,       ["unlimited","white_label"]),
}

CREDIT_PACKS = [
    {"credits": 10_000,    "usd": 9},
    {"credits": 50_000,    "usd": 35},
    {"credits": 250_000,   "usd": 129},
    {"credits": 1_000_000, "usd": 389},
    {"credits": 5_000_000, "usd": 1499},
]
```

---

## Burn Score Implementation

```python
# features/burn/service.py
import hashlib
from sqlalchemy import select, func, text
from app.core.database import AsyncSession

def hash_email(email: str) -> str:
    return hashlib.sha256(email.lower().strip().encode()).hexdigest()

def hash_domain(domain: str) -> str:
    return hashlib.sha256(domain.lower().strip().encode()).hexdigest()

async def bulk_insert_pool(db: AsyncSession, emails: list[str], user_id: str, job_id: str):
    rows = [{"email_hash": hash_email(e), "domain_hash": hash_domain(e.split("@")[1]),
             "user_id": user_id, "job_id": job_id} for e in emails]
    await db.execute(text("""
        INSERT INTO burn_pool (email_hash, domain_hash, user_id, job_id)
        VALUES (:email_hash, :domain_hash, :user_id, :job_id)
        ON CONFLICT DO NOTHING
    """), rows)
    await db.commit()

async def bulk_get_scores(db: AsyncSession, emails: list[str]) -> dict[str, dict]:
    hashes = [hash_email(e) for e in emails]
    result = await db.execute(text("""
        SELECT email_hash,
               COUNT(DISTINCT user_id) AS burn_score,
               COUNT(*) AS total_appearances,
               MIN(uploaded_at) AS first_seen
        FROM burn_pool
        WHERE email_hash = ANY(:hashes)
        AND uploaded_at > NOW() - INTERVAL '90 days'
        GROUP BY email_hash
    """), {"hashes": hashes})
    rows = result.fetchall()
    scores = {r.email_hash: {
        "burn_score": min(int(r.burn_score * 1.5), 100),  # normalise to 0-100
        "times_seen": r.total_appearances,
        "first_seen": r.first_seen.isoformat() if r.first_seen else None,
        "burn_tag": score_to_tag(min(int(r.burn_score * 1.5), 100))
    } for r in rows}
    # emails not in pool = score 0
    for e in emails:
        if hash_email(e) not in scores:
            scores[hash_email(e)] = {"burn_score": 0, "times_seen": 0, "first_seen": None, "burn_tag": "Fresh"}
    return scores

def score_to_tag(score: int) -> str:
    if score <= 20: return "Fresh"
    if score <= 50: return "Warm"
    if score <= 80: return "Burned"
    return "Torched"
```

---

## Environment Variables

```bash
# .env.example — commit this, never commit .env

# App
APP_ENV=development          # development | production
SECRET_KEY=                  # 256-bit random secret for JWT signing
FRONTEND_URL=http://localhost:8000

# Database (Railway auto-injects DATABASE_URL in production)
DATABASE_URL=postgresql+asyncpg://user:pass@localhost:5432/listintel

# Redis (Railway auto-injects REDIS_URL in production)
REDIS_URL=redis://localhost:6379

# Celery
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/1

# Paystack
PAYSTACK_SECRET_KEY=sk_live_xxxx
PAYSTACK_PUBLIC_KEY=pk_live_xxxx
PAYSTACK_WEBHOOK_SECRET=      # From Paystack dashboard → Webhooks
PAYSTACK_CALLBACK_URL=https://your-domain.com/billing/callback

# Resend (email)
RESEND_API_KEY=re_xxxx
EMAIL_FROM=noreply@listintel.io

# JWT
ACCESS_TOKEN_EXPIRE_MINUTES=15
REFRESH_TOKEN_EXPIRE_DAYS=30

# File storage (local path or S3-compatible)
UPLOAD_DIR=/tmp/listintel/uploads
OUTPUT_DIR=/tmp/listintel/outputs

# WhoisXML (optional — falls back to python-whois if not set)
WHOIS_API_KEY=

# OpenRouter (for AI spam copy checker)
OPENROUTER_API_KEY=

# Rate limiting defaults
DEFAULT_RATE_LIMIT_PER_MINUTE=60
API_KEY_RATE_LIMIT_PRO=300
API_KEY_RATE_LIMIT_AGENCY=1000
```

---

## Railway Configuration

```toml
# railway.toml
[build]
builder = "dockerfile"

[[services]]
name = "listintel-api"
[services.deploy]
startCommand = "uvicorn app.main:app --host 0.0.0.0 --port $PORT"

[[services]]
name = "listintel-worker"
[services.deploy]
startCommand = "celery -A app.workers.celery_app worker --loglevel=info -Q default,processing,marketplace"

[[services]]
name = "listintel-beat"
[services.deploy]
startCommand = "celery -A app.workers.celery_app beat --loglevel=info"
```

---

## Credit System Rules

1. Credits deducted ONLY on job completion — never on submission or failure.
2. 1 credit = 1 email processed through all layers.
3. Free tier: 500 credits/mo, resets on 1st of each month.
4. Paid tiers: monthly credits reset on billing_cycle_day.
5. Purchased credit packs stack on top and never expire.
6. Job that fails mid-processing: partial credit deduction for rows completed.
7. Pre-flight check before accepting upload: reject if credits_remaining < estimated row count.

```python
async def check_and_reserve_credits(db, user, row_count):
    if user.credits_remaining < row_count:
        raise InsufficientCreditsException(
            f"You need {row_count} credits but have {user.credits_remaining}. "
            f"Purchase more or upgrade your plan."
        )

async def deduct_credits(db, user_id, amount):
    await db.execute(
        text("UPDATE users SET credits_remaining = credits_remaining - :n WHERE id = :id"),
        {"n": amount, "id": user_id}
    )
    await db.commit()
```

---

## Fresh Only Export Filter

Applied server-side before CSV generation. Filters are stored per user as JSON presets.

```python
# features/exports/service.py
DEFAULT_FILTERS = {
    "max_burn_score": 50,
    "exclude_spam_filters": ["Mimecast", "Barracuda"],
    "min_domain_age_days": 180,
    "max_bounce_score": 5,
    "exclude_syntax_tags": ["disposable", "role"],
    "exclude_invalid_mx": True,
}

def apply_fresh_only(results: list[dict], filters: dict) -> tuple[list[dict], dict]:
    kept, removed = [], {"total": 0, "by_reason": {}}
    for row in results:
        reason = None
        if row["burn_score"] > filters["max_burn_score"]: reason = "burn_score"
        elif row["spam_filter"] in filters["exclude_spam_filters"]: reason = "spam_filter"
        elif row.get("domain_age_days", 999) < filters["min_domain_age_days"]: reason = "domain_age"
        elif row["bounce_score"] > filters["max_bounce_score"]: reason = "bounce_score"
        elif row["syntax_tag"] in filters["exclude_syntax_tags"]: reason = "syntax"
        elif filters["exclude_invalid_mx"] and not row["mx_valid"]: reason = "invalid_mx"

        if reason:
            removed["total"] += 1
            removed["by_reason"][reason] = removed["by_reason"].get(reason, 0) + 1
        else:
            kept.append(row)
    return kept, removed
```

---

## Jinja2 Template Conventions

- All templates extend `base.html`.
- Auth-protected pages extend `dashboard_layout.html`.
- Use `{% block content %}` for page content.
- Use `{% block scripts %}` for page-specific JS at bottom of body.
- Flash messages go through the Alpine toast system, not Flask-style flash.
- Forms use `hx-post` (htmx) OR standard fetch with `apiFetch()` helper.
- Every form submit button shows a loading spinner and disables on click.
- CSRF: use a hidden `csrf_token` field on all forms (generate in FastAPI, verify in middleware).

```html
<!-- templates/base.html structure -->
<!DOCTYPE html>
<html lang="en" x-data>
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>{% block title %}List Intel{% endblock %}</title>
  <script src="https://cdn.tailwindcss.com"></script>
  <script defer src="https://cdn.jsdelivr.net/npm/alpinejs@3/dist/cdn.min.js"></script>
  <link rel="stylesheet" href="/static/css/app.css">
</head>
<body class="bg-[#f2f1ec] text-[#172617] font-sans" x-data="toastStore()" x-init="init()">
  {% include "components/toast.html" %}
  {% include "components/modal.html" %}
  {% block nav %}{% include "components/nav.html" %}{% endblock %}
  <main>{% block content %}{% endblock %}</main>
  <script src="/static/js/app.js"></script>
  {% block scripts %}{% endblock %}
</body>
</html>
```

---

## API Versioning

All API endpoints are prefixed `/api/v1/`. Jinja-rendered page routes have no prefix.

```python
# app/main.py
from fastapi import FastAPI
from app.features.auth.router import router as auth_router
from app.features.jobs.router import router as jobs_router
from app.features.billing.router import router as billing_router
from app.features.bounces.router import router as bounces_router
from app.features.marketplace.router import router as marketplace_router
from app.features.api_keys.router import router as keys_router
from app.features.exports.router import router as exports_router

app = FastAPI(title="List Intel API", version="1.0.0")

# API routes (JSON, used by external frontends + API key clients)
app.include_router(auth_router,        prefix="/api/v1/auth",        tags=["Auth"])
app.include_router(jobs_router,        prefix="/api/v1/jobs",         tags=["Jobs"])
app.include_router(billing_router,     prefix="/api/v1/billing",      tags=["Billing"])
app.include_router(bounces_router,     prefix="/api/v1/bounces",      tags=["Bounces"])
app.include_router(marketplace_router, prefix="/api/v1/marketplace",  tags=["Marketplace"])
app.include_router(keys_router,        prefix="/api/v1/keys",         tags=["API Keys"])
app.include_router(exports_router,     prefix="/api/v1/exports",      tags=["Exports"])

# Page routes (Jinja2, for the web UI)
# These return HTML, not JSON
from app.features.jobs.router import page_router as jobs_pages
app.include_router(jobs_pages)  # /dashboard, /jobs, /jobs/{id}
```

---

## Error Handling Checklist

For every new endpoint, verify:

- [ ] Auth guard applied (`Depends(get_current_user)` or `Depends(require_api_key)`)
- [ ] Plan guard applied where feature is tier-restricted
- [ ] Credit check before job creation
- [ ] Input validated via Pydantic schema
- [ ] Database errors caught and wrapped in `AppException`
- [ ] External API calls (Paystack, Resend) wrapped in try/except → `PaystackException`
- [ ] All exceptions produce standard `APIResponse` envelope
- [ ] For Jinja routes: errors redirect with toast message, not 500 page
- [ ] Celery tasks: failures update job.status = 'failed', set error_message, do NOT deduct credits

---

## Build Sequence

Follow this exact order. Do not skip ahead.

```
Week 1:
  [x] Project scaffold: main.py, config.py, core/ modules
  [x] Database models + Alembic initial migration
  [x] Auth system: register, login, logout, refresh, verify email, forgot/reset password
  [x] Base templates: base.html, dashboard_layout.html, nav, toast, modal components
  [x] Auth pages: login.html, signup.html, forgot_password.html, reset_password.html

Week 2:
  [x] Paystack billing: plans, initialize, webhook, credit deduction
  [x] Billing pages: pricing.html, billing_portal.html
  [x] Job creation: CSV upload, validation, credit check, queue
  [x] Processing layers: syntax, mx_check, spam_filter, infra, domain_age, catchall
  [x] Celery worker + process_job task

Week 3:
  [x] Burn score: hash pool, bulk insert, bulk lookup
  [x] Bounce history: submission endpoint, lookup layer
  [x] Job results: storage, status polling, enriched CSV generation
  [x] Dashboard: upload zone, job progress, results summary, job history

Week 4:
  [x] Fresh Only export: filter presets, server-side filtering, CSV download
  [x] API keys: generation, hashing, rate limiting, usage tracking
  [x] API routes: /api/v1/check, /api/v1/bulk, /api/v1/score, /api/v1/bounces

Month 2:
  [x] Marketplace: listings, matching algorithm, trade flow, fee deduction
  [x] AI spam copy checker layer (OpenRouter free model)
  [x] Admin dashboard: user list, job stats, revenue overview
  [x] Performance: query optimisation, index review, Redis caching audit
```

---

## Key Conventions

- All UUIDs, never integer IDs for user-facing resources.
- All timestamps in UTC, stored as TIMESTAMPTZ.
- Email addresses lowercased and stripped before any operation.
- SHA-256 hashes computed from `email.lower().strip()`.
- Never log plaintext emails in production — log hashes only.
- Celery tasks always idempotent — safe to retry.
- All file paths relative to `UPLOAD_DIR` / `OUTPUT_DIR` env vars.
- Uploaded CSVs auto-deleted after 24h via Celery beat task.
- Output CSVs auto-deleted after 72h.
- All monetary amounts stored as integers (cents/kobo), never floats.

---

## References

See the full conversation history and product specification in the session transcript for:
- Complete pricing tiers and credit allowances per plan
- Full Paystack webhook event list and handlers
- Marketplace matching algorithm specification
- Domain age WHOIS caching strategy
- Burn score network effect analysis
- Go-to-market strategy (WhatsApp community drop sequence)
- List Source (Tool 2) — future product, design backend to accommodate shared users table

---

## UI Flows & Screen Specifications

Every screen below maps directly to a Jinja2 template file. Read this section before
writing any template. All screens use the same design system — see Design System section.

---

### Design System — Quick Reference

```
Background:  #f2f1ec   (warm off-white — body bg)
White:       #ffffff   (cards, sidebar, inputs)
Dark:        #172617   (headings, nav text)
Accent:      #2a5426   (forest green — primary CTA, active nav, links)
Accent2:     #3d7a36   (hover state for accent)
Yellow:      #cce836   (underline accent, best-value badges)
Muted:       #6a796a   (secondary text, placeholders, labels)
Border:      #d8d8cf   (all borders — cards, inputs, dividers)
Surface:     #fafaf6   (table row hover, sidebar bg, toolbar bg)
Font:        Bricolage Grotesque (Google Fonts, weights 400/500/600/700/800)
Border-radius cards: 12px–14px
Border-radius inputs: 8px
Border-radius pills:  3px (status tags) or 100px (rounded badges)
```

**Status pill colours (use exactly these):**
- Valid / Safe / Fresh / Complete → `bg:#d4eecf text:#1b6015`
- Invalid / Burned / Torched / Failed → `bg:#fcd8d8 text:#b31c1c`
- Role / Warning / Warm / Pending → `bg:#fde3c0 text:#964800`
- Infra / Info / Processing → `bg:#d6e8fc text:#1a4c9a`
- Catchall / Yellow → `bg:#fdf5c0 text:#786500`
- Plan badge → `bg:rgba(42,84,38,.1) color:#2a5426`

---

### Screen 1 — Login (`templates/auth/login.html`)

**Route:** `GET /auth/login`
**Access:** Public. Redirect to `/dashboard` if already authenticated.

**Layout:** Centered card (max-width 380px) on `#f2f1ec` background.
Logo mark + wordmark centred above card. No nav bar.

**Fields:**
- Email (type=email, autocomplete=email)
- Password (type=password, autocomplete=current-password)
- "Forgot password?" link (right-aligned, below password field)

**Submit behaviour:**
1. Disable button, show spinner inside button text
2. `POST /api/v1/auth/login` with JSON body
3. On success → store `data.access_token` in `window.__li_token`, redirect to `/dashboard`
4. On `EMAIL_NOT_VERIFIED` error code → show toast warning + link to resend verification
5. On `INVALID_CREDENTIALS` → shake animation on card, red border on both inputs, error toast
6. Re-enable button on any failure

**Below card:** "Don't have an account? Sign up free" — links to `/auth/signup`

---

### Screen 2 — Sign Up (`templates/auth/signup.html`)

**Route:** `GET /auth/signup`
**Access:** Public. Redirect to `/dashboard` if already authenticated.

**Fields (in order):**
1. Full name (text, optional but recommended)
2. Email (type=email)
3. Password (type=password) + live strength indicator
4. Confirm password (type=password) + live match indicator

**Password strength indicator:**
- 4 segment bar below the password field
- Segments fill and change colour as rules are met
- Weak (1 rule met): red — Fair (2): amber — Good (3): green — Strong (4): dark green
- 4 rules shown as checklist below the bar, each ticking green when met:
  - At least 8 characters
  - One uppercase letter
  - One number
  - One special character (!@#$% etc.)
- Implement in vanilla JS, no library needed

**Confirm password behaviour:**
- On input: compare value against password field in real time
- Match: green border + "Passwords match" text in green below field
- Mismatch: red border + "Passwords do not match" in red
- Empty: neutral state, no message

**Submit behaviour:**
1. Client-side validation before any API call:
   - All fields filled
   - Password strength >= 3 rules met
   - Passwords match
2. `POST /api/v1/auth/register`
3. On success → redirect to `/auth/verify-email` with email pre-filled in the UI
4. On `CONFLICT` (email taken) → inline error below email field: "An account with this email already exists"
5. On validation errors → show specific field errors inline, not just a toast

**Below card:** "Already have an account? Log in" — links to `/auth/login`
**Terms notice:** Small grey text below submit button linking to Terms + Privacy Policy

---

### Screen 3 — Verify Email (`templates/auth/verify_email.html`)

**Route:** `GET /auth/verify-email`
**Two states:**

**State A — Awaiting verification (no token in URL)**
- Envelope icon in green circle
- "Check your email" heading
- "We sent a verification link to {email}" — email shown in bold
- "I've verified my email" button → tries to proceed to `/dashboard`
- "Didn't get it? Resend email" link → `POST /api/v1/auth/resend-verification`
- Resend link disabled for 60 seconds after click (countdown shown)

**State B — Token present in URL (`?token=xxx`)**
- Auto-fires `POST /api/v1/auth/verify-email` with token on page load
- Loading state: spinner
- On success: green checkmark, "Email verified!" message, "Go to dashboard" button
- On `TOKEN_EXPIRED`: red icon, "This link expired" message, "Request new link" button
- On `INVALID_TOKEN`: red icon, generic error, "Request new link" button

---

### Screen 4 — Forgot Password (`templates/auth/forgot_password.html`)

**Route:** `GET /auth/forgot-password`
**Layout:** Centered card. Lock icon above heading.

**Fields:** Email only.

**Submit behaviour:**
1. `POST /api/v1/auth/forgot-password`
2. Always show success message regardless of whether email exists (security: don't reveal registered emails)
3. Success state: replace form with confirmation message: "If that email is registered, a reset link has been sent. Check your spam folder too."
4. "← Back to login" secondary button

---

### Screen 5 — Reset Password (`templates/auth/reset_password.html`)

**Route:** `GET /auth/reset-password?token=xxx`
**Three states:**

**State A — Token valid, form shown**
- New password field + strength bar (same as signup)
- Confirm new password field + match indicator
- `POST /api/v1/auth/reset-password` on submit
- On success → show State B

**State B — Success**
- Green checkmark circle
- "Password reset!" heading
- "Your password has been updated. You can now log in."
- "Go to login" button

**State C — Token expired/invalid (detected on page load via API or on submit)**
- Red alert circle
- "Link expired" heading
- "This reset link expired after 1 hour. Request a new one."
- "Request new link" button → redirects to `/auth/forgot-password`

**On page load:** Validate token presence. If no token in URL, redirect to `/auth/forgot-password`.

---

### Screen 6 — Onboarding Checklist (`templates/onboarding.html`)

**Route:** `GET /onboarding`
**When shown:** After first successful email verification. `user.onboarding_complete = False`.
**Redirect:** Once all steps done OR user manually skips → `/dashboard`. Mark `onboarding_complete = True`.

**5 steps (in order):**
1. Create account — always Done on arrival
2. Verify email — always Done on arrival
3. Upload your first list → CTA button → `/dashboard`
4. Submit your first bounce report → CTA → `/bounces`
5. Explore the marketplace → CTA → `/marketplace`

**Step states:**
- Done: green checkmark circle, strikethrough title, green "Done" pill
- Active (current incomplete step): accent-filled circle with step number, full-colour title, CTA button
- Pending: grey circle, muted title, yellow "Pending" pill

**Current plan card** at bottom: shows plan + credits + "View plans" CTA.

**Skip link:** Small text link "Skip for now" → marks onboarding complete, redirects to dashboard.

---

### Screen 7 — Dashboard (`templates/dashboard/index.html`)

**Route:** `GET /dashboard`
**Access:** Auth required. Email verified required.

**Layout:** Topbar + sidebar (220px) + main content area.

**Topbar:** Logo left. Right: plan badge + user chip (avatar initials + name + chevron → dropdown).
User dropdown: Profile, Settings, Billing, Log out.

**Sidebar navigation items:**
- Dashboard (active on this screen)
- Job History → `/jobs`
- Marketplace → `/marketplace`
- — divider — (Account section)
- API Keys → `/api-keys`
- Billing → `/billing`
- Settings → `/settings`

**Credits widget** (bottom of sidebar):
- Label: "Credits"
- Large number: `credits_remaining`
- Sub: "of {credits_monthly} remaining"
- Progress bar: `(credits_remaining / credits_monthly) * 100%`
- Bar colour: green if >50%, amber if 20-50%, red if <20%
- "Upgrade plan →" button — links to `/billing`
- In `FREE_TIER_LAUNCH_MODE`: hide progress bar, show "Free launch — unlimited" instead

**Stat cards (4-up grid):**
- Total emails uploaded (all-time)
- Fresh rate (average across last 5 jobs)
- Mimecast detected (all-time)
- Jobs run (last 30 days)

**Upload zone:** Dashed border card. Upload icon. Title + subtitle. "8 intelligence layers" badge.
States: default → drag-over → uploading (with progress) → complete → error.
See Upload States below for full spec.

**Recent jobs table:** Last 5 jobs. Columns: File, Emails, Fresh, Burned, Status, Date, Action arrow.
Active/processing job shows a progress bar below the table with stage label + percentage.

**If no jobs yet:** Show empty state instead of table (see Empty States).

---

### Screen 8 — Upload Flow (within Dashboard)

**Upload zone states — implement all 6:**

**1. Default**
Upload icon + "Drop your CSV here" + "or click to browse · .csv .xlsx · Max 50MB" + "8 intelligence layers" green badge.

**2. Drag over**
Border becomes solid accent green. Background tints green. Text changes to "Drop to upload · Release to start processing" in green.

**3. File selected / uploading**
Solid green border. File icon + filename + file size + detected row count.
Progress bar with percentage. "Uploading... Xs remaining" below bar.

**4. Error — no email column**
Red border + red tinted background. Red error icon. "No email column found" in red.
Sub-text: "Make sure your CSV has a column with email addresses."
"Try again" ghost button.

**5. Error — insufficient credits**
Amber border + amber tinted background. Star icon. "{filename} has {N} rows. You have {credits} credits remaining."
"Buy credits →" amber primary button.

**6. Complete**
Green border + green tinted background. Green checkmark circle.
"Processing complete · {total} emails · {fresh} fresh · {burned} burned"
"View results →" primary button.

**Upload logic:**
1. Validate file type (.csv or .xlsx) and size (< 50MB) client-side
2. Detect email column — show column name detected: "Detected email column: 'Email Address'"
3. Check credits client-side (use cached `/api/v1/usage` response)
4. `POST /api/v1/jobs` (multipart/form-data)
5. On success: store job_id, start polling `GET /api/v1/jobs/{id}` every 3 seconds
6. Update progress bar from `job.processed_emails / job.total_emails`
7. On complete: show state 6, navigate to `/jobs/{id}` automatically after 2 seconds

---

### Screen 9 — Job Detail (`templates/dashboard/job_detail.html`)

**Route:** `GET /jobs/{id}`
**Access:** Auth required. User must own the job.

**Topbar:** "← Dashboard" breadcrumb. Job filename + status pill. "Share" ghost button + "Download CSV" primary button.

**Layout:** 2-column grid. Left: results (wider). Right: Fresh Only panel + trade prompt (280px fixed).

**Left column:**
- 3 stat cards: Total, Fresh (with %), Burned+Torched (with %)
- Intelligence breakdown card: table of all layer results with counts and pills
- Enriched results preview: first 5 rows of output table (all columns)
- "12,400 total rows in download" note

**Right column — Fresh Only panel:**
- 6 toggle rows (removals): Mimecast, Barracuda, Proofpoint, domain age <180d, burn score >50, bounce score >5
- Each toggle calls server-side filter preview endpoint on change
- Live result: "After filtering: 7,420 emails · removed 4,980 (40.2%)"
- "Download fresh only" primary button
- "Download full list" ghost button
- Both buttons: `GET /api/v1/exports/{job_id}/download?preset=...`

**Right column — Trade prompt (shown if avg burn score >70%):**
- "This list is {N}% burned" heading
- "Trade it for a fresher list in the same niche. Anonymous, server-matched."
- "Trade on marketplace →" ghost button with green border

---

### Screen 10 — Job History (`templates/dashboard/job_list.html`)

**Route:** `GET /jobs`
**Columns:** File, Emails, Fresh, Burned, Mimecast, Status, Date, Action

**Row actions:**
- Arrow icon → navigate to `/jobs/{id}`
- Re-run icon (if job is failed) → re-queue same file
- Delete icon → confirm modal → `DELETE /api/v1/jobs/{id}`

**Status pills:** Complete (green), Processing (blue), Queued (yellow), Failed (red)

**Empty state:** If no jobs, show empty state component (see Empty States).

---

### Screen 11 — Marketplace (`templates/marketplace/index.html`)

**Route:** `GET /marketplace`
**Access:** Auth + Growth plan or above. Show plan-required empty state for free/starter users.

**Layout:** 2-column grid.

**Left: Your active listings**
- Each listing card: niche + list size + submission date
- Avg burn score + fresh rate
- Status: Matched (green) / Searching (yellow) / Expired (red)
- Matched listings: "Confirm trade" primary button + "Decline" ghost button
- Searching listings: "Matching algorithm runs every 15 minutes..." note

**Right: Completed trades**
- Each trade: niche + size + Was burn / Got burn + fee paid
- "Download received list" ghost button
- "How it works" explainer (numbered steps)

**"Submit list for trade" button** (top right): Opens modal to select which completed job to submit + niche selector.

---

### Screen 12 — Billing (`templates/billing/index.html`)

**Route:** `GET /billing`

**Top stats (3-up):** Current plan, Credits remaining (resets date), Total spent

**Plan grid (4 columns):**
- Free / Starter / Growth / Pro
- Current plan highlighted with green border + "Current" badge
- Each plan: name, price, credits/mo, feature list (included = green dot, excluded = grey dot), CTA button
- Current plan button: "Current plan" (disabled, green bg)
- Other plans: "Upgrade →" (accent bg)
- Downgrade flow: "Downgrade" ghost button with confirm modal warning

**Credit packs row:**
- 5 packs shown as cards: 10k / 50k / 250k / 1M / 5M
- Best value badge (yellow) on 250k pack
- Clicking any pack: initialises Paystack transaction via `POST /api/v1/billing/buy-credits`
- After payment: Paystack redirects to `/billing/callback?reference=xxx`

**Billing history table** (below packs): Date, description, amount, status pill

---

### Screen 13 — API Keys (`templates/api_keys/index.html`)

**Route:** `GET /api-keys`
**Access:** Auth required. API visible on all plans. Creation requires Pro+.

**If free/starter/growth plan:** Show upgrade prompt in sidebar. Table is visible but dimmed/locked. CTA to upgrade.

**Key list:**
- Each row: label, masked key (`li_live_••••••••••••` — show first 8 chars only), created date, last used date
- "Revoke" button → confirm modal → `DELETE /api/v1/keys/{id}`

**Create new key modal:**
- Label input (required)
- Optional IP whitelist (comma-separated)
- On submit: `POST /api/v1/keys`
- Show generated key in a one-time reveal box with copy button
- Explicit warning: "This is the only time you will see this key. Copy it now."

**API docs reference panel:** Endpoint list with monospace font. Link to `/docs` (Swagger UI).

---

### Screen 14 — Settings (`templates/settings/index.html`)

**Route:** `GET /settings`
**4 subsections (all on one page, not separate routes):**

**Profile:** Full name edit, email (read-only + contact support link), save button

**Security / Password:**
- Current password + new password + confirm new password
- Same strength indicator as signup
- `POST /api/v1/auth/change-password`

**Default Fresh Only preset:**
- 6 toggles matching the job detail panel
- Saved as `export_presets` with `is_default = True`
- `POST /api/v1/exports/presets`

**Danger zone (red border card):**
- "Log out all devices" → confirm modal → `POST /api/v1/auth/logout-all`
- "Delete account" → confirm modal with typed confirmation ("type DELETE to confirm") → API call

---

### Screen 15 — Profile (`templates/profile/index.html`)

**Route:** `GET /profile`

**Left sidebar with avatar:**
- Large initials avatar (first letter of first + last name)
- Name + plan badge below
- Nav: Profile, Security, Notifications, Billing, — Log out

**Account status table:** Plan, email verified status, member since, credits this month

**Notification preferences:**
- Job complete toggle
- Trade matched toggle
- Credits low toggle
- Billing alerts toggle
- Saved to user preferences via `PATCH /api/v1/users/preferences`

---

### Screen 16 — Notifications (`templates/notifications/index.html`)

**Route:** `GET /notifications`

**Bell icon in topbar** with red badge (unread count). Clicking opens this page.
**Mark all read** button → `POST /api/v1/notifications/read-all`

**Notification types and dot colours:**
- Job complete → green dot
- Credits low → amber dot
- Trade matched → blue dot
- Billing event → purple dot
- Read notifications → grey dot, reduced opacity

**Left sidebar:** Notification preferences toggles (per-type email/in-app preferences)

---

### Screen 17 — Empty States

**When to show each:**

| Screen | Empty state trigger | CTA |
|---|---|---|
| Dashboard | `jobs.count == 0` | "Upload first list →" |
| Job History | `jobs.count == 0` | "New upload →" |
| Marketplace | No listings AND no trades | "Submit a list →" |
| API Keys | `api_keys.count == 0` | "Create first key →" |
| Notifications | All notifications read, none pending | No CTA — just "All caught up" |
| Billing history | Never paid | "View plans →" |
| Marketplace (plan gate) | Plan is free or starter | "Upgrade to Growth →" (amber button) |

**Empty state structure:**
```
Icon (44×44, rounded-12px, rgba(42,84,38,.07) bg — green icon)
Title (14px, bold)
Sub-text (12px, muted, max-width 240px, centred)
CTA button (optional)
```

---

### Screen 18 — Error Pages

**404 — Not Found**
Large "404" in `#e8e8e0`. "Page not found" heading. "← Back to dashboard" button.

**500 — Server Error**
Large "500" in `#fcd8d8`. Red heading "Something went wrong". "Try again" red button.
Include: "We've been notified and are looking into it."

**403 — Plan Required**
Amber star icon. "Plan required" amber heading.
Specific message naming the required plan: "The Marketplace requires Growth plan or above."
"Upgrade plan →" amber button.

**Session Expired (401)**
Clock icon in blue circle. "Session expired" blue heading.
"Your session timed out for security. Log in again to continue."
"Log in again →" blue button. Redirect back to original URL after login.

---

### Toast System — All Types & When to Fire

```
success — green:  Job complete, upload success, password changed, trade confirmed, settings saved
error   — red:    API error, upload failed, invalid credentials, payment failed, file too large
warning — amber:  Credits below 20%, plan limit approaching, trade match about to expire
info    — blue:   Trade matched (needs action), email resent, key created
```

**Always show toasts for:**
- Any successful form submission (except login — redirect instead)
- Any API error that doesn't have an inline field error
- Any background event (job complete, trade matched)

**Never show toasts for:**
- Field-level validation errors (show inline under the field)
- Page navigations (show nothing, just navigate)
- Already-shown inline errors

**Toast duration:** success/info = 4s, warning = 6s, error = 8s (stays until dismissed)

---

### Modal System — When to Use

Use a confirm modal (not a toast) for:
- Revoking an API key
- Cancelling a subscription
- Confirming a marketplace trade
- Logging out all devices
- Any destructive action that cannot be undone

Use a danger modal (red confirm button) for:
- Deleting account
- Permanently deleting a job

**Modal always requires two clicks:** Cancel + Confirm. Never auto-confirm.
**Typed confirmation** ("type DELETE to confirm") required for account deletion only.


---

## UI Screens & Flow Specifications

All screens use the List Intel design system. Every Jinja2 template must match these specs exactly.
Design tokens: bg `#f2f1ec`, accent `#2a5426`, accent2 `#3d7a36`, yellow `#cce836`, text `#172617`,
muted `#6a796a`, border `#d8d8cf`. Font: Bricolage Grotesque (Google Fonts, weights 400–800).

---

### AUTH FLOWS

#### Screen: Login (`/auth/login`)
- Centered card on `#f2f1ec` background. Logo top-center. Card max-width 380px.
- Fields: Email, Password.
- "Forgot password?" right-aligned link below password field.
- Submit button full-width. Loading state: spinner + "Logging in…", button disabled.
- Error state: toast `error` fires with `data.message` from API response.
- On success: store `data.data.access_token` in `window.__li_token`, redirect to `/dashboard`.
- Link: "Don't have an account? Sign up free" → `/auth/signup`.
- No redirect if already logged in check happens in dashboard layout, not here.

#### Screen: Sign Up (`/auth/signup`)
**Fields:** Full name, Email, Password, Confirm password.

**Password strength validator (live, runs on every keystroke):**
```
Rules checked:
  r-len  → length >= 8
  r-up   → contains uppercase [A-Z]
  r-num  → contains number [0-9]
  r-sym  → contains special char [^a-zA-Z0-9]

Strength score = count of rules met (0–4)
Bar segments: 4 bars, each filled based on score
  1 met → 1 bar red     (weak)
  2 met → 2 bars amber  (fair)
  3 met → 3 bars green  (good)
  4 met → 4 bars dark green (strong)

Label text: "" | "Weak" | "Fair" | "Good" | "Strong"
Input border: no class | no class | .ok | .ok
```

**Confirm password validator (live):**
```
On input:
  match  → input gets .ok border, shows green "Passwords match"
  no match + len > 0 → input gets .err border, shows red "Passwords do not match"
  empty → no state shown
```

**Submit button:** Disabled unless all 4 rules met AND passwords match.
On success: redirect to `/auth/verify-email` (check your email screen).
On conflict (409): toast "An account with this email already exists".

#### Screen: Verify Email (`/auth/verify-email`)
- Shows after signup. Email address shown in bold.
- CTA: "I've verified my email" — attempts GET `/auth/me`, if verified redirects to `/dashboard`,
  if not shows toast "Email not verified yet. Check your inbox."
- "Resend email" link → POST `/api/v1/auth/resend-verification` → toast success.

#### Screen: Forgot Password (`/auth/forgot-password`)
- Single email field. Lock icon above title.
- On submit: POST `/api/v1/auth/forgot-password`.
- Always shows success message regardless of whether email exists (security).
- Success message: "If that email is registered, a reset link has been sent. It expires in 1 hour."

#### Screen: Reset Password (`/auth/reset-password?token=xxx`)
**Three states rendered conditionally:**

State 1 — Form (token present, not yet submitted):
- New password + confirm password fields, both with strength bar on new password.
- On submit: POST `/api/v1/auth/reset-password` with `{ token, new_password }`.

State 2 — Success (after successful reset):
- Green circle checkmark icon. "Password reset! Go to login" button.

State 3 — Expired (API returns 401 TokenExpired):
- Red circle alert icon. "This link expired. Request a new one." button → `/auth/forgot-password`.

---

### ONBOARDING FLOW

#### Screen: Onboarding (`/onboarding`) — shown once after email verification
Checklist of 5 steps with three visual states:
- `step-done` (green circle tick): completed
- `step-active` (green filled circle, number): current step
- `step-todo` (grey circle, number): not yet reached

Steps in order:
1. Create account → always done after reaching this page
2. Verify email → done if `user.email_verified = true`
3. Upload first list → done if `user` has any completed jobs
4. Submit first bounce report → done if user has submitted any bounce data
5. Explore marketplace → done if user has viewed marketplace (session flag)

Dismiss button: "Skip for now" → sets a cookie `li_onboarding_done=1`, redirects to `/dashboard`.
Auto-dismiss: Once steps 1–3 are done, show a "You're set up!" banner and auto-redirect after 3s.
Plan widget at bottom: current plan + credits + "View plans" CTA.

---

### DASHBOARD FLOWS

#### Screen: Dashboard (`/dashboard`) — requires auth
**Layout:** Sticky topbar (logo left, plan badge + user chip right) + sidebar (210px) + main content.

**Sidebar contents (in order):**
- Dashboard (active)
- Job History
- Marketplace
- API Keys
- Billing
- Settings
- Credits widget (bottom) — shows credits remaining / total, thin progress bar, "Upgrade plan →" CTA

**Main content:**
- Page header: "Dashboard" title, "Upload a list to get started" subtitle, "Upload list" primary button
- Stats row (4 cards): Total uploaded, Fresh rate, Mimecast found, Jobs run
- Upload zone (see Upload States below)
- Recent jobs table (last 5): File, Emails, Fresh, Burned, Status, Date, arrow CTA
- If job is Processing: shows inline progress bar beneath table with stage label + percentage

**Upload zone states — implement all 6:**

1. Default: dashed border, upload icon, "Drop your CSV here", "8 intelligence layers" badge
2. Drag over: solid green border, green tinted background, "Drop to upload" text turns green
3. Uploading: solid green border, file info row (name, size, row count), progress bar + % + ETA
4. Error — no email column: solid red border, red icon, "No email column found" message, "Try again" btn
5. Error — insufficient credits: amber border, star icon, shows how many credits needed vs. have, "Buy credits →" button
6. Complete: solid green border, green checkmark, "Processing complete", summary stats, "View results →"

**Credit check before upload:**
```python
# In jobs/service.py — run BEFORE queuing job
async def preflight_credit_check(user, row_count):
    if settings.FREE_TIER_LAUNCH_MODE:
        return  # skip during free launch period
    if user.credits_remaining < row_count:
        raise InsufficientCreditsException(
            f"You need {row_count} credits but only have {user.credits_remaining}."
        )
```

---

### JOB DETAIL FLOW

#### Screen: Job Detail (`/jobs/<job_id>`)
**Breadcrumb:** ← Dashboard / filename / status pill

**Two-column layout (main + 280px right panel):**

Left column:
- 3 stat cards: Total, Fresh (green), Burned+Torched (red) with percentages
- Intelligence breakdown card: counts for Mimecast, Proofpoint, GWS, M365, domain risk, catchall, disposable
- Enriched results table: first 5 rows preview — email, syntax, mx, spam_filter, infra, domain_risk, burn_score (bar + number), burn_tag, bounce_score

Right panel:
- **Fresh Only Export panel:**
  - 6 toggles with labels. Default state loaded from user's saved preset.
  - Live preview: "After filtering: X,XXX emails — removed Y,YYY (Z%)"
  - Preview recalculates client-side on every toggle change (uses job summary data)
  - "Download fresh only" primary button
  - "Download full list" ghost button
- **Trade prompt card** (shown if avg burn score > 70%):
  - "This list is X% burned"
  - "Trade it for a fresher list in the same niche"
  - "Trade on marketplace →" ghost button → `/marketplace`

**Download flow:**
```
GET /api/v1/jobs/{id}/download?fresh_only=true&filters=<json_preset>
→ Server applies filters server-side
→ Returns CSV as StreamingResponse
→ Browser triggers file download
```

---

### JOB HISTORY FLOW

#### Screen: Job History (`/jobs`)
Table columns: File, Emails, Fresh, Burned, Mimecast, Status, Date, arrow
Status pills:
- `complete` → green "Complete"
- `processing` → blue "Processing"
- `queued` → yellow "Queued"
- `failed` → red "Failed"

Failed row: show error tooltip on hover / "See error" link → modal with `job.error_message`.
Clicking arrow → `/jobs/<job_id>`.
Empty state: upload icon, "No jobs yet", "Upload first list →" button.

**Polling:** If any job is `processing` or `queued`, page auto-polls every 5 seconds via:
```javascript
// In poll.js
async function pollActiveJobs() {
  const active = document.querySelectorAll('[data-status="processing"], [data-status="queued"]');
  if (!active.length) return;
  // fetch updated statuses, update DOM
  setTimeout(pollActiveJobs, 5000);
}
```

---

### MARKETPLACE FLOW

#### Screen: Marketplace (`/marketplace`) — requires Growth plan+

**Entry points:**
- Sidebar nav
- Job detail "Trade on marketplace →" CTA (pre-fills niche based on job metadata)
- Dashboard prompt when avg burn > 70%

**Plan gate:** Free/Starter users see empty state with "Growth plan required" message and upgrade CTA.
Do NOT render the marketplace UI at all for unqualified plans — show plan gate instead.

**Layout:** Two-column grid.

Left column — "Your active listings":
- Each listing card shows: title (niche + size), submitted date, avg burn score, fresh rate, status pill
- Status: `Searching` (yellow), `Matched` (green), `Confirmed` (blue), `Complete` (grey)
- Matched listing: shows "Confirm trade" + "Decline" buttons
- Searching listing: shows "Searching..." message with frequency note

Right column — "Completed trades":
- Shows before/after burn score, fee charged in credits, "Download received list" button
- Empty state if no completed trades

**Submit list for trade modal:**
```
Fields:
  - Select job (dropdown of completed jobs with burn score > 50)
  - Niche (select: B2B SaaS / Ecommerce / Healthcare / Finance / Real Estate / Agency / Other)
  - Confirm: checkbox "I understand this is anonymous and the fee is 10% of list size in credits"
On submit: POST /api/v1/marketplace/offer
```

**Trade confirmation modal:**
- Shows: what you're giving (list size, burn score), what you'll receive (niche, approximate size)
- Shows fee: "X,XXX credits will be deducted"
- "Confirm trade" → POST `/api/v1/marketplace/accept/{trade_id}`
- "Decline" → POST `/api/v1/marketplace/decline/{trade_id}` → listing re-opens for matching

---

### BILLING FLOW

#### Screen: Billing (`/billing`)

**Three stat cards:** Current plan, Credits remaining (with reset date), Total spent

**Plan grid (4 cards):** Free, Starter, Growth, Pro
- Current plan card: highlighted border, "Current plan" badge, disabled button "Current plan"
- Other plans: "Upgrade →" button → POST `/api/v1/billing/initialize` → redirect to Paystack checkout URL
- Most popular badge on Growth card

**Paystack checkout flow:**
```
1. User clicks "Upgrade →"
2. POST /api/v1/billing/initialize { plan: "growth" }
3. Server creates Paystack transaction, returns { checkout_url }
4. window.location.href = checkout_url (Paystack hosted page)
5. User pays on Paystack
6. Paystack redirects to PAYSTACK_CALLBACK_URL (/billing/callback?reference=xxx)
7. GET /billing/callback → server verifies transaction → activates plan → redirect to /billing with toast
```

**Credit packs:** 5 cards, best value highlighted with yellow badge.
Click → same Paystack flow with `type: "credits"` and `pack_index`.

**Billing history table:** Reference, Plan/Pack, Amount, Date, Status
Empty state if no transactions.

---

### API KEYS FLOW

#### Screen: API Keys (`/api-keys`) — requires Pro plan+

**Plan gate:** Free/Starter/Growth users see plan gate empty state with "Upgrade to Pro" CTA.

**Create key modal:**
```
Fields:
  - Label (e.g. "Production", "n8n automation")
  - IP whitelist (optional, comma-separated)
On create: POST /api/v1/keys → returns { raw_key } (shown ONCE, never again)
Show key in modal with copy button and warning: "Save this key now. We cannot show it again."
```

**Key row display:** Label, masked key (`li_live_••••••••••`), last used date, created date, Revoke button.
Revoke → confirm modal → DELETE `/api/v1/keys/{id}` → row removed with toast.

**API docs reference:** Show endpoint list at bottom of page.
Link to `/docs` for full Swagger UI.

---

### NOTIFICATIONS FLOW

#### Screen: Notifications (`/notifications`)

**Notification types and triggers:**

| Type | Trigger | Colour |
|------|---------|--------|
| Job complete | Celery task finishes | Green dot |
| Job failed | Celery task errors | Red dot |
| Trade matched | Marketplace matcher finds a match | Blue dot |
| Trade confirmed | Counterparty confirms | Green dot |
| Credits low | credits_remaining < 100 | Amber dot |
| Credits at zero | credits_remaining = 0 | Red dot |
| Billing payment failed | Paystack webhook | Red dot |
| Email verified | After user clicks verify link | Green dot |

**Unread state:** Bold title, filled dot.
**Read state:** Normal weight, grey dot.
**Mark all read:** Button top-right → POST `/api/v1/notifications/read-all`.

**Notification preferences (sidebar toggles):**
Stored per user in `notification_preferences JSONB` column on `users` table.
Celery tasks check preferences before creating notification records.

---

### SETTINGS FLOW

#### Screen: Settings (`/settings`)

**Four sections in 2-column grid:**

1. Profile — name field (editable), email field (disabled with "Contact support" link), Save button
2. Change password — current password, new password (with strength bar), confirm new password
3. Default Fresh Only preset — 6 toggles, Save preset button → updates `export_presets` table
4. Danger zone — Log out everywhere (POST `/api/v1/auth/logout-all`), Delete account (confirm modal required)

**Delete account modal:**
- Danger modal style (red title, red confirm button)
- User must type "DELETE" in a text field to confirm
- On confirm: DELETE `/api/v1/users/me` → logs out → redirects to landing page with toast "Account deleted"

---

### PROFILE FLOW

#### Screen: Profile (`/profile`)

**Sidebar with avatar** — initials-based avatar (first letter of first name + first letter of last name).
Avatar background: always `var(--accent)` (#2a5426), white text.

**Sidebar nav items:** Profile (active), Security, Notifications, Billing, Log out (red)

**Profile card:** Name (editable), email (read-only). Save button.
**Account status card:** Plan, email verified badge, member since, credits this month.
**Danger zone card:** Log out everywhere, Delete account — same as settings.

---

### ERROR PAGES

All error pages share the same layout: topbar with logo, centered content, no sidebar.

| Code | Title | Icon Background | CTA |
|------|-------|----------------|-----|
| 404 | Page not found | Grey `#e8e8e0` number | ← Back to dashboard |
| 500 | Something went wrong | Red `#fcd8d8` number | Try again (reloads) |
| 403 | Plan required | Amber icon | Upgrade plan → |
| 401 session | Session expired | Blue icon | Log in again → |

**500 page behaviour:** Auto-reports to structured log. Shows "We've been notified" message.
Never show raw stack traces in production (`APP_ENV=production`).

---

### EMPTY STATES — Reference

Every empty state follows the same structure:
```
icon (44×44px rounded rect, light accent background)
title (14px bold)
subtitle (12px muted, max 240px wide, line-height 1.5)
CTA button (optional — primary for action, not shown for "all caught up" states)
```

| Screen | Trigger | CTA |
|--------|---------|-----|
| Job History | No jobs | "Upload first list →" |
| Job History failed | Job failed | "See error" modal |
| Marketplace | No listings + qualified plan | "Submit a list →" |
| Marketplace | Unqualified plan | "Upgrade to Growth →" |
| API Keys | No keys + qualified plan | "Create first key →" |
| API Keys | Unqualified plan | "Upgrade to Pro →" |
| Notifications | No notifications | (no CTA — "All caught up") |
| Billing history | No transactions | "View plans →" |
| Notifications | No unread | (no CTA) |

---

### TOAST NOTIFICATION REFERENCE

All toasts fire via `window.$toast.show(type, title, message, duration)`.
Duration defaults to 4000ms. Set to 0 for persistent (requires manual dismiss).

| Event | Type | Title | Message |
|-------|------|-------|---------|
| Login success | success | "Welcome back!" | — |
| Signup success | success | "Account created" | "Check your email to verify" |
| Upload queued | info | "Processing started" | "{filename} · {n} rows" |
| Job complete | success | "Job complete" | "{n} emails · {fresh}% fresh" |
| Job failed | error | "Job failed" | job.error_message |
| Credits low (80%) | warning | "Credits running low" | "{n} credits remaining this month" |
| Credits exhausted | error | "No credits remaining" | "Buy a credit pack or upgrade" |
| Trade matched | info | "Trade matched!" | "Confirm before it expires in 48h" |
| Trade confirmed | success | "Trade confirmed" | "Your new list is being prepared" |
| Download ready | success | "Download ready" | "Fresh Only: {n} emails" |
| Password changed | success | "Password updated" | "All sessions have been revoked" |
| Plan upgraded | success | "Plan upgraded!" | "Welcome to {plan}. Credits loaded." |
| API key created | success | "API key created" | "Save it now — we won't show it again" |
| API key revoked | success | "Key revoked" | — |
| Payment failed | error | "Payment failed" | "Check your card details and try again" |
| Session expired | warning | "Session expired" | "Please log in again" |
| Form validation | error | First validation error message | — |

---

### MODAL REFERENCE

Two modal types. Both use the Alpine `$store.modal` global.

**Confirm modal (default):** Green confirm button.
```javascript
$store.modal.open({
  title: "Confirm trade",
  message: "You're trading your SaaS list (8,400 leads, burn 74) for a fresher list. Fee: 840 credits. Cannot be undone.",
  confirmLabel: "Confirm trade",
  danger: false,
  onConfirm: async () => { /* call API */ }
})
```

**Danger modal:** Red confirm button. Used for: Delete account, Revoke key, Log out all devices.
```javascript
$store.modal.open({
  title: "Delete account",
  message: "This permanently deletes everything. Type DELETE to confirm.",
  confirmLabel: "Delete forever",
  danger: true,
  requiresTyping: "DELETE",  // input must match before confirm enables
  onConfirm: async () => { /* call DELETE /api/v1/users/me */ }
})
```

---

### NAVIGATION & ROUTING RULES

```
Public routes (no auth required):
  /                    Landing page
  /auth/login
  /auth/signup
  /auth/verify-email
  /auth/forgot-password
  /auth/reset-password

Protected routes (redirect to /auth/login if not authed):
  /dashboard           Requires email_verified = true
  /onboarding          Requires email_verified = true, shown once
  /jobs
  /jobs/<id>
  /marketplace         Requires plan in [growth, pro, agency]
  /billing
  /api-keys            Requires plan in [pro, agency]
  /notifications
  /settings
  /profile

Plan gate logic (in Jinja templates + FastAPI dependency):
  growth+: marketplace, bounce history
  pro+: api keys, api access
  agency: white-label, unlimited credits
```

**Auth guard in dashboard layout (`dashboard_layout.html`):**
```javascript
// Runs on every protected page load
(async () => {
  if (!window.__li_token) {
    // Attempt silent refresh via httpOnly cookie
    const res = await fetch('/api/v1/auth/refresh', { method: 'POST', credentials: 'include' });
    const data = await res.json();
    if (!data.success) { window.location.href = '/auth/login'; return; }
    window.__li_token = data.data.access_token;
  }
})();
```

---

### RESPONSIVE BREAKPOINTS

The app is primarily a desktop tool (cold emailers work on desktop).
Mobile is supported but not the primary use case.

```
Desktop (default): full sidebar + main layout
Tablet (< 1024px): sidebar collapses to icon-only (48px wide)
Mobile (< 768px):  sidebar hidden, hamburger menu, stacked layout
```

Tailwind breakpoint classes used: `md:` for tablet, `sm:` for mobile.
