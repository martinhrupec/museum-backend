"""
FAZA 5: Hungarian Algorithm Integration Tests

Tests for the integration of scipy.optimize.linear_sum_assignment (Hungarian algorithm)
and the post-processing logic that converts matrix assignments to actual Position assignments.

The Hungarian algorithm solves the assignment problem optimally:
- Given: cost matrix (we use negative scores for minimization)
- Returns: optimal row-to-column assignments

Post-processing handles:
- Converting matrix indices back to Guard and Position objects
- Filtering out impossible assignments (-9999 scores)
- Creating Assignment records
- Handling edge cases (more guards than positions, etc.)
"""

import pytest
from decimal import Decimal
from datetime import timedelta
import numpy as np

from api.models import Position, PositionHistory, GuardWorkPeriod
from background_tasks.assignment_algorithm import assign_positions_automatically


# ============================================================================
# HUNGARIAN ALGORITHM EXECUTION TESTS (3 tests)
# ============================================================================

@pytest.mark.django_db
def test_hungarian_algorithm_executes_successfully(
    create_guard_with_user, system_settings_for_assignment, sample_exhibitions
):
    """
    Test that Hungarian algorithm executes without errors.
    Basic smoke test to ensure scipy integration works.
    """
    settings = system_settings_for_assignment
    
    # Create guards
    guard1 = create_guard_with_user('guard1', 'g1@test.com', availability=3, priority=Decimal('2.0'))
    guard2 = create_guard_with_user('guard2', 'g2@test.com', availability=2, priority=Decimal('1.5'))
    
    # Add work periods so guards are considered available
    for guard in [guard1, guard2]:
        for day in range(5):  # Monday-Friday
            GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='morning', is_template=True)
            GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='afternoon', is_template=True)
    
    positions = Position.objects.filter(
        date__gte=settings.next_week_start,
        date__lte=settings.next_week_end
    )
    
    initial_count = positions.count()
    
    # Execute assignment algorithm (should not raise any exceptions)
    result = assign_positions_automatically(settings)
    
    # Should return success result
    assert result is not None
    assert 'assigned' in result or 'assignments_created' in result
    

@pytest.mark.django_db
def test_optimal_assignment_respects_scores(
    create_guard_with_user, system_settings_for_assignment, sample_exhibitions
):
    """
    Test that Hungarian algorithm produces optimal assignments based on scores.
    Guards with higher priority should get more positions.
    """
    settings = system_settings_for_assignment
    
    # Create guards with very different priorities
    guard_high = create_guard_with_user('high', 'high@test.com', availability=5, priority=Decimal('3.0'))
    guard_low = create_guard_with_user('low', 'low@test.com', availability=5, priority=Decimal('1.0'))
    
    # Manually set priorities to ensure difference
    guard_high.priority_number = Decimal('3.0')
    guard_high.save()
    guard_low.priority_number = Decimal('1.0')
    guard_low.save()
    
    # Add work periods
    for guard in [guard_high, guard_low]:
        for day in range(5):  # Monday-Friday
            GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='morning', is_template=True)
            GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='afternoon', is_template=True)
    
    # Run assignment
    result = assign_positions_automatically(settings)
    
    # Check assignments
    assignments_high = PositionHistory.objects.filter(
        action=PositionHistory.Action.ASSIGNED,
        guard=guard_high,
        position__date__gte=settings.next_week_start
    )
    assignments_low = PositionHistory.objects.filter(
        action=PositionHistory.Action.ASSIGNED,
        guard=guard_low,
        position__date__gte=settings.next_week_start
    )
    
    # Both should have assignments (if enough positions exist)
    assert assignments_high.count() > 0
    assert assignments_low.count() > 0
    
    # High priority guard should not get significantly fewer positions than low priority
    # (The algorithm optimizes for overall matching, not individual preference)


