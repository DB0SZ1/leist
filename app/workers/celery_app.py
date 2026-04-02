from celery import Celery
from kombu.serialization import register
from app.config import settings
from app.core.msgpack import encode, decode

register('msgpack', encode, decode, content_type='application/x-msgpack', content_encoding='utf-8')

app = Celery("listintel")

app.conf.update(
    broker_url=getattr(settings, "CELERY_BROKER_URL", "redis://localhost:6379/0"),
    result_backend=getattr(settings, "CELERY_RESULT_BACKEND", "redis://localhost:6379/1"),
    task_serializer='msgpack',
    result_serializer='msgpack',
    accept_content=['msgpack'],
    task_routes={
        'app.workers.tasks.process_job.*': {'queue': 'processing'},
        'app.workers.tasks.marketplace_match.*': {'queue': 'marketplace'},
        'app.workers.tasks.domain_health_monitor.*': {'queue': 'processing'},
    },
    beat_schedule={
        'check-all-domains-daily': {
            'task': 'app.workers.tasks.domain_health_monitor.check_all_domains',
            'schedule': 86400.0,  # Run every 24 hours
        },
        'nightly-list-aging': {
            'task': 'app.workers.tasks.list_aging.run_nightly_list_aging',
            'schedule': 86400.0,  # Run every 24 hours
        },
        'nightly-niche-benchmarks': {
            'task': 'app.workers.tasks.niche_benchmarks.run_daily_niche_benchmarks',
            'schedule': 86400.0,
        },
        'weekly-burn-alerts': {
            'task': 'app.workers.tasks.burn_alerts.run_weekly_burn_alerts',
            'schedule': 604800.0,  # Run every 7 days
        },
        'outreach-engine-tick': {
            'task': 'app.features.sending.engine.outreach_engine_tick',
            'schedule': 300.0,  # Run every 5 minutes
        },
    }
)

app.autodiscover_tasks(['app.workers.tasks', 'app.features.sending'])
