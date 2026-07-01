from rest_framework.response import Response
from django.utils import timezone


class CustomResponse:

    @staticmethod
    def success(message, data=None, status_code=200):
        response_data = {
            "success": True,
            "statusCode": status_code,
            "message": message,
            "timestamp": timezone.now().isoformat(),
            "data": data,
            "errors": None,
        }
        return Response(response_data, status=status_code)

    @staticmethod
    def error(message, status_code=400, data=None, errors=None):
        # If we have detailed errors, bubble up the first specific error into the main message for convenience
        if errors and isinstance(errors, dict) and message in ["Validation failed.", "Invalid data"]:
            first_key = next(iter(errors), None)
            if first_key:
                first_val = errors[first_key]
                if isinstance(first_val, list) and len(first_val) > 0:
                    message = str(first_val[0])
                elif isinstance(first_val, str):
                    message = first_val

        response_data = {
            "success": False,
            "statusCode": status_code,
            "message": message,
            "timestamp": timezone.now().isoformat(),
            "data": data,
            "errors": errors,
        }
        return Response(response_data, status=status_code)
