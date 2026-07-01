import zoneinfo
from datetime import datetime, timedelta, timezone as dt_timezone
from django.utils import timezone

def calculate_next_check_in_target(anchor_time, frequency_hours, from_time=None, user_timezone='UTC'):
    if from_time is None:
        from_time = timezone.now()

    try:
        tz = zoneinfo.ZoneInfo(user_timezone)
    except Exception:
        tz = zoneinfo.ZoneInfo('UTC')

    # Convert from_time to the user's local timezone to get the correct "today's date"
    local_from_time = from_time.astimezone(tz)

    # Create today's anchor datetime in the user's local timezone
    local_anchor_datetime_today = timezone.make_aware(
        datetime.combine(local_from_time.date(), anchor_time),
        timezone=tz
    )

    # Convert back to UTC for the database and candidate calculation
    anchor_datetime_today = local_anchor_datetime_today.astimezone(dt_timezone.utc)

    # Compute all possible targets within a 48 hour window centered around today
    # to ensure we find the immediate next one safely.
    candidates = []
    
    # Base could be yesterday's anchor to guarantee we cover all slots
    base_anchor = anchor_datetime_today - timedelta(days=1)
    
    # Generate 10 slots ahead just to be safe
    for i in range(10):
        candidate = base_anchor + timedelta(hours=i * frequency_hours)
        candidates.append(candidate)
        
    # Find the earliest candidate that is strictly in the future relative to from_time
    for candidate in candidates:
        if candidate > from_time:
            return candidate

    # Fallback (should theoretically never hit)
    return anchor_datetime_today + timedelta(hours=frequency_hours)
