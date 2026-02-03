"""
Test check_penalize_insufficient_positions management command.

This command checks if manual assignment period has ended, and if so,
penalizes guards who have fewer than minimal_number_of_positions_in_week
assigned positions for next_week period.
"""
import pytest
from io import StringIO
from django.core.management import call_command
from django.utils import timezone
from datetime import timedelta
from decimal import Decimal
from api.api_models import Position, Point, Guard, PositionHistory, SystemSettings
from background_tasks.tasks import penalize_insufficient_positions


@pytest.mark.django_db
class TestCheckPenalizeInsufficientPositionsCommand:
    """Test check_and_penalize_insufficient_positions management command."""
    
    def test_penalize_guard_with_insufficient_positions(self, system_settings, guard_user, sample_exhibition):
        """
        Test penalizing guard with insufficient positions for next_week.
        
        The command checks guards who have fewer assigned positions than
        minimal_number_of_positions_in_week for the next_week period.
        """
        guard = Guard.objects.get(user=guard_user)
        exhibition = sample_exhibition
        settings = system_settings
        
        # Set minimal requirement
        settings.minimal_number_of_positions_in_week = 5
        settings.penalty_for_assigning_less_then_minimal_positions = Decimal('-3.00')
        settings.save()
        
        # Create only 2 positions for next_week (less than minimal 5)
        for i in range(2):
            pos = Position.objects.create(
                exhibition=exhibition,
                date=settings.next_week_start + timedelta(days=i),
                start_time=settings.weekday_morning_start,
                end_time=settings.weekday_morning_end
            )
            # Assign to guard
            PositionHistory.objects.create(
                position=pos,
                guard=guard,
                action=PositionHistory.Action.ASSIGNED
            )
        
        initial_points_count = Point.objects.filter(guard=guard).count()
        
        # Call penalize_insufficient_positions directly (bypasses time check)
        result = penalize_insufficient_positions()
        
        # Verify penalty was created
        final_points_count = Point.objects.filter(guard=guard).count()
        assert final_points_count > initial_points_count, "Penalty point should be created"
        
        # Verify penalty explanation contains correct info
        penalty_point = Point.objects.filter(guard=guard).order_by('-date_awarded').first()
        assert 'nedovoljno' in penalty_point.explanation.lower() or '2/5' in penalty_point.explanation
        assert penalty_point.points == Decimal('-3.00')
    
    def test_no_penalty_for_sufficient_positions(self, system_settings, guard_user, sample_exhibition):
        """Test no penalty when guard has sufficient positions for next_week."""
        guard = Guard.objects.get(user=guard_user)
        exhibition = sample_exhibition
        settings = system_settings
        
        # Set minimal requirement
        settings.minimal_number_of_positions_in_week = 3
        settings.penalty_for_assigning_less_then_minimal_positions = Decimal('-3.00')
        settings.save()
        
        # Create 4 positions for next_week (more than minimal 3)
        for i in range(4):
            pos = Position.objects.create(
                exhibition=exhibition,
                date=settings.next_week_start + timedelta(days=min(i, 6)),  # stay within week
                start_time=settings.weekday_morning_start,
                end_time=settings.weekday_morning_end
            )
            # Assign to guard
            PositionHistory.objects.create(
                position=pos,
                guard=guard,
                action=PositionHistory.Action.ASSIGNED
            )
        
        initial_points_count = Point.objects.filter(guard=guard).count()
        
        # Call penalize_insufficient_positions directly
        result = penalize_insufficient_positions()
        
        # Verify no penalty was created
        final_points_count = Point.objects.filter(guard=guard).count()
        assert final_points_count == initial_points_count, "No penalty should be created"
    
    def test_command_runs_without_error(self, system_settings):
        """Test that command completes without crashing."""
        out = StringIO()
        call_command('check_penalize_insufficient_positions', stdout=out)
        
        output = out.getvalue()
        # Command should complete (may return early if period active, or run penalty check)
        assert '✓' in output or 'completed' in output.lower() or 'period' in output.lower()
