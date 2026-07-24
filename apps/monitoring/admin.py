from django.contrib import admin
from django.utils import timezone
from .models import CheckIn, MonitoringLog, NotificationLog, ActivityLog


@admin.register(MonitoringLog)
class MonitoringLogAdmin(admin.ModelAdmin):
    list_display = ['user', 'target_time', 'status', 'sleep_mode', 'notified', 'deadline', 'notified_at']
    list_filter = ['status', 'notified', 'sleep_mode']
    search_fields = ['user__email', 'user__name']
    ordering = ['-target_time']
    readonly_fields = ['created_at', 'updated_at']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')

    # Highlight overdue rows
    def get_list_display_links(self, request, list_display):
        return ['user']

    def changelist_view(self, request, extra_context=None):
        today_start = timezone.now().replace(hour=0, minute=0, second=0, microsecond=0)
        overdue_today = MonitoringLog.objects.filter(
            target_time__gte=today_start,
            status=MonitoringLog.STATUS_OVERDUE,
        ).count()
        extra_context = extra_context or {}
        extra_context['overdue_today_count'] = overdue_today
        return super().changelist_view(request, extra_context=extra_context)


@admin.register(CheckIn)
class CheckInAdmin(admin.ModelAdmin):
    list_display = ['user', 'checked_in_at', 'note']
    list_filter = []
    search_fields = ['user__email', 'user__name']
    ordering = ['-checked_in_at']
    readonly_fields = ['checked_in_at']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')


@admin.register(NotificationLog)
class NotificationLogAdmin(admin.ModelAdmin):
    list_display = ['contact_name', 'contact_relationship', 'contact_phone', 'status', 'sent_at']
    list_filter = ['status', 'sent_at']
    search_fields = ['contact_name', 'contact_phone', 'monitoring_log__user__email']
    ordering = ['-sent_at']
    readonly_fields = ['sent_at']

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('monitoring_log__user')


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ['created_at', 'user', 'action', 'description', 'ip_address']
    list_display_links = ['created_at']
    list_filter = ['action', 'created_at', 'user__email']
    search_fields = ['user__email', 'user__name', 'description']
    ordering = ['-created_at']
    date_hierarchy = 'created_at'
    readonly_fields = ['user', 'action', 'description', 'metadata', 'ip_address', 'created_at']
    list_per_page = 50

    def get_queryset(self, request):
        return super().get_queryset(request).select_related('user')

    def has_add_permission(self, request):
        return False  # Logs are system-generated only

    def has_change_permission(self, request, obj=None):
        return False  # Audit trail is immutable

    def has_delete_permission(self, request, obj=None):
        return False  # Never delete audit logs