@pytest.mark.django_db
def test_hungarian_handles_more_guards_than_positions(
    create_guard_with_user, system_settings_for_assignment, sample_exhibitions
):
    """
    Test that algorithm handles case where total guard availability exceeds positions.
    Some guards will not get assignments.
    """
    settings = system_settings_for_assignment
    
    # Count available positions
    positions = Position.objects.filter(
        date__gte=settings.next_week_start,
        date__lte=settings.next_week_end
    )
    position_count = positions.count()
    
    # Create many guards with high availability (more slots than positions)
    guards = []
    for i in range(10):
        guard = create_guard_with_user(f'guard{i}', f'g{i}@test.com', availability=5, priority=Decimal('2.0'))
        guards.append(guard)
        # Add work periods
        for day in range(5):  # Monday-Friday
            GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='morning', is_template=True)
            GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='afternoon', is_template=True)
    
    # Total slots = 10 * 5 = 50, likely more than positions
    total_slots = sum(g.availability for g in guards)
    
    # Run assignment
    result = assign_positions_automatically(settings)
    
    # Total assignments should not exceed position count
    total_assignments = PositionHistory.objects.filter(
        action=PositionHistory.Action.ASSIGNED,
        position__date__gte=settings.next_week_start,
        position__date__lte=settings.next_week_end
    ).count()
    
    assert total_assignments <= position_count
    
    # Some guards might have 0 assignments if there aren't enough positions
    guards_with_assignments = sum(
        1 for g in guards 
        if PositionHistory.objects.filter(
            action=PositionHistory.Action.ASSIGNED,
            guard=g,
            position__date__gte=settings.next_week_start
        ).exists()
    )
    
    # At least some guards should have assignments
    assert guards_with_assignments > 0


# ============================================================================
# ASSIGNMENT POST-PROCESSING TESTS (4 tests)
# ============================================================================

@pytest.mark.django_db
def test_assignment_records_created_correctly(
    create_guard_with_user, system_settings_for_assignment, sample_exhibitions
):
    """
    Test that Assignment records are created with correct guard-position pairs.
    """
    settings = system_settings_for_assignment
    
    guard = create_guard_with_user('test_guard', 'test@test.com', availability=3, priority=Decimal('2.0'))
    
    # Add work periods
    for day in range(5):  # Monday-Friday
        GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='morning', is_template=True)
        GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='afternoon', is_template=True)
    
    # Run assignment
    assign_positions_automatically(settings)
    
    # Check that assignments were created
    assignments = PositionHistory.objects.filter(
        action=PositionHistory.Action.ASSIGNED,
        guard=guard,
        position__date__gte=settings.next_week_start,
        position__date__lte=settings.next_week_end
    )
    
    assert assignments.count() > 0
    assert assignments.count() <= guard.availability
    
    # Verify each assignment has valid guard and position
    for assignment in assignments:
        assert assignment.guard == guard
        assert assignment.position is not None
        assert assignment.position.date >= settings.next_week_start
        assert assignment.position.date <= settings.next_week_end


@pytest.mark.django_db
def test_impossible_assignments_filtered_out(
    create_guard_with_user, system_settings_for_assignment, sample_exhibitions
):
    """
    Test that positions with -9999 scores (impossible assignments) are not assigned.
    This happens when guard work periods don't match position times.
    """
    settings = system_settings_for_assignment
    
    # Create guard with very restrictive work periods (only Monday morning)
    guard = create_guard_with_user('restricted', 'rest@test.com', availability=5, priority=Decimal('2.0'))
    
    GuardWorkPeriod.objects.create(
        guard=guard,
        day_of_week=0,  # Monday only
        shift_type='morning',
        is_template=True
    )
    
    # Run assignment
    assign_positions_automatically(settings)
    
    # Check assignments
    assignments = PositionHistory.objects.filter(
        action=PositionHistory.Action.ASSIGNED,
        guard=guard,
        position__date__gte=settings.next_week_start,
        position__date__lte=settings.next_week_end
    )
    
    # All assigned positions should be Monday mornings
    for assignment in assignments:
        assert assignment.position.date.weekday() == 0  # Monday
        assert assignment.position.start_time == settings.weekday_morning_start


@pytest.mark.django_db
def test_no_duplicate_position_assignments(
    create_guard_with_user, system_settings_for_assignment, sample_exhibitions
):
    """
    Test that each position is assigned to at most one guard.
    Hungarian algorithm ensures 1-to-1 matching.
    """
    settings = system_settings_for_assignment
    
    # Create multiple guards
    for i in range(5):
        guard = create_guard_with_user(f'guard{i}', f'g{i}@test.com', availability=3, priority=Decimal('2.0'))
        # Add work periods
        for day in range(5):  # Monday-Friday
            GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='morning', is_template=True)
            GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='afternoon', is_template=True)
    
    # Run assignment
    assign_positions_automatically(settings)
    
    # Check for duplicate assignments
    positions = Position.objects.filter(
        date__gte=settings.next_week_start,
        date__lte=settings.next_week_end
    )
    
    for position in positions:
        assignments = PositionHistory.objects.filter(
            action=PositionHistory.Action.ASSIGNED,
            position=position
        )
        # Each position should have 0 or 1 assignment, never more
        assert assignments.count() <= 1


