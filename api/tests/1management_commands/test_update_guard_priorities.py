"""
Test update_guard_priorities management command.

This command recalculates priority_number for all active guards
based on weighted points history from the last N weeks.
Higher points = higher priority number.
"""
import pytest
from io import StringIO
from django.core.management import call_command
from django.utils import timezone
from datetime import timedelta
from api.api_models import Guard, Point, SystemSettings
from decimal import Decimal


@pytest.mark.django_db
class TestUpdateGuardPrioritiesCommand:
    """Test update_guard_priorities management command."""
    
    def test_update_priorities_based_on_points(self, guard_user, second_guard_user, system_settings):
        """Test that guard with more points gets higher priority."""
        guard1 = Guard.objects.get(user=guard_user)
        guard2 = Guard.objects.get(user=second_guard_user)
        
        # Reset priority numbers
        guard1.priority_number = Decimal('0')
        guard1.save()
        guard2.priority_number = Decimal('0')
        guard2.save()
        
        # Calculate date within current week (priority looks at recent weeks)
        today = timezone.now().date()
        days_since_monday = today.weekday()
        week_start = today - timedelta(days=days_since_monday)
        point_date = week_start + timedelta(days=1)  # Tuesday of this week
        
        # Give guard1 more points than guard2 with date_awarded in current week
        p1 = Point.objects.create(guard=guard1, points=Decimal('10.0'), explanation="Test points")
        p1.date_awarded = point_date
        p1.save()
        
        p2 = Point.objects.create(guard=guard2, points=Decimal('3.0'), explanation="Test points")
        p2.date_awarded = point_date
        p2.save()
        
        # Run command
        out = StringIO()
        call_command('update_guard_priorities', stdout=out)
        
        # Refresh from DB
        guard1.refresh_from_db()
        guard2.refresh_from_db()
        
        # Guard with more points should have higher priority
        assert guard1.priority_number > guard2.priority_number, \
            f"Guard1 (10pts) should have higher priority than Guard2 (3pts). " \
            f"Got {guard1.priority_number} vs {guard2.priority_number}"
    
    def test_update_priorities_changes_values(self, guard_user, system_settings):
        """Test that running command actually updates priority_number."""
        guard = Guard.objects.get(user=guard_user)
        
        # Set initial priority to 0
        guard.priority_number = Decimal('0')
        guard.save()
        
        # Add points with date in current week
        today = timezone.now().date()
        days_since_monday = today.weekday()
        week_start = today - timedelta(days=days_since_monday)
        point_date = week_start + timedelta(days=1)
        
        p = Point.objects.create(guard=guard, points=Decimal('5.0'), explanation="Test")
        p.date_awarded = point_date
        p.save()
        
        # Run command
        out = StringIO()
        call_command('update_guard_priorities', stdout=out)
        
        # Refresh and verify priority changed
        guard.refresh_from_db()
        assert guard.priority_number != Decimal('0'), \
            "Priority should be updated based on points"
    
    def test_update_priorities_no_guards(self):
        """Test priority update with no guards."""
        # Delete all guards
        Guard.objects.all().delete()
        
        # Run command - should not crash
        out = StringIO()
        call_command('update_guard_priorities', stdout=out)
        
        output = out.getvalue()
        assert '✓' in output or 'updat' in output.lower() or 'no guards' in output.lower()
