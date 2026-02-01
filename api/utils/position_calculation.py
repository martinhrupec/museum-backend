"""
Helper functions for calculating which positions match guard's work periods.

Guards select time periods (day + shift type), and the system dynamically
calculates which Position objects match these availability periods.
"""

from datetime import datetime, time
from django.db.models import Q
from ..api_models import Position, GuardWorkPeriod, SystemSettings


def get_positions_for_guard_periods(guard, next_week_start=None):
    """
    Calculate which Position objects match guard's work periods for next week.
    
    Args:
        guard: Guard instance
        next_week_start: Date of next week start (optional, gets from SystemSettings if not provided)
    
    Returns:
        QuerySet of Position objects that match guard's work periods
    
    Logic:
        1. Get guard's work periods (template or specific week)
        2. For each period, determine shift time range from SystemSettings
        3. Find Position objects matching day_of_week and time range
        4. Return union of all matching positions
    """
    # Get SystemSettings
    settings = SystemSettings.get_active()
    
    if next_week_start is None:
        if not settings.next_week_start:
            return Position.objects.none()
        next_week_start = settings.next_week_start
    
    next_week_end = settings.next_week_end
    
    # Get guard's work periods (prefer specific week over template)
    work_periods = GuardWorkPeriod.objects.filter(
        guard=guard,
        next_week_start=next_week_start,
        is_template=False
    )
    
    if not work_periods.exists():
        # Fall back to template if no specific periods for this week
        work_periods = GuardWorkPeriod.objects.filter(
            guard=guard,
            is_template=True
        )
    
    if not work_periods.exists():
        # No periods set - default behavior: guard can work ALL positions
        return Position.objects.filter(
            date__gte=next_week_start,
            date__lte=next_week_end
        )
    
    # Build query for matching positions
    position_queries = []
    
    for period in work_periods:
        # Calculate actual dates for this day_of_week in next_week
        from datetime import timedelta
        
        # Calculate which date in next_week corresponds to this day_of_week
        days_offset = period.day_of_week - next_week_start.weekday()
        if days_offset < 0:
            days_offset += 7  # If day is earlier in week, it's next occurrence
        
        target_date = next_week_start + timedelta(days=days_offset)
        
        # Determine if this is a weekend day
        is_weekend = period.day_of_week in [5, 6]  # Saturday=5, Sunday=6
        
        # Get shift time range from SystemSettings
        if period.shift_type == 'morning':
            if is_weekend:
                shift_start = settings.weekend_morning_start
                shift_end = settings.weekend_morning_end
            else:
                shift_start = settings.weekday_morning_start
                shift_end = settings.weekday_morning_end
        else:  # afternoon
            if is_weekend:
                shift_start = settings.weekend_afternoon_start
                shift_end = settings.weekend_afternoon_end
            else:
                shift_start = settings.weekday_afternoon_start
                shift_end = settings.weekday_afternoon_end
        
        # Find positions matching this date and time range
        # A position matches if it overlaps with the shift time
        period_query = Q(
            date=target_date,
            start_time__lte=shift_end,  # Position starts at or before shift ends
            end_time__gte=shift_start   # Position ends at or after shift starts
        )
        
        position_queries.append(period_query)
    
    # Combine all queries with OR
    combined_query = position_queries[0]
    for query in position_queries[1:]:
        combined_query |= query
    
    return Position.objects.filter(combined_query).distinct()


def get_guard_work_periods_summary(guard, next_week_start=None):
    """
    Get a summary of guard's work periods and matching position count.
    
    Args:
        guard: Guard instance
        next_week_start: Date of next week start (optional)
    
    Returns:
        dict with:
            - periods: list of work period dictionaries
            - matching_positions_count: number of positions matching these periods
            - is_using_template: whether using template or specific week periods
    """
    settings = SystemSettings.get_active()
    
    if next_week_start is None:
        next_week_start = settings.next_week_start
    
    # Get work periods
    specific_periods = GuardWorkPeriod.objects.filter(
        guard=guard,
        next_week_start=next_week_start,
        is_template=False
    )
    
    if specific_periods.exists():
        periods = specific_periods
        is_using_template = False
    else:
        periods = GuardWorkPeriod.objects.filter(
            guard=guard,
            is_template=True
        )
        is_using_template = True
    
    # Get matching positions
    matching_positions = get_positions_for_guard_periods(guard, next_week_start)
    
    # Format periods for response
    periods_data = [
        {
            'day_of_week': p.day_of_week,
            'day_name': p.get_day_of_week_display(),
            'shift_type': p.shift_type,
            'is_template': p.is_template
        }
        for p in periods
    ]
    
    return {
        'periods': periods_data,
        'matching_positions_count': matching_positions.count(),
        'is_using_template': is_using_template
    }


def calculate_max_availability_for_week(next_week_start, next_week_end):
    """
    Calculate maximum availability for next week based on:
    - SystemSettings workdays (which days museum is open)
    - Morning and afternoon shifts (2 shifts per workday)
    - NonWorkingDay entries (full day = -2 shifts, half day = -1 shift)
    
    Returns: (max_availability, breakdown_dict)
    """
    from ..api_models import NonWorkingDay
    
    settings = SystemSettings.get_active()
    workdays = settings.workdays
    
    # Start with 2 shifts per workday (morning + afternoon)
    total_shifts = len(workdays) * 2
    
    # Subtract shifts for non-working days
    non_working_days = NonWorkingDay.objects.filter(
        date__gte=next_week_start,
        date__lte=next_week_end
    )
    
    full_days_off = 0
    half_days_off = 0
    
    for nwd in non_working_days:
        if nwd.is_full_day:
            full_days_off += 1
            total_shifts -= 2  # Both morning and afternoon
        else:
            half_days_off += 1
            total_shifts -= 1  # Only one shift
    
    breakdown = {
        'base_workdays': len(workdays),
        'base_shifts': len(workdays) * 2,
        'full_days_off': full_days_off,
        'half_days_off': half_days_off,
        'shifts_removed': (full_days_off * 2) + half_days_off,
        'final_max_availability': total_shifts
    }
    
    return total_shifts, breakdown
