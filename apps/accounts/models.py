import uuid
from django.db import models
from django.contrib.auth.models import AbstractBaseUser, PermissionsMixin
from django.utils import timezone
from datetime import timedelta

from .managers import UserManager


# Custom user model using email as the unique identifier
class User(AbstractBaseUser, PermissionsMixin):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    name = models.CharField(max_length=255)
    email = models.EmailField(unique=True)
    phone_number = models.CharField(max_length=20, unique=True)
    is_active = models.BooleanField(default=True)
    is_staff = models.BooleanField(default=False)
    is_superuser = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    USERNAME_FIELD = 'email'
    REQUIRED_FIELDS = []

    objects = UserManager()

    class Meta:
        db_table = 'accounts_user'

    def __str__(self):
        return self.email


# Safety-related information for users living alone or temporarily alone
class SafetyInfo(models.Model):
    LIVING_STATUS_CHOICES = [
        ('living_alone', 'Living Alone'),
        ('temporarily_alone', 'Temporarily Alone'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='safety_info')
    living_status = models.CharField(max_length=20, choices=LIVING_STATUS_CHOICES)
    home_address = models.TextField()
    access_notes = models.TextField(blank=True, default='')
    # Used to trigger alerts if the user misses a daily check-in
    check_in_time = models.TimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'accounts_safety_info'

    def __str__(self):
        return f'SafetyInfo for {self.user.email}'


# Emergency contacts linked to a user (max 5 enforced at the API layer)
class TrustedContact(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='trusted_contacts')
    name = models.CharField(max_length=255)
    relationship = models.CharField(max_length=100)
    phone_number = models.CharField(max_length=20)
    email = models.EmailField(blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'accounts_trusted_contact'

    def __str__(self):
        return f'{self.name} ({self.relationship}) — {self.user.email}'


# Pet records registered by the user for emergency care coordination (max 5 enforced at the API layer)
class Pet(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='pets')
    pet_name = models.CharField(max_length=255)
    age = models.PositiveIntegerField()
    breed = models.CharField(max_length=255)
    photo = models.ImageField(upload_to='pets/', blank=True, null=True)
    caregiver_name = models.CharField(max_length=255, blank=True, default='')
    caregiver_phone = models.CharField(max_length=20, blank=True, default='')
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'accounts_pet'

    def __str__(self):
        return f'{self.pet_name} — {self.user.email}'


# OTP codes used for email verification and password reset
class OTPVerification(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    email = models.EmailField()
    otp = models.CharField(max_length=4)
    is_verified = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    expires_at = models.DateTimeField()

    class Meta:
        db_table = 'accounts_otp_verification'

    def save(self, *args, **kwargs):
        if not self.expires_at:
            self.expires_at = timezone.now() + timedelta(minutes=5)
        super().save(*args, **kwargs)

    def is_expired(self):
        return timezone.now() > self.expires_at

    def __str__(self):
        return f'OTP for {self.email}'


# Invalidated JWT refresh tokens to prevent reuse after logout
class BlacklistedToken(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    token = models.TextField()
    blacklisted_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'accounts_blacklisted_token'

    def __str__(self):
        return f'Blacklisted token at {self.blacklisted_at}'
