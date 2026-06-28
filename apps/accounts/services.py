from django.core.mail import send_mail
from django.core.signing import TimestampSigner, SignatureExpired, BadSignature
from django.urls import reverse
from django.conf import settings


# Sends a 4-digit OTP to the given email for verification or password reset
def send_otp_email(email: str, otp: str) -> None:
    subject = 'Your Life Pulse verification code'
    message = (
        f'Your verification code is: {otp}\n\n'
        f'This code expires in 5 minutes.\n'
        f'If you did not request this, please ignore this email.'
    )
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )


_signer = TimestampSigner(salt='account-deletion')


def generate_deletion_token(email: str) -> str:
    # Returns a signed, timestamped token encoding the user's email.
    return _signer.sign(email)


def verify_deletion_token(token: str, max_age: int = 86400) -> str:
    """
    Validates the token and returns the email it encodes.
    Raises SignatureExpired if older than max_age seconds (default 24 h).
    Raises BadSignature if the token is tampered or invalid.
    """
    return _signer.unsign(token, max_age=max_age)


def send_deletion_confirmation_email(request, email: str, token: str) -> None:
    # Sends an account deletion confirmation link to the given email.
    confirmation_url = request.build_absolute_uri(
        reverse('confirm-account-deletion', kwargs={'token': token})
    )
    subject = 'Confirm your Life Pulse account deletion'
    message = (
        f'You requested to permanently delete your Life Pulse account.\n\n'
        f'Click the link below to confirm. This link expires in 24 hours.\n\n'
        f'{confirmation_url}\n\n'
        f'If you did not request this, you can safely ignore this email.'
    )
    send_mail(
        subject=subject,
        message=message,
        from_email=settings.DEFAULT_FROM_EMAIL,
        recipient_list=[email],
        fail_silently=False,
    )
