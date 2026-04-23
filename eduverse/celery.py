# ===== Celery Configuration for EduVerse Platform =====
# Handles async tasks, scheduled jobs, and background processing

import os
from celery import Celery
from celery.schedules import crontab

# Set default Django settings
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'eduverse.settings')

app = Celery('eduverse')

# Load config from Django settings with CELERY_ prefix
app.config_from_object('django.conf:settings', namespace='CELERY')

# Auto-discover tasks from all installed apps
app.autodiscover_tasks()


# Celery Beat Schedule for periodic tasks
app.conf.beat_schedule = {
    # Send daily digest emails at 8 AM
    'send-daily-digest': {
        'task': 'notifications.tasks.send_daily_digest',
        'schedule': crontab(hour=8, minute=0),
    },
    
    # Check and update booking statuses every 5 minutes
    'check-booking-status': {
        'task': 'bookings.tasks.check_booking_statuses',
        'schedule': crontab(minute='*/5'),
    },
    
    # Send booking reminders 1 hour before
    'send-booking-reminders': {
        'task': 'bookings.tasks.send_booking_reminders',
        'schedule': crontab(minute='*/10'),
    },
    
    # Clean up expired payment intents daily
    'cleanup-expired-payments': {
        'task': 'payments.tasks.cleanup_expired_payments',
        'schedule': crontab(hour=2, minute=0),
    },
    
    # Generate weekly progress reports every Monday at 9 AM
    'generate-weekly-reports': {
        'task': 'courses.tasks.generate_weekly_reports',
        'schedule': crontab(hour=9, minute=0, day_of_week=1),
    },
    
    # Update course popularity scores every hour
    'update-popularity-scores': {
        'task': 'courses.tasks.update_popularity_scores',
        'schedule': crontab(minute=0),
    },
    
    # Process certificate generation queue
    'process-certificate-queue': {
        'task': 'courses.tasks.process_certificate_queue',
        'schedule': crontab(minute='*/15'),
    },
}

# Celery configuration
app.conf.update(
    task_serializer='json',
    accept_content=['json'],
    result_serializer='json',
    timezone='Asia/Riyadh',
    enable_utc=True,
    task_track_started=True,
    task_time_limit=30 * 60,  # 30 minutes
    task_soft_time_limit=25 * 60,  # 25 minutes
)


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    """Debug task to test Celery is working"""
    print(f'Request: {self.request!r}')
