"""
Test expire_swap_requests management command.

This command expires pending swap requests where expires_at has passed.
For each expired request:
- Status changed to 'expired'
- PositionHistory CANCELLED created
- Penalty points assigned (penalty_for_position_cancellation_on_the_position_day)
"""
import pytest
from io import StringIO
from django.core.management import call_command
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from api.api_models import PositionSwapRequest, Position, Guard, PositionHistory, Point


@pytest.mark.django_db
class TestExpireSwapRequestsCommand:
    """Test expire_swap_requests management command."""
    
    def test_expire_old_swap_requests(self, guard_user, second_guard_user, sample_exhibition, system_settings):
        """Test expiring swap requests with past expires_at date."""
        guard1 = Guard.objects.get(user=guard_user)
        exhibition = sample_exhibition
        settings = system_settings
        
        # Set penalty amount
        settings.penalty_for_position_cancellation_on_the_position_day = Decimal('-5.00')
        settings.save()
        
        # Create position assigned to guard1
        position1 = Position.objects.create(
            exhibition=exhibition,
            date=timezone.now().date() + timedelta(days=10),
            start_time=settings.weekday_morning_start,
            end_time=settings.weekday_morning_end
        )
        PositionHistory.objects.create(
            position=position1,
            guard=guard1,
            action=PositionHistory.Action.ASSIGNED
        )
        
        # Create expired swap request
        old_swap = PositionSwapRequest.objects.create(
            requesting_guard=guard1,
            position_to_swap=position1,
            status=PositionSwapRequest.STATUS_PENDING,
            expires_at=timezone.now() - timedelta(hours=1),  # Already expired
        )
        
        initial_points_count = Point.objects.filter(guard=guard1).count()
        
        # Run command
        out = StringIO()
        call_command('expire_swap_requests', stdout=out)
        
        # Verify swap request status changed
        old_swap.refresh_from_db()
        assert old_swap.status == 'expired', "Swap request should be expired"
        
        # Verify PositionHistory CANCELLED was created
        cancelled_history = PositionHistory.objects.filter(
            position=position1,
            guard=guard1,
            action=PositionHistory.Action.CANCELLED
        )
        assert cancelled_history.exists(), "CANCELLED history should be created"
        
        # Verify penalty was created
        final_points_count = Point.objects.filter(guard=guard1).count()
        assert final_points_count > initial_points_count, "Penalty should be created"
        
        penalty = Point.objects.filter(guard=guard1).order_by('-date_awarded').first()
        assert penalty.points == Decimal('-5.00')
        assert 'no-show' in penalty.explanation.lower() or 'swap' in penalty.explanation.lower()
    
    def test_keep_recent_swap_requests(self, guard_user, sample_exhibition, system_settings):
        """Test that swap requests with future expires_at are not expired."""
        guard1 = Guard.objects.get(user=guard_user)
        exhibition = sample_exhibition
        settings = system_settings
        
        # Create position
        position1 = Position.objects.create(
            exhibition=exhibition,
            date=timezone.now().date() + timedelta(days=10),
            start_time=settings.weekday_morning_start,
            end_time=settings.weekday_morning_end
        )
        PositionHistory.objects.create(
            position=position1,
            guard=guard1,
            action=PositionHistory.Action.ASSIGNED
        )
        
        # Create swap request that expires in future
        future_swap = PositionSwapRequest.objects.create(
            requesting_guard=guard1,
            position_to_swap=position1,
            status=PositionSwapRequest.STATUS_PENDING,
            expires_at=timezone.now() + timedelta(days=5),  # Expires in future
        )
        
        # Run command
        out = StringIO()
        call_command('expire_swap_requests', stdout=out)
        
        # Verify swap request is still pending
        future_swap.refresh_from_db()
        assert future_swap.status == PositionSwapRequest.STATUS_PENDING, "Future swap should remain pending"
        
        # Verify no penalty was created
        assert not Point.objects.filter(guard=guard1).exists(), "No penalty for future swaps"
