from rest_framework import serializers
from .models import CheckIn, MonitoringLog


class CheckInSerializer(serializers.ModelSerializer):
    class Meta:
        model = CheckIn
        fields = ['note']


class CheckInResponseSerializer(serializers.ModelSerializer):
    class Meta:
        model = CheckIn
        fields = ['checked_in_at', 'date', 'note']


class MonitoringStatusSerializer(serializers.ModelSerializer):
    checked_in_at = serializers.SerializerMethodField()

    class Meta:
        model = MonitoringLog
        fields = ['date', 'scheduled_check_in_time', 'deadline', 'status', 'sleep_mode', 'checked_in_at']

    def get_checked_in_at(self, obj):
        if obj.status == MonitoringLog.STATUS_CHECKED_IN:
            check_in = obj.user.check_ins.filter(date=obj.date).order_by('-checked_in_at').first()
            if check_in:
                return check_in.checked_in_at
        return None
