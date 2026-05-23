from django.conf import settings


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
        f'Scheduled check-in time: {log.scheduled_check_in_time.strftime("%H:%M")}\n'
        f'Missed deadline: {log.deadline.strftime("%Y-%m-%d %H:%M UTC")}\n'
        f'Home address: {safety_info.home_address}\n'
        f'Access notes: {safety_info.access_notes or "None provided"}\n'
        f'Pets: {pet_details}\n'
        f'Please check on them or contact local authorities if needed.'
    )