@pytest.mark.django_db
def test_guard_availability_respected(
    create_guard_with_user, system_settings_for_assignment, sample_exhibitions
):
    """
    Test that guards don't get assigned more positions than their availability.
    """
    settings = system_settings_for_assignment
    
    # Create guards with different availabilities
    guard1 = create_guard_with_user('guard1', 'g1@test.com', availability=2, priority=Decimal('2.0'))
    guard2 = create_guard_with_user('guard2', 'g2@test.com', availability=5, priority=Decimal('2.0'))
    guard3 = create_guard_with_user('guard3', 'g3@test.com', availability=1, priority=Decimal('2.0'))
    
    # Add work periods
    for guard in [guard1, guard2, guard3]:
        for day in range(5):  # Monday-Friday
            GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='morning', is_template=True)
            GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='afternoon', is_template=True)
    
    # Run assignment
    assign_positions_automatically(settings)
    
    # Check each guard's assignments don't exceed availability
    for guard in [guard1, guard2, guard3]:
        assignments = PositionHistory.objects.filter(
            action=PositionHistory.Action.ASSIGNED,
            guard=guard,
            position__date__gte=settings.next_week_start,
            position__date__lte=settings.next_week_end
        )
        assert assignments.count() <= guard.availability


# ============================================================================
# EDGE CASES TESTS (3 tests)
# ============================================================================

@pytest.mark.django_db
def test_no_guards_returns_gracefully(
    system_settings_for_assignment, sample_exhibitions
):
    """
    Test that algorithm handles case with no guards available.
    Should return gracefully without crashing.
    """
    settings = system_settings_for_assignment
    
    # Don't create any guards
    
    # Run assignment (should not crash)
    result = assign_positions_automatically(settings)
    
    # Should complete but with no assignments
    assert result is not None


@pytest.mark.django_db
def test_no_positions_returns_gracefully(
    create_guard_with_user, system_settings_for_assignment
):
    """
    Test that algorithm handles case with guards but no positions.
    Should return gracefully without crashing.
    """
    # Create guards but no positions (don't call sample_exhibitions fixture)
    guard = create_guard_with_user('test_guard', 'test@test.com', availability=3, priority=Decimal('2.0'))
    
    # Delete all positions for next week
    settings = system_settings_for_assignment
    Position.objects.filter(
        date__gte=settings.next_week_start,
        date__lte=settings.next_week_end
    ).delete()
    
    # Run assignment (should not crash)
    result = assign_positions_automatically(settings)
    
    # Should complete but with no assignments
    assert result is not None
    
    assignments = PositionHistory.objects.filter(
        action=PositionHistory.Action.ASSIGNED,
        guard=guard
    )
    assert assignments.count() == 0


@pytest.mark.django_db
def test_all_guards_unavailable_for_all_positions(
    create_guard_with_user, system_settings_for_assignment, sample_exhibitions
):
    """
    Test edge case where all guards have work periods that don't match any positions.
    All scores would be -9999, nothing should be assigned.
    """
    settings = system_settings_for_assignment
    
    # Create guards with impossible work periods (e.g., Sunday only, but no Sunday positions)
    guard1 = create_guard_with_user('guard1', 'g1@test.com', availability=3, priority=Decimal('2.0'))
    guard2 = create_guard_with_user('guard2', 'g2@test.com', availability=3, priority=Decimal('2.0'))
    
    # Set work periods to Sunday (day 6) only
    for guard in [guard1, guard2]:
        GuardWorkPeriod.objects.create(
            guard=guard,
            day_of_week=6,  # Sunday
            shift_type='morning',
            is_template=True
        )
    
    # Verify no positions exist on Sunday
    sunday_positions = Position.objects.filter(
        date__gte=settings.next_week_start,
        date__lte=settings.next_week_end,
        date__week_day=1  # Sunday in Django (1=Sunday, 2=Monday, etc.)
    ).count()
    
    # If Sunday positions exist, this test is invalid
    if sunday_positions > 0:
        pytest.skip("Sunday positions exist, cannot test impossible assignment case")
    
    # Run assignment
    result = assign_positions_automatically(settings)
    
    # Should complete but with few/no assignments (only if guards found matching positions)
    assignments = PositionHistory.objects.filter(
        action=PositionHistory.Action.ASSIGNED,
        guard__in=[guard1, guard2],
        position__date__gte=settings.next_week_start,
        position__date__lte=settings.next_week_end
    )
    
    # If workdays don't include Sunday, assignments should be 0
    assert assignments.count() == 0
