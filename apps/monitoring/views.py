from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from utils.response import CustomResponse
from .models import CheckIn, MonitoringLog
from .serializers import CheckInSerializer, CheckInResponseSerializer, MonitoringStatusSerializer
from .services import get_or_create_today_log


class CheckInView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        log, _ = get_or_create_today_log(request.user)

        if log is None:
            return CustomResponse.error(
                message='No check-in time configured. Please set up your safety info first.',
                status_code=400,
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
            date=timezone.localdate(),
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
        log, _ = get_or_create_today_log(request.user)

        if log is None:
            return CustomResponse.error(
                message='No check-in time configured. Please set up your safety info first.',
                status_code=400,
            )

        serializer = MonitoringStatusSerializer(log)
        return CustomResponse.success(
            message='Status retrieved successfully.',
            data=serializer.data,
        )
