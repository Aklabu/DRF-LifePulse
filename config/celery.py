import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')

app = Celery('lifepulse')
app.config_from_object('django.conf:settings', namespace='CELERY')
app.autodiscover_tasks()


app.conf.beat_schedule = {
    # Create daily monitoring logs at midnight
    'create-daily-monitoring-logs': {
        'task': 'monitoring.create_daily_monitoring_logs',
        'schedule': crontab(hour=0, minute=0),
    },
    # Detect overdue check-ins every 15 minutes
    'detect-overdue-checkins': {
        'task': 'monitoring.detect_overdue_checkins',
        'schedule': crontab(minute='*/15'),
    },
}
