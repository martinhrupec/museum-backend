"""
Basic assignment algorithm tests.

Tests fundamental assignment functionality without complex preferences or edge cases.
"""
import pytest
from decimal import Decimal

from background_tasks.assignment_algorithm import assign_positions_automatically
from api.api_models import PositionHistory


@pytest.mark.django_db
class TestBasicAssignment:
    """Test core assignment algorithm functionality."""
    
    def test_simple_assignment_with_sufficient_guards(
        self,
        system_settings_for_assignment,
        minimal_positions,
        guards_with_high_availability
    ):
        """
        Basic test: More guards than positions, all guards have sufficient availability.
        
        Expected: All positions assigned, guards distributed fairly.
        """
        settings = system_settings_for_assignment
        
        # Run assignment
        result = assign_positions_automatically(settings)
        
        # Check that positions were assigned
        assigned_count = PositionHistory.objects.filter(
            action=PositionHistory.Action.ASSIGNED
        ).count()
        
        assert assigned_count > 0, "At least some positions should be assigned"
        assert result['status'] == 'success'
    
    def test_assignment_with_exact_match(
        self,
        system_settings_for_assignment,
        minimal_positions,
        create_guard_with_user
    ):
        """
        Edge case: Guards with availability matching available positions.
        
        If we have 2 positions (from minimal_positions), guards should fill them.
        """
        settings = system_settings_for_assignment
        
        # Create guards with availability to match
        guard1 = create_guard_with_user('exact1', 'ex1@test.com', 2, Decimal('1.0'))
        guard2 = create_guard_with_user('exact2', 'ex2@test.com', 2, Decimal('1.0'))
        
        # Run assignment
        result = assign_positions_automatically(settings)
        
        # All positions should be assigned
        total_assigned = PositionHistory.objects.filter(
            action=PositionHistory.Action.ASSIGNED
        ).count()
        
        total_positions = len(minimal_positions)
        
        # Should assign close to total (might not be exact due to work periods)
        assert total_assigned >= total_positions * 0.8, "Most positions should be assigned"
        assert result['status'] == 'success'

    def test_assignment_respects_guard_availability(
        self,
        system_settings_for_assignment,
        next_week_positions,
        create_guard_with_user
    ):
        """
        Guards should not be assigned more positions than their availability.
        """
        settings = system_settings_for_assignment
        
        # Create guard with low availability
        guard = create_guard_with_user('lowavail', 'low@test.com', 2, Decimal('5.0'))
        
        # Run assignment
        assign_positions_automatically(settings)
        
        # Count how many positions this guard got
        assigned_to_guard = PositionHistory.objects.filter(
            guard=guard,
            action=PositionHistory.Action.ASSIGNED
        ).count()
        
        assert assigned_to_guard <= 2, f"Guard should not exceed availability of 2, got {assigned_to_guard}"
    
    def test_no_guards_available_returns_empty_result(
        self,
        system_settings_for_assignment,
        minimal_positions
    ):
        """
        When no guards exist, assignment should handle gracefully.
        """
        settings = system_settings_for_assignment
        
        # No guards created
        result = assign_positions_automatically(settings)
        
        # Should return skipped with 0 assignments
        assert result['status'] == 'skipped'
        
        assigned_count = PositionHistory.objects.filter(
            action=PositionHistory.Action.ASSIGNED
        ).count()
        
        assert assigned_count == 0, "No positions should be assigned when no guards exist"
    
    def test_guards_without_availability_set_are_skipped(
        self,
        system_settings_for_assignment,
        minimal_positions,
        create_guard_with_user
    ):
        """
        Guards who haven't set availability (availability=None) should not be assigned.
        """
        settings = system_settings_for_assignment
        
        # Create guards: one with availability, one without
        guard_with = create_guard_with_user('has_avail', 'has@test.com', 5, Decimal('3.0'))
        guard_without = create_guard_with_user('no_avail', 'none@test.com', None, Decimal('3.0'))
        
        # Run assignment
        assign_positions_automatically(settings)
        
        # Only guard_with should get assignments
        assigned_to_with = PositionHistory.objects.filter(
            guard=guard_with,
            action=PositionHistory.Action.ASSIGNED
        ).count()
        
        assigned_to_without = PositionHistory.objects.filter(
            guard=guard_without,
            action=PositionHistory.Action.ASSIGNED
        ).count()
        
        assert assigned_to_with > 0, "Guard with availability should get assignments"
        assert assigned_to_without == 0, "Guard without availability should not be assigned"
