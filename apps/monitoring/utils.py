from datetime import datetime, timedelta
from django.utils import timezone

def calculate_next_check_in_target(anchor_time, frequency_hours, from_time=None):
    if from_time is None:
        from_time = timezone.now()

    # Create today's anchor datetime
    anchor_datetime_today = timezone.make_aware(
        datetime.combine(from_time.date(), anchor_time)
    )

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
