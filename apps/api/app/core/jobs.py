from celery import Celery

from app.core.config import get_settings
from app.core.redis_connection import redis_tls_options

settings = get_settings()
def create_celery_app(redis_url: str, *, production: bool = False) -> Celery:
    tls = redis_tls_options(redis_url, production=production)
    app = Celery("syre_banks_fitness", broker=redis_url, backend=redis_url, include=["app.providers.email"])
    app.conf.update(
        task_serializer="json", result_serializer="json", accept_content=["json"],
        timezone="UTC", enable_utc=True, task_acks_late=True, task_time_limit=120,
        broker_use_ssl=tls or False, redis_backend_use_ssl=tls or None,
        broker_connection_retry_on_startup=True,
        broker_transport_options={"socket_connect_timeout": 5, "socket_timeout": 5},
        redis_socket_connect_timeout=5, redis_socket_timeout=5,
        task_publish_retry_policy={"max_retries": 2, "interval_start": 0.2, "interval_step": 0.2, "interval_max": 1},
        worker_prefetch_multiplier=1,
    )
    return app


celery_app = create_celery_app(settings.redis_url, production=settings.production)

celery_app.conf.beat_schedule = {"pending-mail": {"task": "app.providers.email.dispatch_outbox", "schedule": 60.0}}
