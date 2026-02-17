"""
Position swap eligibility utilities.

Handles checking if guards are eligible to accept swap requests
and determining which positions they can offer in return.
"""
import structlog
from datetime import timedelta
from django.db.models import Q
from django.utils import timezone

from api.api_models.calculation import GuardWorkPeriod
from api.api_models.schedule import Position, PositionHistory
from api.api_models.system_settings import SystemSettings

logger = structlog.get_logger(__name__)


def _get_week_start_from_date(date):
    """
    Calculate Monday (week start) from any date.
    
    Args:
        date: Date object
    
    Returns:
        date: Monday of the week containing the input date
    """
    return date - timedelta(days=date.weekday())


def guard_has_work_periods(guard):
    """
    Check if guard has any work periods (template or specific week).
    
    Args:
        guard: Guard instance
    
    Returns:
        bool: True if guard has work periods configured
    """
    return GuardWorkPeriod.objects.filter(guard=guard).exists()


def get_work_period_for_position(guard, position):
    """
    Get guard's work period that covers the given position.
    
    With the new schema, ALL work periods have next_week_start set (even templates).
    Uses the week_start (Monday) of the position's date for lookup.
    
    Args:
        guard: Guard instance
        position: Position instance
    
    Returns:
        GuardWorkPeriod or None: Matching work period if found
    """
    day_of_week = position.date.weekday()
    shift_type = get_shift_type_for_position(position)
    
    # Calculate week_start (Monday) from position date
    week_start = _get_week_start_from_date(position.date)
    
    # Find work period for this week (both templates and non-templates now have next_week_start)
    work_period = GuardWorkPeriod.objects.filter(
        guard=guard,
        next_week_start=week_start,
        day_of_week=day_of_week,
        shift_type=shift_type
    ).first()
    
    return work_period


def get_shift_type_for_position(position):
    """
    Determine shift type (morning/afternoon) for a position.
    
    Args:
        position: Position instance
    
    Returns:
        str: 'morning' or 'afternoon'
    """
    settings = SystemSettings.get_active()
    is_weekend = position.date.weekday() in [5, 6]
    
    if is_weekend:
        morning_start = settings.weekend_morning_start
    else:
        morning_start = settings.weekday_morning_start
    
    return 'morning' if position.start_time == morning_start else 'afternoon'


def is_guard_assigned_in_period(guard, position):
    """
    Check if guard already has a position assigned in the same time period.
    
    Args:
        guard: Guard instance
        position: Position instance to check period for
    
    Returns:
        bool: True if guard is already assigned in that time slot
    """
    # Get all positions in the same time slot
    overlapping_positions = Position.objects.filter(
        date=position.date,
        start_time=position.start_time,
        end_time=position.end_time
    )
    
    # Check if guard has latest history (assigned/replaced/swapped) on any of them
    for pos in overlapping_positions:
        latest_history = pos.position_histories.order_by('-action_time').first()
        if latest_history and latest_history.guard == guard:
            if latest_history.action in [
                PositionHistory.Action.ASSIGNED,
                PositionHistory.Action.REPLACED,
                PositionHistory.Action.SWAPPED
            ]:
                return True
    
    return False


def get_guard_assigned_positions_in_week(guard, week_start, week_end):
    """
    Get all positions where guard is currently assigned in given week.
    
    Args:
        guard: Guard instance
        week_start: Date of week start
        week_end: Date of week end
    
    Returns:
        list: List of Position instances where guard is assigned
    """
    assigned_positions = []
    
    # Get all positions in the week
    positions = Position.objects.filter(
        date__gte=week_start,
        date__lte=week_end
    )
    
    for position in positions:
        latest_history = position.position_histories.order_by('-action_time').first()
        if latest_history and latest_history.guard == guard:
            if latest_history.action in [
                PositionHistory.Action.ASSIGNED,
                PositionHistory.Action.REPLACED,
                PositionHistory.Action.SWAPPED
            ]:
                assigned_positions.append(position)
    
    return assigned_positions


