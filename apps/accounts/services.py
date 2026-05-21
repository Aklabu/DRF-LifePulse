from django.core.mail import send_mail
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
