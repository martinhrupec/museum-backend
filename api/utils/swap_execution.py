"""
Position swap execution utilities.

Handles the actual swapping of positions between guards.
"""
import structlog
from django.db import transaction
from django.utils import timezone
from django.core.cache import cache

from api.api_models.schedule import PositionHistory
from api.api_models.textual_model import AdminNotification

logger = structlog.get_logger(__name__)


def perform_position_swap(swap_request, accepting_guard, position_offered):
    """
    Execute the position swap between two guards.
    
    This is atomic - either both swaps succeed or neither does.
    
    Steps:
    1. Create PositionHistory for requesting_guard getting position_offered (swapped)
    2. Create PositionHistory for accepting_guard getting position_to_swap (swapped)
    3. Update swap_request status to 'accepted'
    4. Send notification to requesting_guard
    
    Args:
        swap_request: PositionSwapRequest instance
        accepting_guard: Guard who is accepting the swap
        position_offered: Position that accepting_guard is offering in return
    
    Returns:
        dict: {
            'success': bool,
            'message': str,
            'swap_request': PositionSwapRequest
        }
    
    Raises:
        ValidationError: If swap cannot be completed
    """
    from django.core.exceptions import ValidationError
    from api.api_models.textual_model import PositionSwapRequest
    
    requesting_guard = swap_request.requesting_guard
    position_to_swap = swap_request.position_to_swap
    
    try:
        with transaction.atomic():
            # Race condition protection: Lock swap request during acceptance
            swap_request = PositionSwapRequest.objects.select_for_update().get(pk=swap_request.pk)
            
            # Validate that both positions are still valid for swap
            if not _validate_swap_still_valid(swap_request, accepting_guard, position_offered):
                raise ValidationError("Swap is no longer valid - positions have changed")
            # 1. Requesting guard gets position_offered
            PositionHistory.objects.create(
                position=position_offered,
                guard=requesting_guard,
                action=PositionHistory.ACTION_SWAPPED
            )
            logger.info(
                f"Swap: {requesting_guard.user.username} takes {position_offered} "
                f"from {accepting_guard.user.username}"
            )
            
            # 2. Accepting guard gets position_to_swap
            PositionHistory.objects.create(
                position=position_to_swap,
                guard=accepting_guard,
                action=PositionHistory.ACTION_SWAPPED
            )
            logger.info(
                f"Swap: {accepting_guard.user.username} takes {position_to_swap} "
                f"from {requesting_guard.user.username}"
            )
            
            # 3. Update swap_request
            swap_request.status = 'accepted'
            swap_request.accepted_by_guard = accepting_guard
            swap_request.position_offered_in_return = position_offered
            swap_request.accepted_at = timezone.now()
            swap_request.save()
            
            # 4. Send notification to requesting guard
            _send_swap_accepted_notification(swap_request)
            
            # 5. Invalidate schedule cache for affected weeks
            _invalidate_schedule_cache_for_swap(position_to_swap, position_offered)
            
            return {
                'success': True,
                'message': 'Position swap completed successfully',
                'swap_request': swap_request
            }
            
    except Exception as e:
        logger.error(f"Error performing swap: {e}")
        raise ValidationError(f"Failed to complete swap: {str(e)}")


