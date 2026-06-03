import uuid
from django.db import models
from django.conf import settings


class CheckIn(models.Model):
    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='check_ins',
    )
    checked_in_at = models.DateTimeField(auto_now_add=True)
    date = models.DateField()
    note = models.TextField(blank=True, default='')

    class Meta:
        db_table = 'monitoring_check_in'
        ordering = ['-checked_in_at']

    def __str__(self):
        return f'{self.user.email} checked in on {self.date}'


class MonitoringLog(models.Model):
    STATUS_PENDING = 'pending'
    STATUS_CHECKED_IN = 'checked_in'
    STATUS_OVERDUE = 'overdue'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_CHECKED_IN, 'Checked In'),
        (STATUS_OVERDUE, 'Overdue'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='monitoring_logs',
    )
    date = models.DateField()
    scheduled_check_in_time = models.TimeField()
    deadline = models.DateTimeField()
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default=STATUS_PENDING)
    sleep_mode = models.BooleanField(default=False)
    notified = models.BooleanField(default=False)
    notified_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'monitoring_log'
        unique_together = [('user', 'date')]
        ordering = ['-date']

    def __str__(self):
        return f'{self.user.email} — {self.date} — {self.status}'


class NotificationLog(models.Model):
    STATUS_SENT = 'sent'
    STATUS_FAILED = 'failed'

    STATUS_CHOICES = [
        (STATUS_SENT, 'Sent'),
        (STATUS_FAILED, 'Failed'),
    ]

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    monitoring_log = models.ForeignKey(
        MonitoringLog,
        on_delete=models.CASCADE,
        related_name='notification_logs',
    )
    contact_name = models.CharField(max_length=255)
    contact_phone = models.CharField(max_length=20)
    contact_relationship = models.CharField(max_length=100)
    message_sent = models.TextField()
    status = models.CharField(max_length=10, choices=STATUS_CHOICES)
    sent_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'monitoring_notification_log'
        ordering = ['-sent_at']

    def __str__(self):
        return f'Notification to {self.contact_name} — {self.status}'
