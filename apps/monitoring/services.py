from datetime import datetime, timedelta

from django.conf import settings
from django.utils import timezone


def get_or_create_current_cycle_log(user, auto_reactivate=True):
    """
    Returns (MonitoringLog, created) for the current cycle.

    If no log exists yet for the current next_check_in_target, creates one.
    Returns (None, False) if the user has no SafetyInfo.

    When auto_reactivate=False and monitoring is paused, returns (None, False)
    so the caller can detect the deactivated state without side effects.
    """
    from .models import MonitoringLog

    # Check the user has a valid SafetyInfo
    safety_info = getattr(user, 'safety_info', None)
    if not safety_info or not safety_info.next_check_in_target:
        return None, False

    # If the user's monitoring is paused, reactivate only when explicitly requested.
    if not safety_info.is_monitoring_active:
        if not auto_reactivate:
            return None, False

        from .utils import calculate_next_check_in_target
        from .models import log_activity, ActivityLog
        safety_info.is_monitoring_active = True
        safety_info.next_check_in_target = calculate_next_check_in_target(
            safety_info.anchor_time,
            safety_info.check_in_frequency,
            from_time=timezone.now(),
            user_timezone=safety_info.timezone
        )
        safety_info.save(update_fields=['is_monitoring_active', 'next_check_in_target'])
        log_activity(user, ActivityLog.MONITORING_ACTIVATED, f'Monitoring reactivated via check-in. Next target: {safety_info.next_check_in_target}')

    target_time = safety_info.next_check_in_target

    # Fast path
    try:
        log = MonitoringLog.objects.get(user=user, target_time=target_time)
        return log, False
    except MonitoringLog.DoesNotExist:
        pass

    deadline = target_time + timedelta(hours=6)

    log, created = MonitoringLog.objects.get_or_create(
        user=user,
        target_time=target_time,
        defaults={
            'deadline': deadline,
            'status': MonitoringLog.STATUS_PENDING,
        },
    )
    return log, created


def send_sms(to_phone: str, message: str) -> bool:
    """
    Send an SMS via Twilio.
    Returns True on success, False on failure.
    Abstracted so the gateway can be swapped without touching task logic.
    """
    try:
        from twilio.rest import Client
        client = Client(settings.TWILIO_ACCOUNT_SID, settings.TWILIO_AUTH_TOKEN)
        client.messages.create(
            body=message,
            from_=settings.TWILIO_PHONE_NUMBER,
            to=to_phone,
        )
        return True
    except Exception as e:
        # Log the error but don't raise — caller handles the failure status
        import logging
        logger = logging.getLogger(__name__)
        logger.error(f'SMS send failed to {to_phone}: {e}')
        return False


def compose_alert_message(user, safety_info, log) -> str:
    # Compose the SMS alert message for overdue check-in
    pets = user.pets.all()
    if pets.exists():
        pet_details = ', '.join(
            f'{p.pet_name} ({p.breed}, age {p.age})' for p in pets
        )
    else:
        pet_details = 'None'

    return (
        f'[SAFETY ALERT] — {user.name} has missed their check-in.\n'
        f'Target check-in time: {log.target_time.strftime("%Y-%m-%d %H:%M UTC")}\n'
        f'Missed deadline: {log.deadline.strftime("%Y-%m-%d %H:%M UTC")}\n'
        f'Home address: {safety_info.home_address}\n'
        f'Access notes: {safety_info.access_notes or "None provided"}\n'
        f'Pets: {pet_details}\n'
        f'Please check on them or contact local authorities if needed.'
    )
