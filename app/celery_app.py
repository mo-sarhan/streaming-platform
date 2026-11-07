
from app.core.config import settings
import os

from celery import Celery

celery_app = Celery(
    "video_processor",
    broker=settings.CELERY_BROKER_URL,
    include=["app.tasks.video"],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)