def _validate_swap_still_valid(swap_request, accepting_guard, position_offered):
    """
    Validate that swap can still be completed.
    
    Checks:
    - Swap request is still pending
    - Requesting guard still has position_to_swap
    - Accepting guard still has position_offered
    - Position_to_swap still has same time slot
    - Position_offered is in the list of valid positions accepting guard can offer
    
    Args:
        swap_request: PositionSwapRequest instance
        accepting_guard: Guard accepting the swap
        position_offered: Position being offered in return
    
    Returns:
        bool: True if swap is still valid
    """
    # Check swap request status
    if swap_request.status != 'pending':
        logger.warning(f"Swap request {swap_request.id} is no longer pending")
        return False
    
    # Check requesting guard still has position_to_swap
    position_to_swap = swap_request.position_to_swap
    latest_history_swap = position_to_swap.position_histories.order_by('-action_time').first()
    
    if not latest_history_swap or latest_history_swap.guard != swap_request.requesting_guard:
        logger.warning(
            f"Requesting guard {swap_request.requesting_guard.user.username} "
            f"no longer has position {position_to_swap.id}"
        )
        return False
    
    if latest_history_swap.action not in [
        PositionHistory.ACTION_ASSIGNED,
        PositionHistory.ACTION_REPLACED,
        PositionHistory.ACTION_SWAPPED
    ]:
        logger.warning(f"Position {position_to_swap.id} is not in assigned state")
        return False
    
    # Check accepting guard still has position_offered
    latest_history_offered = position_offered.position_histories.order_by('-action_time').first()
    
    if not latest_history_offered or latest_history_offered.guard != accepting_guard:
        logger.warning(
            f"Accepting guard {accepting_guard.user.username} "
            f"no longer has position {position_offered.id}"
        )
        return False
    
    if latest_history_offered.action not in [
        PositionHistory.ACTION_ASSIGNED,
        PositionHistory.ACTION_REPLACED,
        PositionHistory.ACTION_SWAPPED
    ]:
        logger.warning(f"Position {position_offered.id} is not in assigned state")
        return False
    
    # Check that position_offered is valid for this swap
    from api.utils.swap_eligibility import check_guard_eligibility_for_swap
    
    eligibility = check_guard_eligibility_for_swap(accepting_guard, swap_request)
    
    if not eligibility['is_eligible']:
        logger.warning(
            f"Guard {accepting_guard.user.username} is no longer eligible "
            f"for swap {swap_request.id}: {eligibility['reason']}"
        )
        return False
    
    if position_offered not in eligibility['positions_can_offer']:
        logger.warning(
            f"Position {position_offered.id} is not in list of positions "
            f"guard {accepting_guard.user.username} can offer"
        )
        return False
    
    return True


def _send_swap_accepted_notification(swap_request):
    """
    Send unicast notification to requesting guard that swap was accepted.
    
    Args:
        swap_request: PositionSwapRequest instance with status='accepted'
    """
    requesting_user = swap_request.requesting_guard.user
    accepting_guard_name = swap_request.accepted_by_guard.user.get_full_name()
    
    position_to_swap = swap_request.position_to_swap
    position_offered = swap_request.position_offered_in_return
    
    message = (
        f"{accepting_guard_name} je prihvatio/la vašu zamjenu!\n\n"
        f"Dajete: {position_to_swap.exhibition.name} - "
        f"{position_to_swap.date.strftime('%d.%m.%Y')} "
        f"{position_to_swap.start_time.strftime('%H:%M')}-{position_to_swap.end_time.strftime('%H:%M')}\n\n"
        f"Dobivate: {position_offered.exhibition.name} - "
        f"{position_offered.date.strftime('%d.%m.%Y')} "
        f"{position_offered.start_time.strftime('%H:%M')}-{position_offered.end_time.strftime('%H:%M')}"
    )
    
    AdminNotification.objects.create(
        created_by=None,  # System-generated
        title="Zamjena pozicije prihvaćena",
        message=message,
        cast_type=AdminNotification.CAST_UNICAST,
        to_user=requesting_user
    )
    
    logger.info(
        f"Sent swap accepted notification to {requesting_user.username} "
        f"for swap request {swap_request.id}"
    )


def _invalidate_schedule_cache_for_swap(position1, position2):
    """
    Invalidate schedule cache for weeks affected by swap.
    
    Args:
        position1: First position in swap
        position2: Second position in swap
    """
    from api.api_models.system_settings import SystemSettings
    
    settings = SystemSettings.get_active()
    
    # Check all positions against both weeks
    positions_to_check = [position1, position2]
    
    for position in positions_to_check:
        # Check this_week
        if settings.this_week_start and settings.this_week_end:
            if settings.this_week_start <= position.date <= settings.this_week_end:
                cache_key = f'schedule_this_week_{settings.this_week_start.isoformat()}'
                cache.delete(cache_key)
                logger.info(f"Invalidated cache: {cache_key}")
        
        # Check next_week
        if settings.next_week_start and settings.next_week_end:
            if settings.next_week_start <= position.date <= settings.next_week_end:
                cache_key = f'schedule_next_week_{settings.next_week_start.isoformat()}'
                cache.delete(cache_key)
                logger.info(f"Invalidated cache: {cache_key}")

