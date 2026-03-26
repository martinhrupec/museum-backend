"""
Dynamic minimum positions calculator.

Calculates minimal_number_of_positions_in_week based on supply/demand analysis.
Called during automated assignment process.
"""
from decimal import Decimal
from datetime import timedelta
import structlog

logger = structlog.get_logger(__name__)


def _calculate_max_positions_per_guard(settings):
    """
    Calculate maximum positions a guard can physically work in next week.

    Base max = number of workday-slots in next week (each workday contributes 2
    slots: morning + afternoon), minus any slots removed by NonWorkingDay entries.

    Extra slots are added for special events whose time interval does NOT overlap
    with any standard shift on that day (e.g. an opening ceremony 08:00-10:00
    when normal shifts start at 11:00).  Each such event is one additional slot
    a guard can take, so it raises the ceiling by 1.

    Returns:
        int: Maximum number of positions per guard for next week
    """
    from api.api_models.schedule import Exhibition, NonWorkingDay

    next_week_start = settings.next_week_start
    next_week_end = settings.next_week_end

    # Collect non-working day info
    non_working_days = NonWorkingDay.objects.filter(
        date__gte=next_week_start,
        date__lte=next_week_end
    )
    nwd_full = {nwd.date for nwd in non_working_days if nwd.is_full_day}
    nwd_half = {nwd.date for nwd in non_working_days if not nwd.is_full_day}

    # Count standard shift slots
    total_shifts = 0
    current_date = next_week_start
    while current_date <= next_week_end:
        if current_date.weekday() in settings.workdays:
            if current_date in nwd_full:
                pass  # 0 shifts
            elif current_date in nwd_half:
                total_shifts += 1  # one shift cancelled
            else:
                total_shifts += 2  # morning + afternoon
        current_date += timedelta(days=1)

    # Count extra slots from special events outside normal shift hours
    extra_slots = 0
    special_events = Exhibition.objects.filter(
        is_special_event=True,
        start_date__date__gte=next_week_start,
        start_date__date__lte=next_week_end
    )

    for event in special_events:
        event_date = event.start_date.date()
        is_weekend = event_date.weekday() in [5, 6]

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

        # Overlap: event_start < shift_end  AND  event_end > shift_start
        overlaps_morning = (
            event.event_start_time < morning_end and
            event.event_end_time > morning_start
        )
        overlaps_afternoon = (
            event.event_start_time < afternoon_end and
            event.event_end_time > afternoon_start
        )

        if not overlaps_morning and not overlaps_afternoon:
            extra_slots += 1

    return total_shifts + extra_slots


def calculate_and_update_minimum(settings, total_positions):
    """
    Calculate and update minimal_number_of_positions_in_week based on ACTUAL situation.
    
    Uses simple logic after automated assignment:
    1. Count empty positions (no PositionHistory)
    2. Count ALL active guards (inner + outer)
    3. Get actual assigned counts per guard
    4. Iteratively raise minimum until empty positions would be filled
    
    Zaokružuje NA MANJE - ako ne stane, ne dižemo minimum.
    
    Args:
        settings: SystemSettings instance
        total_positions: Total number of positions available for next_week
    
    Returns:
        int: Calculated minimum
    """
    from api.api_models.user_type import Guard
    from api.api_models.schedule import Position, PositionHistory
    
    logger.info("Calculating optimal minimum based on actual situation...")
    
    # Count empty positions (those without any PositionHistory)
    next_week_positions = Position.objects.filter(
        date__gte=settings.next_week_start,
        date__lte=settings.next_week_end
    )
    
    empty_positions_count = sum(
        1 for position in next_week_positions
        if not position.position_histories.exists()
    )
    
    logger.info(f"Empty positions: {empty_positions_count}/{total_positions}")
    
    if empty_positions_count == 0:
        logger.info("All positions filled. Setting minimum to 0.")
        settings.minimal_number_of_positions_in_week = 0
        settings.save()
        return 0
    
    # Get ALL active guards (inner + outer)
    all_active_guards = Guard.active_guards.all()
    
    logger.info(f"Total active guards: {all_active_guards.count()}")
    
    # If no guards exist, minimum is 0
    if not all_active_guards.exists():
        logger.info("No active guards. Setting minimum to 0.")
        settings.minimal_number_of_positions_in_week = 0
        settings.save()
        return 0
    
    # Count actual assigned positions per guard
    guard_assigned_counts = {}
    for guard in all_active_guards:
        assigned_count = 0
        for position in next_week_positions:
            latest_history = position.position_histories.order_by('-action_time', '-id').first()
            if latest_history and latest_history.action in [
                PositionHistory.Action.ASSIGNED,
                PositionHistory.Action.REPLACED,
                PositionHistory.Action.SWAPPED
            ] and latest_history.guard == guard:
                assigned_count += 1
        guard_assigned_counts[guard.id] = assigned_count
    
    logger.info(
        f"Current assignment distribution: "
        f"min={min(guard_assigned_counts.values())}, "
        f"max={max(guard_assigned_counts.values())}, "
        f"avg={sum(guard_assigned_counts.values()) / len(guard_assigned_counts):.1f}"
    )
    
    # Calculate physical upper bound for the minimum
    max_positions_per_guard = _calculate_max_positions_per_guard(settings)
    logger.info(f"Physical maximum positions per guard for next week: {max_positions_per_guard}")

    # Simulate raising minimum
    simulated_counts = guard_assigned_counts.copy()
    minimum = 0

    # Iteratively raise minimum: find all guards at lowest level, raise them by 1
    # Repeat until empty positions would be filled (zaokružuje NA MANJE)
    while True:
        # Find current minimum assigned count across all guards
        current_min = min(simulated_counts.values())

        # Never exceed physical maximum a guard can work in a week
        if current_min + 1 > max_positions_per_guard:
            logger.info(
                f"Cannot raise to {current_min + 1}: "
                f"would exceed physical maximum of {max_positions_per_guard} positions per guard. "
                f"Final minimum = {minimum}"
            )
            break

        guards_at_min = [gid for gid, count in simulated_counts.items() if count == current_min]

        # Test: raise all guards at minimum by 1
        test_counts = simulated_counts.copy()
        for gid in guards_at_min:
            test_counts[gid] = current_min + 1

        # Calculate how many additional positions would be needed
        additional_needed = sum(test_counts[gid] - simulated_counts[gid] for gid in guards_at_min)

        if additional_needed <= empty_positions_count:
            # Fits! Accept this minimum level
            minimum = current_min + 1
            simulated_counts = test_counts
            empty_positions_count -= additional_needed  # Reduce available empty slots
            logger.info(
                f"Minimum raised to {minimum}: "
                f"{len(guards_at_min)} guards raised from {current_min}, "
                f"used {additional_needed} positions, {empty_positions_count} empty remaining"
            )
        else:
            # Doesn't fit! Stop (zaokružuje se NA MANJE)
            logger.info(
                f"Cannot raise to {current_min + 1}: "
                f"would need {additional_needed} positions (> {empty_positions_count} empty). "
                f"Final minimum = {minimum}"
            )
            break
    
    # Update SystemSettings
    settings.minimal_number_of_positions_in_week = minimum
    settings.save()
    
    logger.info(f"Minimum calculated and saved: {minimum}")
    return minimum
