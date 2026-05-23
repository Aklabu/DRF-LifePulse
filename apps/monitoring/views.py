from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from utils.response import CustomResponse
from .models import CheckIn, MonitoringLog
from .serializers import CheckInSerializer, CheckInResponseSerializer, MonitoringStatusSerializer


class CheckInView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        today = timezone.localdate()

        try:
            log = MonitoringLog.objects.get(user=request.user, date=today)
        except MonitoringLog.DoesNotExist:
            return CustomResponse.error(
                message='No monitoring log found for today.',
                status_code=404,
            )

        if log.status == MonitoringLog.STATUS_CHECKED_IN:
            return CustomResponse.error(
                message='Already checked in today.',
                status_code=400,
            )

        serializer = CheckInSerializer(data=request.data)
        if not serializer.is_valid():
            return CustomResponse.error(
                message='Validation failed.',
                status_code=400,
                errors=serializer.errors,
            )

        note = serializer.validated_data.get('note', '')

        # If overdue, still allow but note it was late
        if log.status == MonitoringLog.STATUS_OVERDUE:
            note = f'[Late check-in — after deadline] {note}'.strip()

        check_in = CheckIn.objects.create(
            user=request.user,
            date=today,
            note=note,
        )

        log.status = MonitoringLog.STATUS_CHECKED_IN
        log.save(update_fields=['status', 'updated_at'])

        return CustomResponse.success(
            message='Checked in successfully.',
            data={
                'checked_in_at': check_in.checked_in_at,
                'date': check_in.date,
                'status': log.status,
                'note': check_in.note,
            },
        )


class MonitoringStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        today = timezone.localdate()

        try:
            log = MonitoringLog.objects.get(user=request.user, date=today)
        except MonitoringLog.DoesNotExist:
            return CustomResponse.error(
                message='No monitoring log found for today.',
                status_code=404,
            )

        serializer = MonitoringStatusSerializer(log)
        return CustomResponse.success(
            message='Status retrieved successfully.',
            data=serializer.data,
        )
