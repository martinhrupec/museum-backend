"""
Guard work period utilities for assignment algorithm.

Handles guard availability and work period retrieval with fallback logic.
"""
import structlog
from api.api_models.calculation import GuardWorkPeriod
from api.api_models.schedule import Position
from api.api_models.system_settings import SystemSettings

logger = structlog.get_logger(__name__)


def get_guard_work_periods(guard, next_week_start, next_week_end):
    """
    Get guard's work periods for a specific week.
    
    With the new schema, ALL work periods have next_week_start set (even templates).
    Priority:
    1. Periods matching next_week_start (template or non-template)
    2. Fallback: ALL available shifts (if availability set but no periods)
    
    Args:
        guard: Guard instance
        next_week_start: Date of week start
        next_week_end: Date of week end
    
    Returns:
        list: List of (day_of_week, shift_type) tuples
        Empty list if guard has no availability set
    """
    # Check if guard has availability set
    if guard.availability is None or guard.availability == 0:
        logger.debug(f"Guard {guard.user.username} has no availability - returning empty periods")
        return []
    
    # Find periods for this specific week (both templates and non-templates now have next_week_start)
    week_periods = GuardWorkPeriod.objects.filter(
        guard=guard,
        next_week_start=next_week_start
    )
    
    if week_periods.exists():
        periods = [(wp.day_of_week, wp.shift_type) for wp in week_periods]
        is_template = week_periods.first().is_template
        logger.debug(f"Guard {guard.user.username}: using week periods ({len(periods)}, template={is_template})")
        return periods
    
    # Fallback: Generate all available shifts from positions in that week
    logger.debug(f"Guard {guard.user.username}: using fallback - all available shifts")
    
    settings = SystemSettings.get_active()
    
    # Get all positions in next_week
    positions = Position.objects.filter(
        date__gte=next_week_start,
        date__lte=next_week_end
    ).values('date', 'start_time').distinct()
    
    available_periods = set()
    
    for pos in positions:
        day_of_week = pos['date'].weekday()
        start_time = pos['start_time']
        
        # Determine shift type based on start_time
        is_weekend = day_of_week in [5, 6]
        
        if is_weekend:
            morning_start = settings.weekend_morning_start
            afternoon_start = settings.weekend_afternoon_start
        else:
            morning_start = settings.weekday_morning_start
            afternoon_start = settings.weekday_afternoon_start
        
        if start_time == morning_start:
            available_periods.add((day_of_week, 'morning'))
        elif start_time == afternoon_start:
            available_periods.add((day_of_week, 'afternoon'))
    
    return list(available_periods)


def get_positions_for_guard(all_positions, guard_work_periods):
    """
    Filter positions that match given work periods.
    
    Args:
        all_positions: QuerySet or list of Position instances
        guard_work_periods: List of (day_of_week, shift_type) tuples
    
    Returns:
        list: Filtered Position instances matching work periods
    """
    if not guard_work_periods:
        # No work periods = can't work any positions
        return []
    
    settings = SystemSettings.get_active()
    
    # Convert work periods to set for fast lookup
    work_periods_set = set(guard_work_periods)
    
    matched_positions = []
    
    for position in all_positions:
        pos_day_of_week = position.date.weekday()
        is_weekend = pos_day_of_week in [5, 6]
        
        # Determine shift type based on position start_time
        if is_weekend:
            morning_start = settings.weekend_morning_start
            morning_end = settings.weekend_morning_end
            afternoon_start = settings.weekend_afternoon_start
            afternoon_end = settings.weekend_afternoon_end
        else:
            morning_start = settings.weekday_morning_start
            morning_end = settings.weekday_morning_end
            afternoon_start = settings.weekday_afternoon_start
            afternoon_end = settings.weekday_afternoon_end
        
        # Check if position overlaps with morning shift
        if (position.start_time <= morning_end and position.end_time >= morning_start):
            if (pos_day_of_week, 'morning') in work_periods_set:
                matched_positions.append(position)
                continue
        
        # Check if position overlaps with afternoon shift
        if (position.start_time <= afternoon_end and position.end_time >= afternoon_start):
            if (pos_day_of_week, 'afternoon') in work_periods_set:
                matched_positions.append(position)
                continue
    
    return matched_positions
