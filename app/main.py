from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse, JSONResponse
from app.core.database import templates
import structlog

from app.config import settings
from app.core.database import engine, Base
from app.core.redis import init_redis, close_redis
from app.core.exceptions import setup_exception_handlers

# Import all models to ensure they are registered with Base.metadata before create_all
from app.features.auth import models as auth_models
from app.features.billing import models as billing_models
from app.features.jobs import models as jobs_models
from app.features.exports import models as exports_models
from app.features.api_keys import models as api_keys_models
from app.features.marketplace import models as marketplace_models
from app.features.bounces import models as bounces_models
from app.features.burn import models as burn_models
from app.features.notifications import models as notifications_models
from app.features.suppression import models as suppression_models
from app.features.sending import models as sending_models
from app.features.exports.models import ExportPreset
from app.features.notifications.models import Notification
from app.features.burn.report_models import SpamReport
from app.features.workspaces.models import Workspace, WorkspaceMember
from app.features.audit.models import AuditEvent
from app.features.jobs.diff_models import JobDiff as _diff_model
from app.features.jobs.aging_models import ListAgingSnapshot as _aging_model
from app.features.burn.niche_models import NicheBurnBenchmark as _niche_model
from app.features.burn.report_models import SpamReport as _spam_report_model
from app.features.auth.router import router as auth_router
from app.features.billing.router import router as billing_api_router, page_router as billing_page_router
from app.features.jobs.router import router as jobs_api_router, page_router as jobs_page_router
from app.features.exports.router import router as exports_api_router
from app.features.api_keys.router import router as api_keys_api_router, page_router as api_keys_page_router
from app.features.api_keys.public_router import router as public_api_router
from app.features.marketplace.router import router as marketplace_api_router, page_router as marketplace_page_router
from app.features.settings.router import router as settings_api_router, page_router as settings_page_router
from app.features.bounces.router import router as bounces_api_router
from app.features.notifications.router import router as notifications_api_router, page_router as notifications_page_router
from app.features.onboarding.router import page_router as onboarding_page_router
from app.features.admin.router import page_router as admin_page_router
from app.features.integrations.router import router as integrations_router
from app.features.domains.router import router as domains_router
from app.features.suppression.router import router as suppression_api_router, page_router as suppression_page_router
from app.features.copilot.router import router as copilot_api_router, page_router as copilot_page_router
from app.features.burn.report_router import router as report_api_router, page_router as report_page_router
from app.features.simulator.router import router as simulator_api_router, page_router as simulator_page_router
from app.features.workspaces.router import router as workspaces_api_router, page_router as workspaces_page_router
from app.features.reports.router import router as reports_api_router
from app.features.audit.router import router as audit_api_router, page_router as audit_page_router
from app.features.sending.router import router as sending_api_router, page_router as sending_page_router
from app.features.sending.tracking import router as tracking_api_router
from app.features.sourcing.router import router as sourcing_api_router, page_router as sourcing_page_router
from app.features.outreach.router import router as outreach_api_router, page_router as outreach_page_router
from app.features.outreach.tracking import router as outreach_tracking_router
from app.features.prospects.router import router as prospects_api_router, page_router as prospects_page_router
from app.core.exceptions import AppException
from fastapi.responses import HTMLResponse

logger = structlog.get_logger()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup hook
    logger.info("startup.starting")
    
    if settings.ENV == "development":
        # Auto-create SQLite tables in development using a sync engine to 
        # bypass Python 3.13 async/greenlet DLL issues on Windows
        from sqlalchemy import create_engine
        sync_db_url = settings.DATABASE_URL.replace("sqlite+aiosqlite", "sqlite")
        sync_engine = create_engine(sync_db_url)
        Base.metadata.create_all(sync_engine)
        logger.info("startup.sqlite_tables_created")
            
    await init_redis()
    logger.info("startup.complete")
    yield
    # Shutdown hook
    logger.info("shutdown.starting")
    await close_redis()
    await engine.dispose()
    logger.info("shutdown.complete")

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan,
    docs_url="/api/docs" if settings.DEBUG else None,
    redoc_url=None,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    # Remove Server header if present
    if "server" in response.headers:
        del response.headers["server"]
    return response

app.mount("/static", StaticFiles(directory="app/static"), name="static")

setup_exception_handlers(app)

@app.exception_handler(404)
async def custom_404_handler(request: Request, __):
    if request.url.path.startswith("/api/v1"):
        return JSONResponse(status_code=404, content={"message": "Not Found"})
    return templates.TemplateResponse("errors/404.html", {"request": request}, status_code=404)

