from django.utils import timezone
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated

from utils.response import CustomResponse
from .models import CheckIn, MonitoringLog
from .serializers import CheckInSerializer, CheckInResponseSerializer, MonitoringStatusSerializer
from .services import get_or_create_current_cycle_log
from .utils import calculate_next_check_in_target


class CheckInView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        log, _ = get_or_create_current_cycle_log(request.user)

        if log is None:
            return CustomResponse.error(
                message='No check-in time configured. Please set up your safety info first.',
                status_code=400,
            )

        if log.sleep_mode:
            return CustomResponse.error(
                message='Sleep mode is active. Disable sleep mode before checking in.',
                status_code=400,
            )
        # Removed the Already Checked in Today logic, as users can check in multiple times

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
            note=note,
        )

        log.status = MonitoringLog.STATUS_CHECKED_IN
        log.save(update_fields=['status', 'updated_at'])
        
        safety_info = request.user.safety_info
        new_target = calculate_next_check_in_target(
            safety_info.anchor_time, 
            safety_info.check_in_frequency, 
            from_time=timezone.now()
        )
        safety_info.next_check_in_target = new_target
        safety_info.save(update_fields=['next_check_in_target'])

        return CustomResponse.success(
            message='Checked in successfully.',
            data={
                'checked_in_at': check_in.checked_in_at,
                'status': log.status,
                'note': check_in.note,
                'next_check_in_target': new_target,
            },
        )


class MonitoringStatusView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        log, _ = get_or_create_current_cycle_log(request.user)

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


class SleepModeView(APIView):
    permission_classes = [IsAuthenticated]

    def patch(self, request):
        """Toggle sleep mode for the current cycle."""
        log, _ = get_or_create_current_cycle_log(request.user)

        if log is None:
            return CustomResponse.error(
                message='No check-in time configured. Please set up your safety info first.',
                status_code=400,
            )
        if log.status == MonitoringLog.STATUS_CHECKED_IN:
            return CustomResponse.error(
                message='Already checked in for this cycle. Sleep mode not needed.',
                status_code=400,
            )

        log.sleep_mode = not log.sleep_mode
        log.save(update_fields=['sleep_mode', 'updated_at'])

        if log.sleep_mode:
            message = 'Sleep mode enabled. Monitoring is paused for today.'
        else:
            message = 'Sleep mode disabled. Monitoring has resumed.'

        return CustomResponse.success(
            message=message,
            data={
                'target_time': log.target_time,
                'sleep_mode': log.sleep_mode,
            },
        )
