from celery import Celery

from app.core.config import get_settings

settings = get_settings()
celery_app = Celery("syre_banks_fitness", broker=settings.redis_url, backend=settings.redis_url, include=["app.providers.email"])
celery_app.conf.update(task_serializer="json", result_serializer="json", accept_content=["json"], timezone="UTC", enable_utc=True, task_acks_late=True, task_time_limit=120)

celery_app.conf.beat_schedule = {"pending-mail": {"task": "app.providers.email.dispatch_outbox", "schedule": 60.0}}
