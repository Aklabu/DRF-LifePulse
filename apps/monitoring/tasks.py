import logging
from celery import shared_task
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)


@shared_task(name='monitoring.create_daily_monitoring_logs')
def create_daily_monitoring_logs():
    """
    Runs daily at midnight.
    Creates a MonitoringLog for every active user who has a SafetyInfo
    with a check_in_time set. Idempotent — skips users who already have
    a log for today.
    """
    from django.contrib.auth import get_user_model
    from datetime import datetime, timedelta
    from .models import MonitoringLog

    User = get_user_model()
    today = timezone.localdate()
    created_count = 0

    users = User.objects.filter(
        is_active=True,
        safety_info__check_in_time__isnull=False,
    ).select_related('safety_info')

    for user in users:
        if MonitoringLog.objects.filter(user=user, date=today).exists():
            continue

        check_in_time = user.safety_info.check_in_time
        # Build deadline as today's date + check_in_time + 6 hours
        scheduled_dt = timezone.make_aware(
            datetime.combine(today, check_in_time)
        )
        deadline = scheduled_dt + timedelta(hours=6)

        MonitoringLog.objects.create(
            user=user,
            date=today,
            scheduled_check_in_time=check_in_time,
            deadline=deadline,
            status=MonitoringLog.STATUS_PENDING,
        )
        created_count += 1

    logger.info(f'create_daily_monitoring_logs: created {created_count} logs for {today}')
    return created_count


@shared_task(name='monitoring.detect_overdue_checkins')
def detect_overdue_checkins():
    """
    Runs every 15 minutes.
    Marks pending logs past their deadline as overdue and triggers
    the notification task for each.
    """
    from .models import MonitoringLog

    now = timezone.now()
    overdue_logs = MonitoringLog.objects.filter(
        status=MonitoringLog.STATUS_PENDING,
        deadline__lte=now,
        notified=False,
    )

    count = 0
    for log in overdue_logs:
        log.status = MonitoringLog.STATUS_OVERDUE
        log.save(update_fields=['status', 'updated_at'])
        notify_trusted_contacts.delay(str(log.id))
        count += 1

    logger.info(f'detect_overdue_checkins: found {count} overdue logs')
    return count


@shared_task(name='monitoring.notify_trusted_contacts')
def notify_trusted_contacts(monitoring_log_id: str):
    """
    Triggered by detect_overdue_checkins.
    Sends SMS to all trusted contacts, creates NotificationLog entries,
    and marks the MonitoringLog as notified.
    """
    from .models import MonitoringLog, NotificationLog
    from .services import send_sms, compose_alert_message

    try:
        log = MonitoringLog.objects.select_related(
            'user', 'user__safety_info'
        ).get(id=monitoring_log_id)
    except MonitoringLog.DoesNotExist:
        logger.error(f'notify_trusted_contacts: MonitoringLog {monitoring_log_id} not found')
        return

    user = log.user
    safety_info = getattr(user, 'safety_info', None)

    if not safety_info:
        logger.warning(f'notify_trusted_contacts: no SafetyInfo for user {user.email}')
        return

    contacts = user.trusted_contacts.all()
    if not contacts.exists():
        logger.warning(f'notify_trusted_contacts: no trusted contacts for user {user.email}')
        return

    message = compose_alert_message(user, safety_info, log)

    for contact in contacts:
        success = send_sms(contact.phone_number, message)
        NotificationLog.objects.create(
            monitoring_log=log,
            contact_name=contact.name,
            contact_phone=contact.phone_number,
            contact_relationship=contact.relationship,
            message_sent=message,
            status=NotificationLog.STATUS_SENT if success else NotificationLog.STATUS_FAILED,
        )

    log.notified = True
    log.notified_at = timezone.now()
    log.save(update_fields=['notified', 'notified_at', 'updated_at'])

    logger.info(f'notify_trusted_contacts: notified {contacts.count()} contacts for user {user.email}')
