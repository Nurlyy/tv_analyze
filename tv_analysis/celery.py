import os
from celery import Celery

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "tv_analysis.settings")
app = Celery("tv_analysis")
app.config_from_object("django.conf:settings", namespace="CELERY")
app.autodiscover_tasks()