@app.exception_handler(500)
async def custom_500_handler(request: Request, exc: Exception):
    logger.exception("Internal Server Error", exc_info=exc)
    if request.url.path.startswith("/api/v1"):
        return JSONResponse(status_code=500, content={"message": "Internal Server Error"})
    return templates.TemplateResponse("errors/500.html", {"request": request}, status_code=500)

@app.exception_handler(403)
async def custom_403_handler(request: Request, __):
    if request.url.path.startswith("/api/v1"):
        return JSONResponse(status_code=403, content={"message": "Forbidden"})
    return templates.TemplateResponse("errors/403.html", {"request": request}, status_code=403)

# API Routers
app.include_router(billing_api_router, prefix="/api/v1/billing", tags=["billing"])
app.include_router(jobs_api_router, prefix="/api/v1/jobs", tags=["jobs"])
app.include_router(exports_api_router, prefix="/api/v1/exports", tags=["exports"])
app.include_router(api_keys_api_router, prefix="/api/v1/keys", tags=["api_keys"])
app.include_router(public_api_router, prefix="/api/v1", tags=["public_api"])
app.include_router(marketplace_api_router, prefix="/api/v1/marketplace", tags=["marketplace"])
app.include_router(bounces_api_router, prefix="/api/v1/bounces", tags=["bounces"])
app.include_router(settings_api_router, prefix="/api/v1/settings", tags=["settings"])
app.include_router(notifications_api_router, prefix="/api/v1/notifications", tags=["notifications"])
app.include_router(suppression_api_router, prefix="/api/v1/suppressions", tags=["suppression"])
app.include_router(copilot_api_router, prefix="/api/v1/copilot", tags=["copilot"])
app.include_router(simulator_api_router, prefix="/api/v1/simulator", tags=["simulator"])
app.include_router(workspaces_api_router, prefix="/api/v1/workspaces", tags=["workspaces"])
app.include_router(reports_api_router, prefix="/api/v1/reports", tags=["reports"])
app.include_router(audit_api_router, prefix="/api/v1/audit", tags=["audit"])
app.include_router(sending_api_router, prefix="/api/v1/sending", tags=["sending"])
app.include_router(tracking_api_router, prefix="/api/v1", tags=["tracking"])
app.include_router(sourcing_api_router, prefix="/api/v1/sourcing", tags=["sourcing"])
app.include_router(prospects_api_router, prefix="/api/v1/prospects", tags=["prospects"])
app.include_router(outreach_api_router, prefix="/api/v1/outreach", tags=["outreach"])
app.include_router(outreach_tracking_router, prefix="/api/t", tags=["tracking"])

# Page Routers
# All auth routes (API and Pages) are now in this single root-level router
app.include_router(auth_router, tags=["auth", "pages"])
app.include_router(billing_page_router, tags=["pages"])
app.include_router(jobs_page_router, tags=["pages"])
app.include_router(api_keys_page_router, tags=["pages"])
app.include_router(copilot_page_router, tags=["pages"])
app.include_router(simulator_page_router, tags=["pages"])
app.include_router(marketplace_page_router, tags=["pages"])
app.include_router(workspaces_page_router, tags=["pages"])
app.include_router(audit_page_router, tags=["pages"])
app.include_router(settings_page_router, tags=["pages"])
app.include_router(notifications_page_router, tags=["pages"])
app.include_router(onboarding_page_router, tags=["pages"])
app.include_router(admin_page_router, prefix="/admin-portal", tags=["admin"])
app.include_router(report_page_router, tags=["pages"])
app.include_router(integrations_router, prefix="/integrations", tags=["pages", "integrations"])
app.include_router(domains_router, prefix="/domains", tags=["pages", "domains"])
app.include_router(sending_page_router, tags=["pages", "sending"])
app.include_router(sourcing_page_router, tags=["pages", "sourcing"])
app.include_router(suppression_page_router, tags=["pages", "suppression"])
app.include_router(prospects_page_router, tags=["pages", "prospects"])
app.include_router(outreach_page_router, tags=["pages", "outreach"])

@app.get("/")
async def root(request: Request):
    return templates.TemplateResponse("landing.html", {"request": request})

@app.get("/info", response_class=HTMLResponse)
async def info_page(request: Request):
    return templates.TemplateResponse("info.html", {"request": request})
