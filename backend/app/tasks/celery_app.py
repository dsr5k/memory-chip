from celery import Celery

from app.core.config import get_settings

settings = get_settings()

celery_app = Celery('memory_chip', broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.update(task_always_eager=settings.celery_task_always_eager)