def can_guard_take_position(guard, position):
    """
    Check if guard can take the given position (has work period and is free).
    
    Args:
        guard: Guard instance
        position: Position instance
    
    Returns:
        bool: True if guard can work this position
    """
    # Must have work periods configured
    if not guard_has_work_periods(guard):
        return False
    
    # Must have work period covering this position
    work_period = get_work_period_for_position(guard, position)
    if not work_period:
        return False
    
    # Must not be already assigned in this time slot
    if is_guard_assigned_in_period(guard, position):
        return False
    
    return True


def check_guard_eligibility_for_swap(guard, swap_request):
    """
    Check if guard is eligible to accept a swap request.
    
    Returns dictionary with eligibility status and positions guard can offer.
    
    Eligibility criteria:
    1. Guard has work_periods configured (template or specific) - SKIPPED for special events
    2. Guard has work_period covering position_to_swap - SKIPPED for special events
    3. Guard is NOT already assigned in that time slot
    4. Guard has at least one position that requesting_guard can take
    
    Args:
        guard: Guard instance to check
        swap_request: PositionSwapRequest instance
    
    Returns:
        dict: {
            'is_eligible': bool,
            'positions_can_offer': [Position],
            'reason': str (if not eligible)
        }
    """
    position_wanted = swap_request.position_to_swap
    requesting_guard = swap_request.requesting_guard
    
    # Don't allow guard to accept their own request
    if guard == requesting_guard:
        return {
            'is_eligible': False,
            'positions_can_offer': [],
            'reason': 'Cannot accept your own swap request'
        }
    
    # For special events, skip work_period checks (all guards can accept)
    if not position_wanted.is_special_event:
        # 1. Check if guard has work_periods (only for regular exhibitions)
        if not guard_has_work_periods(guard):
            return {
                'is_eligible': False,
                'positions_can_offer': [],
                'reason': 'Guard has no work periods configured'
            }
        
        # 2. Check if guard has work_period covering position_wanted (only for regular exhibitions)
        work_period = get_work_period_for_position(guard, position_wanted)
        if not work_period:
            return {
                'is_eligible': False,
                'positions_can_offer': [],
                'reason': 'Guard does not have work period for this position'
            }
    
    # 3. Check if guard is free in that time slot
    if is_guard_assigned_in_period(guard, position_wanted):
        return {
            'is_eligible': False,
            'positions_can_offer': [],
            'reason': 'Guard is already assigned in this time slot'
        }
    
    # 4. Find positions guard can offer (where they're assigned and requesting_guard can take)
    settings = SystemSettings.get_active()
    week_start = settings.this_week_start
    week_end = settings.this_week_end
    
    guard_assigned_positions = get_guard_assigned_positions_in_week(guard, week_start, week_end)
    
    positions_can_offer = []
    for pos in guard_assigned_positions:
        if can_guard_take_position(requesting_guard, pos):
            positions_can_offer.append(pos)
    
    if not positions_can_offer:
        return {
            'is_eligible': False,
            'positions_can_offer': [],
            'reason': 'No positions available to offer in return'
        }
    
    return {
        'is_eligible': True,
        'positions_can_offer': positions_can_offer,
        'reason': None
    }


def get_eligible_guards_for_swap(swap_request):
    """
    Get all guards who are eligible to accept the swap request.
    
    Args:
        swap_request: PositionSwapRequest instance
    
    Returns:
        list: List of dicts with guard and positions they can offer
            [{'guard': Guard, 'positions_can_offer': [Position]}]
    """
    from api.api_models.user_type import Guard
    
    eligible_guards = []
    
    # Check all active guards except the requesting guard
    for guard in Guard.active_objects.exclude(id=swap_request.requesting_guard.id):
        eligibility = check_guard_eligibility_for_swap(guard, swap_request)
        
        if eligibility['is_eligible']:
            eligible_guards.append({
                'guard': guard,
                'positions_can_offer': eligibility['positions_can_offer']
            })
    
    return eligible_guards
