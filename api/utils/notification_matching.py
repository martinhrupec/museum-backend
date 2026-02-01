"""
Helper function for matching guards to multicast notifications.

Complex business logic for determining if a guard matches notification criteria
based on date ranges, exhibitions, shift types, and position assignments.
"""

from datetime import timedelta
from django.utils import timezone


def guard_matches_multicast(guard, notification):
    """
    Check if guard matches multicast notification criteria.
    
    Logic:
    notification_date postavljen?
    ├─ DA → Provjeri SAMO taj dan (ignoriraj this/next week)
    │       ├─ + exhibition → samo ta izložba taj dan
    │       ├─ + shift_type → samo ta smjena taj dan
    │       └─ + oba → kombinacija
    │
    └─ NE → Provjeri this_week(od danas) + next_week period - presjek intervala 
    s onim od danas do expires_at
            ├─ + exhibition → svi na toj izložbi u oba perioda
            ├─ + shift_type → svi u toj smjeni u oba perioda
            └─ + oba → kombinacija u oba perioda
    
    Then check if guard is ASSIGNED to any matching position via PositionHistory.
    
    Args:
        guard: Guard instance
        notification: AdminNotification instance
    
    Returns:
        bool: True if guard matches notification criteria
    """
    from ..api_models import SystemSettings, Position, PositionHistory, AdminNotification
    
    settings = SystemSettings.get_active()
    today = timezone.now().date()
    
    # Determine date range based on notification_date
    if notification.notification_date:
        # CASE 1: notification_date set → Check ONLY that specific day (ignore this/next week)
        date_range = [notification.notification_date]
    else:
        # CASE 2: notification_date NOT set → Check this_week(from today) + next_week
        #         intersected with (today → expires_at)
        
        if not settings.this_week_start or not settings.next_week_end:
            return False  # Can't determine working periods
        
        # Interval 1: today → expires_at (notification validity)
        if notification.expires_at:
            interval1_end = notification.expires_at.date()
        else:
            # No expiry = far future
            from datetime import date
            interval1_end = date(2099, 12, 31)
        
        # Interval 2: today → next_week_end (this_week + next_week working period)
        interval2_end = settings.next_week_end
        
        # Intersection: today → min(interval1_end, interval2_end)
        date_range_end = min(interval1_end, interval2_end)
        
        if date_range_end < today:
            return False  # No valid date range
        
        # Generate all dates in range
        date_range = []
        current_date = today
        while current_date <= date_range_end:
            date_range.append(current_date)
            current_date += timedelta(days=1)
    
    if not date_range:
        return False
    
    # Build position filter
    position_filter = {'date__in': date_range}
    
    if notification.shift_type:
        # Determine shift start_time for each date
        start_times = []
        for check_date in date_range:
            is_weekend = check_date.weekday() in [5, 6]
            if notification.shift_type == AdminNotification.SHIFT_MORNING:
                start_time = settings.weekend_morning_start if is_weekend else settings.weekday_morning_start
            else:  # AFTERNOON
                start_time = settings.weekend_afternoon_start if is_weekend else settings.weekday_afternoon_start
            start_times.append(start_time)
        
        # Filter positions with any of these start times
        position_filter['start_time__in'] = list(set(start_times))
    
    if notification.exhibition:
        position_filter['exhibition'] = notification.exhibition
    
    # Find positions matching criteria
    matching_positions = Position.objects.filter(**position_filter)
    
    if not matching_positions.exists():
        return False
    
    # Check if guard is ASSIGNED to any of these positions
    # Use the helper function to get assigned guard for each position
    for position in matching_positions:
        assigned_guard = position.get_assigned_guard()
        if assigned_guard == guard:
            return True
    
    return False
