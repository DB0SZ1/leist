import asyncio
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy import engine_from_config
from sqlalchemy import pool
from alembic import context

from app.config import settings
from app.core.database import Base
from app.features.auth.models import User, RefreshToken
from app.features.billing.models import BillingEvent, Subscription
from app.features.jobs.models import Job, JobResult
from app.features.burn.models import BurnPool
from app.features.bounces.models import BounceEvent
from app.features.marketplace.models import Listing, Trade, MarketplaceFee
from app.features.api_keys.models import APIKey
from app.features.exports.models import ExportPreset
try:
    from app.features.notifications.models import Notification
except ImportError:
    pass
from app.features.prospects.models import ProspectJob, Prospect
from app.features.outreach.models import SendingAccount, EmailTemplate, Campaign, SequenceStep, CampaignRecipient, TrackingEvent

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

target_metadata = Base.metadata

def get_url():
    if settings.ENV == "development":
        # Force sync sqlite for migrations on Windows
        return settings.DATABASE_URL.replace("sqlite+aiosqlite://", "sqlite://")
    # Force use of psycopg2 for migrations to avoid greenlet DLL issues on Windows
    return settings.DATABASE_URL.replace("postgresql+asyncpg://", "postgresql://").replace("postgres://", "postgresql://")

def run_migrations_offline() -> None:
    url = get_url()
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()

def run_migrations_online() -> None:
    # Use sync engine for migrations
    configuration = config.get_section(config.config_ini_section)
    configuration["sqlalchemy.url"] = get_url()
    connectable = engine_from_config(
        configuration,
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(
            connection=connection, target_metadata=target_metadata, render_as_batch=True
        )

        with context.begin_transaction():
            context.run_migrations()

if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
