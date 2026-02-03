"""
Test award_daily_completions management command.

This command awards points for completed positions from today.
- 2.00 points for each completed position (award_for_position_completion)
- 0.50 points for Sunday positions (award_for_sunday_position_completion)
"""
import pytest
from io import StringIO
from django.core.management import call_command
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from api.api_models import Position, Point, Guard, PositionHistory


@pytest.mark.django_db
class TestAwardDailyCompletionsCommand:
    """Test award_daily_completions management command."""
    
    def test_award_for_today_completed_positions(self, guard_user, sample_exhibition, system_settings):
        """Test awarding points for TODAY's completed positions."""
        guard = Guard.objects.get(user=guard_user)
        exhibition = sample_exhibition
        settings = system_settings
        
        # Set award amounts
        settings.award_for_position_completion = Decimal('2.00')
        settings.award_for_sunday_position_completion = Decimal('0.50')
        settings.save()
        
        # Create TODAY's position and assign to guard
        today = timezone.now().date()
        position = Position.objects.create(
            exhibition=exhibition,
            date=today,
            start_time=settings.weekday_morning_start,
            end_time=settings.weekday_morning_end
        )
        
        # Create position history (ASSIGNED = completed position for award)
        PositionHistory.objects.create(
            position=position,
            guard=guard,
            action=PositionHistory.Action.ASSIGNED
        )
        
        initial_points_count = Point.objects.filter(guard=guard).count()
        
        # Run command
        out = StringIO()
        call_command('award_daily_completions', stdout=out)
        
        # Verify points were awarded
        final_points_count = Point.objects.filter(guard=guard).count()
        assert final_points_count > initial_points_count, "Award points should be created"
        
        # Check award value (depends on day of week)
        award = Point.objects.filter(guard=guard).order_by('-date_awarded').first()
        is_sunday = today.weekday() == 6
        expected_amount = Decimal('0.50') if is_sunday else Decimal('2.00')
        assert award.points == expected_amount, f"Award should be {expected_amount}"
        assert 'completed' in award.explanation.lower() or exhibition.name in award.explanation
    
    def test_no_award_for_future_positions(self, guard_user, sample_exhibition, system_settings):
        """Test command doesn't award for positions not today."""
        guard = Guard.objects.get(user=guard_user)
        exhibition = sample_exhibition
        settings = system_settings
        
        # Create TOMORROW's position (not today)
        tomorrow = timezone.now().date() + timedelta(days=1)
        position = Position.objects.create(
            exhibition=exhibition,
            date=tomorrow,
            start_time=settings.weekday_morning_start,
            end_time=settings.weekday_morning_end
        )
        
        # Assign position
        PositionHistory.objects.create(
            position=position,
            guard=guard,
            action=PositionHistory.Action.ASSIGNED
        )
        
        # Run command
        out = StringIO()
        call_command('award_daily_completions', stdout=out)
        
        # Verify no points were awarded (position is not today)
        assert not Point.objects.filter(guard=guard).exists(), "No award for future positions"
    
    def test_no_award_for_cancelled_positions(self, guard_user, sample_exhibition, system_settings):
        """Test no award for positions that were cancelled (last action is CANCELLED)."""
        guard = Guard.objects.get(user=guard_user)
        exhibition = sample_exhibition
        settings = system_settings
        
        # Create today's position
        today = timezone.now().date()
        position = Position.objects.create(
            exhibition=exhibition,
            date=today,
            start_time=settings.weekday_morning_start,
            end_time=settings.weekday_morning_end
        )
        
        # First assign, then cancel
        PositionHistory.objects.create(
            position=position,
            guard=guard,
            action=PositionHistory.Action.ASSIGNED
        )
        PositionHistory.objects.create(
            position=position,
            guard=guard,
            action=PositionHistory.Action.CANCELLED
        )
        
        # Run command
        out = StringIO()
        call_command('award_daily_completions', stdout=out)
        
        # Verify no points (last action was CANCELLED, not ASSIGNED)
        assert not Point.objects.filter(guard=guard).exists(), "No award for cancelled positions"
