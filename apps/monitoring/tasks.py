import logging
from celery import shared_task
from django.utils import timezone
from django.conf import settings

logger = logging.getLogger(__name__)


# create_daily_monitoring_logs has been removed as it is no longer needed in the frequency-based system.


@shared_task(name='monitoring.detect_overdue_checkins')
def detect_overdue_checkins():
    """
    Runs every 15 minutes.
    Finds users whose next_check_in_target + 6 hours is in the past.
    Creates an overdue MonitoringLog (if not exists) and triggers notification.
    """
    from django.contrib.auth import get_user_model
    from .models import MonitoringLog
    from datetime import timedelta

    User = get_user_model()
    now = timezone.now()

    users = User.objects.filter(
        is_active=True,
        safety_info__next_check_in_target__isnull=False,
    ).select_related('safety_info')

    count = 0
    for user in users:
        target_time = user.safety_info.next_check_in_target
        deadline = target_time + timedelta(hours=6)

        if now >= deadline:
            log, created = MonitoringLog.objects.get_or_create(
                user=user,
                target_time=target_time,
                defaults={
                    'deadline': deadline,
                    'status': MonitoringLog.STATUS_OVERDUE,
                }
            )

            if log.status != MonitoringLog.STATUS_OVERDUE:
                log.status = MonitoringLog.STATUS_OVERDUE
                log.save(update_fields=['status', 'updated_at'])

            if not log.notified and not log.sleep_mode:
                notify_trusted_contacts.delay(str(log.id))
                count += 1

    logger.info(f'detect_overdue_checkins: triggered {count} new notifications')
    return count


@shared_task(name='monitoring.notify_trusted_contacts')
def notify_trusted_contacts(monitoring_log_id: str):
    """
    Triggered by detect_overdue_checkins.
    Sends SMS to all trusted contacts, creates NotificationLog entries,
    and marks the MonitoringLog as notified.

    SMS alerts are limited to 2 consecutive missed days. If the user has
    already missed 2 or more days in a row before today, no SMS is sent.
    The counter resets when the user checks in.
    """
    from .models import MonitoringLog, NotificationLog
    from .services import send_sms, compose_alert_message
    from django.utils import timezone

    try:
        log = MonitoringLog.objects.select_related(
            'user', 'user__safety_info'
        ).get(id=monitoring_log_id)
    except MonitoringLog.DoesNotExist:
        logger.error(f'notify_trusted_contacts: MonitoringLog {monitoring_log_id} not found')
        return

    user = log.user

    # Skip SMS if the user is not currently logged in
    if not user.is_logged_in:
        logger.info(
            f'notify_trusted_contacts: skipping SMS for {user.email} — user is logged out'
        )
        log.notified = True
        log.notified_at = timezone.now()
        log.save(update_fields=['notified', 'notified_at', 'updated_at'])
        return

    # Consecutive miss check
    consecutive_misses = 0
    check_target = log.target_time
    frequency = user.safety_info.check_in_frequency if user.safety_info else 24

    while True:
        from datetime import timedelta
        check_target = check_target - timedelta(hours=frequency)
        previous_log = MonitoringLog.objects.filter(
            user=user,
            target_time=check_target,
        ).first()

        if not previous_log:
            break
        if previous_log.status == MonitoringLog.STATUS_CHECKED_IN:
            break  # Chain broken by a successful check-in
        if previous_log.status == MonitoringLog.STATUS_OVERDUE and previous_log.notified:
            consecutive_misses += 1
        else:
            break

    # Current day counts as miss #1. If we already have 1+ previous consecutive
    # misses, this would be miss #2 or beyond — skip the SMS.
    if consecutive_misses >= 1:
        logger.info(
            f'notify_trusted_contacts: skipping SMS for {user.email} — '
            f'{consecutive_misses + 1} consecutive misses (limit is 1)'
        )
        # Still mark notified so the task doesn't keep retrying
        log.notified = True
        log.notified_at = timezone.now()
        log.save(update_fields=['notified', 'notified_at', 'updated_at'])
        return


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

    logger.info(
        f'notify_trusted_contacts: notified {contacts.count()} contacts for {user.email} '
        f'(consecutive miss #{consecutive_misses + 1})'
    )
