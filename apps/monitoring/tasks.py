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
    Finds users whose next_check_in_target + 1 hour is in the past.
    Creates an overdue MonitoringLog (if not exists) and triggers notification.
    """
    from django.contrib.auth import get_user_model
    from django.db import transaction
    from .models import MonitoringLog
    from apps.accounts.models import SafetyInfo
    from datetime import timedelta

    User = get_user_model()
    now = timezone.now()

    users = User.objects.filter(
        is_active=True,
        is_logged_in=True,
        safety_info__next_check_in_target__isnull=False,
        safety_info__is_monitoring_active=True,
    ).select_related('safety_info')

    count = 0
    for user in users:
        with transaction.atomic():
            safety_info = SafetyInfo.objects.select_for_update(of=('self',)).filter(user=user).first()
            if not safety_info or not safety_info.is_monitoring_active:
                continue

            target_time = safety_info.next_check_in_target
            deadline = target_time + timedelta(hours=1)

            if now >= deadline:
                log, created = MonitoringLog.objects.select_for_update(of=('self',)).get_or_create(
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
                    log.notified = True
                    log.notified_at = now
                    log.save(update_fields=['notified', 'notified_at', 'updated_at'])

                    notify_trusted_contacts.delay(str(log.id))
                    count += 1

                    from .models import log_activity, ActivityLog
                    log_activity(user, ActivityLog.OVERDUE_DETECTED, f'Overdue detected. Target: {target_time}, Deadline: {deadline}', metadata={'target_time': str(target_time), 'deadline': str(deadline)})

    logger.info(f'detect_overdue_checkins: triggered {count} new notifications')
    return count


@shared_task(name='monitoring.notify_trusted_contacts')
def notify_trusted_contacts(monitoring_log_id: str):
    """
    Triggered by detect_overdue_checkins.
    Sends SMS to all trusted contacts immediately on the first missed interval.
    After sending the SMS, the user's monitoring is paused (is_monitoring_active = False).
    """
    from .models import MonitoringLog, NotificationLog
    from .services import send_sms, compose_alert_message
    from django.utils import timezone
    from django.db import transaction

    with transaction.atomic():
        try:
            log = MonitoringLog.objects.select_for_update(of=('self',)).select_related(
                'user', 'user__safety_info'
            ).get(id=monitoring_log_id)
        except MonitoringLog.DoesNotExist:
            logger.error(f'notify_trusted_contacts: MonitoringLog {monitoring_log_id} not found')
            return

        user = log.user
        safety_info = getattr(user, 'safety_info', None)

        # --- FINAL SAFETY CHECKS BEFORE SENDING SMS ---
        # 1. Is the user currently signed in?
        if not user.is_active or not user.is_logged_in:
            logger.info(f'notify_trusted_contacts: skipping SMS for {user.email} — user is not active or logged out')
            return

        # 2. Is there safety info?
        if not safety_info:
            logger.info(f'notify_trusted_contacts: skipping SMS for {user.email} — no safety info')
            return

        # 3. Is there an active check-in schedule?
        if not safety_info.next_check_in_target:
            logger.info(f'notify_trusted_contacts: skipping SMS for {user.email} — no active check-in schedule')
            return

        # 4. Has the user genuinely missed the deadline and grace period?
        if log.status != MonitoringLog.STATUS_OVERDUE or timezone.now() < log.deadline:
            logger.info(f'notify_trusted_contacts: skipping SMS for {user.email} — deadline not genuinely missed')
            return

        # 5. Has the session not been cancelled by sleep mode?
        if log.sleep_mode:
            logger.info(f'notify_trusted_contacts: skipping SMS for {user.email} — session is in sleep mode')
            return

    contacts = user.trusted_contacts.all()
    if not contacts.exists():
        logger.warning(f'notify_trusted_contacts: no trusted contacts for user {user.email}')
        return

    message = compose_alert_message(user, safety_info, log)

    notified_count = 0
    for contact in contacts:
        if user.sms_credits <= 0:
            logger.warning(f'notify_trusted_contacts: user {user.email} ran out of SMS credits. Stopping notifications.')
            break
            
        success = send_sms(contact.phone_number, message)
        NotificationLog.objects.create(
            monitoring_log=log,
            contact_name=contact.name,
            contact_phone=contact.phone_number,
            contact_relationship=contact.relationship,
            message_sent=message,
            status=NotificationLog.STATUS_SENT if success else NotificationLog.STATUS_FAILED,
        )
        
        if success:
            user.sms_credits -= 1
            user.save(update_fields=['sms_credits', 'updated_at'])
            notified_count += 1

            from .models import log_activity as _log_activity, ActivityLog
            _log_activity(user, ActivityLog.SMS_SENT, f'SMS sent to {contact.name} ({contact.phone_number})', metadata={'contact_name': contact.name, 'contact_phone': contact.phone_number})
        else:
            from .models import log_activity as _log_activity, ActivityLog
            _log_activity(user, ActivityLog.SMS_FAILED, f'SMS failed to {contact.name} ({contact.phone_number})', metadata={'contact_name': contact.name, 'contact_phone': contact.phone_number})

    # Pause monitoring so no more SMS are sent until the user reactivates by opening the app
    safety_info.is_monitoring_active = False
    safety_info.save(update_fields=['is_monitoring_active'])

    from .models import log_activity as _log_activity, ActivityLog
    _log_activity(user, ActivityLog.MONITORING_DEACTIVATED, f'Monitoring paused after SMS escalation. {notified_count} contact(s) notified.')

    logger.info(
        f'notify_trusted_contacts: notified {notified_count} contacts for {user.email} and paused monitoring.'
    )


@shared_task
def reset_monthly_sms_credits():
    from apps.accounts.models import User
    
    logger.info('Running monthly SMS credits reset task...')
    
    # Pro users get 50 SMS credits per month
    pro_users = User.objects.filter(is_active=True, subscription_tier='pro')
    pro_count = pro_users.update(sms_credits=50)
    
    # Free users get 0 SMS credits (No free trial allowed)
    free_users = User.objects.filter(is_active=True, subscription_tier='free')
    free_count = free_users.update(sms_credits=0)

    logger.info(f'Monthly SMS reset complete. Updated {pro_count} Pro users and {free_count} Free users.')
