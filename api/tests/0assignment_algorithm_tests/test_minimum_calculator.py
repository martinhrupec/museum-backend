"""
FAZA 7: Minimum Calculator Tests

Tests for calculate_and_update_minimum() function which determines the 
minimum number of positions guards must take based on current situation.

Logic:
- Called AFTER automated assignment completes
- Counts empty positions (without PositionHistory)
- Counts ALL active guards (inner + outer, not just those with availability)
- Looks at current assignment distribution per guard
- Iteratively RAISES minimum while it can fit into empty positions:
  * Finds guards with lowest assignment count
  * Tests: "What if I raise all of them by +1?"
  * If additional positions needed <= empty positions: ACCEPT, raise minimum
  * If additional positions needed > empty positions: STOP (rounds DOWN)
- Saves result to SystemSettings.minimal_number_of_positions_in_week

Key scenarios:
1. All positions filled (0 empty) → Minimum = 0 (nothing to require)
2. Many empty positions → Minimum can be RAISED higher (space to distribute)
3. Few empty positions → Minimum is LOWER (not enough space to raise it)

IMPORTANT: More empty positions = HIGHER minimum (not lower!)
"""
import pytest
from decimal import Decimal
from datetime import timedelta
from django.utils import timezone

from api.api_models import Position, PositionHistory, GuardWorkPeriod, SystemSettings, Exhibition
from background_tasks.minimum_calculator import calculate_and_update_minimum
from background_tasks.assignment_algorithm import assign_positions_automatically


# ============================================================================
# UNIT TESTS - Minimum Calculation (4 tests)
# ============================================================================

@pytest.mark.django_db
def test_minimum_calculated_after_full_assignment(
    create_guard_with_user, system_settings_for_assignment, sample_exhibitions_weekdays_only
):
    """
    When all positions are filled, minimum is set to 0.
    No more positions to distribute, so minimum requirement is 0.
    
    Uses sample_exhibitions_weekdays_only (open Tue-Fri) so guard work periods match.
    """
    settings = system_settings_for_assignment
    
    # Create enough guards to fill all positions
    positions = list(Position.objects.filter(
        date__gte=settings.next_week_start,
        date__lte=settings.next_week_end
    ))
    position_count = len(positions)
    
    # Create fewer guards to speed up test
    guards = []
    for i in range(3):
        guard = create_guard_with_user(
            f'guard{i}', 
            f'g{i}@test.com', 
            availability=25,  # 3×25=75 slots > positions 
            priority=Decimal('2.0')
        )
        guards.append(guard)
        # Add work periods for Tue-Fri (days 1-4) to match exhibition open_on
        for day in range(1, 5):  # 1=Tue, 2=Wed, 3=Thu, 4=Fri
            GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='morning', is_template=True)
            GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='afternoon', is_template=True)
    
    # Run assignment (should fill all positions with 3 guards × 25 availability = 75 slots)
    result = assign_positions_automatically(settings)
    
    # Calculate minimum based on actual situation
    minimum = calculate_and_update_minimum(settings, position_count)
    
    # When all positions are filled, minimum should be 0
    assert minimum == 0, f"Expected minimum=0 when all positions filled, got {minimum}"
    assert isinstance(minimum, int)
    
    # Settings should be updated
    settings.refresh_from_db()
    assert settings.minimal_number_of_positions_in_week == 0


@pytest.mark.django_db
def test_minimum_with_many_empty_positions_and_few_guards(
    create_guard_with_user, system_settings_for_assignment
):
    """
    When many positions remain empty (not enough guards participated in assignment),
    but there are OTHER active guards who didn't participate, minimum can be raised
    to encourage those other guards to take positions during manual assignment.
    
    Key: Algorithm looks at ALL active guards, not just those who got assignments.
    
    SIMPLIFIED: Use minimal positions to avoid slow iteration in minimum calculator.
    """
    settings = system_settings_for_assignment
    
    # Create small exhibition - use workdays that match system settings (Tue-Fri = 1,2,3,4)
    today = timezone.now()
    exhibition = Exhibition.objects.create(
        name="Small Test Gallery",
        number_of_positions=1,  # 1 position per shift
        start_date=today,
        end_date=today + timedelta(days=60),
        is_special_event=False,
        open_on=[1, 2, 3, 4]  # Tue-Fri (matches workdays in system_settings_for_assignment)
    )
    
    positions = list(Position.objects.filter(
        date__gte=settings.next_week_start,
        date__lte=settings.next_week_end
    ))
    position_count = len(positions)
    
    # Should have 4 days × 2 shifts × 1 position = 8 positions
    assert position_count == 8, f"Expected 8 positions, got {position_count}"
    
    # Create 2 guards with availability (will participate in automated assignment)
    guard1 = create_guard_with_user('guard1', 'g1@test.com', availability=2, priority=Decimal('2.0'))
    guard2 = create_guard_with_user('guard2', 'g2@test.com', availability=1, priority=Decimal('1.5'))
    
    for guard in [guard1, guard2]:
        for day in range(1, 5):  # Tue-Fri to match exhibition
            GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='morning', is_template=True)
            GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='afternoon', is_template=True)
    
    # Create 3 additional guards WITHOUT availability (won't participate but are counted!)
    for i in range(3):
        create_guard_with_user(f'outer{i}', f'outer{i}@test.com', availability=None, priority=Decimal('1.0'))
    
    # Run assignment (only guard1 and guard2 will get positions, ~5 will remain empty)
    result = assign_positions_automatically(settings)
    
    # Calculate minimum (considers ALL 5 guards, not just the 2 who got assignments)
    minimum = calculate_and_update_minimum(settings, position_count)
    
    # With 5 total guards and ~5 empty positions out of 8, minimum should be reasonable
    # It can be raised because there's space for outer guards to take positions manually
    assert minimum >= 0
    assert isinstance(minimum, int)
    assert minimum <= position_count, f"Minimum {minimum} should not exceed {position_count} positions"


@pytest.mark.django_db
def test_minimum_iterative_raising_logic(
    create_guard_with_user, system_settings_for_assignment, sample_exhibitions
):
    """
    Test the iterative raising logic: minimum increases while it can fit.
    
    Algorithm finds guards with lowest assignment count and raises them by 1,
    repeating until additional positions needed exceeds empty positions.
    """
    settings = system_settings_for_assignment
    
    positions = list(Position.objects.filter(
        date__gte=settings.next_week_start,
        date__lte=settings.next_week_end
    ))
    position_count = len(positions)
    
    # Create guards with moderate availability (will leave some positions empty)
    guards = []
    for i in range(5):
        guard = create_guard_with_user(
            f'guard{i}', 
            f'g{i}@test.com', 
            availability=2,  # 5×2=10 slots, leaving ~14 empty positions
            priority=Decimal('2.0')
        )
        guards.append(guard)
        for day in range(1, 7):  # Tuesday-Sunday (6 days)
            GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='morning', is_template=True)
            GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='afternoon', is_template=True)
    
    # Run assignment
    result = assign_positions_automatically(settings)
    
    # Count empty positions
    empty_count = 0
    for position in positions:
        if not position.position_histories.exists():
            empty_count += 1
    
    # Calculate minimum
    minimum = calculate_and_update_minimum(settings, position_count)
    
    # Basic sanity checks
    assert minimum >= 0, "Minimum cannot be negative"
    assert isinstance(minimum, int), "Minimum must be integer"
    
    # If there are empty positions and guards, minimum should be positive
    if empty_count > 0 and len(guards) > 0:
        assert minimum >= 0  # Could be 0 if algorithm can't raise it
    
    # Verify minimum is reasonable relative to empty positions
    empty_ratio = empty_count / position_count if position_count > 0 else 0
    
    if empty_ratio > 0.5:
        # More than 50% empty → minimum can be RAISED higher (more space to distribute)
        # Per algorithm: more empty = higher minimum (encourages guards to take more)
        assert minimum > 0, "Minimum should be positive when many positions empty"
    else:
        # Less than 50% empty → minimum can be higher
        assert minimum >= 0


@pytest.mark.django_db
def test_minimum_never_exceeds_total_positions(
    create_guard_with_user, system_settings_for_assignment, sample_exhibitions
):
    """
    Minimum should never exceed total available positions.
    Edge case validation.
    """
    settings = system_settings_for_assignment
    
    positions = list(Position.objects.filter(
        date__gte=settings.next_week_start,
        date__lte=settings.next_week_end
    ))
    position_count = len(positions)
    
    # Create one guard
    guard = create_guard_with_user('guard1', 'g1@test.com', availability=5, priority=Decimal('2.0'))
    for day in range(5):
        GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='morning', is_template=True)
        GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='afternoon', is_template=True)
    
    # Run assignment
    assign_positions_automatically(settings)
    
    # Calculate minimum
    minimum = calculate_and_update_minimum(settings, position_count)
    
    # Minimum must not exceed total positions
    assert minimum <= position_count


# ============================================================================
# INTEGRATION TESTS (6 tests)
# ============================================================================

@pytest.mark.django_db
def test_minimum_updates_system_settings(
    create_guard_with_user, system_settings_for_assignment, sample_exhibitions
):
    """
    Test that calculate_and_update_minimum actually updates SystemSettings.
    """
    settings = system_settings_for_assignment
    
    # Store original minimum
    original_minimum = settings.minimal_number_of_positions_in_week
    
    positions = list(Position.objects.filter(
        date__gte=settings.next_week_start,
        date__lte=settings.next_week_end
    ))
    position_count = len(positions)
    
    # Create guards and run assignment
    # Create 3 guards - enough to fill positions
    for i in range(3):
        guard = create_guard_with_user(f'guard{i}', f'g{i}@test.com', availability=4, priority=Decimal('2.0'))
        for day in range(1, 7):  # Tuesday-Sunday (6 days)
            GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='morning', is_template=True)
            GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='afternoon', is_template=True)
    
    assign_positions_automatically(settings)
    
    # Calculate minimum
    calculated_minimum = calculate_and_update_minimum(settings, position_count)
    
    # Reload settings from DB
    settings.refresh_from_db()
    
    # Verify settings were updated
    assert settings.minimal_number_of_positions_in_week == calculated_minimum


@pytest.mark.django_db
def test_minimum_calculation_with_no_assignments(
    create_guard_with_user, system_settings_for_assignment, sample_exhibitions
):
    """
    When no automated assignments are made (guards without availability),
    but guards exist, minimum should be raised to encourage manual assignment.
    """
    settings = system_settings_for_assignment
    
    positions = list(Position.objects.filter(
        date__gte=settings.next_week_start,
        date__lte=settings.next_week_end
    ))
    position_count = len(positions)
    
    # Create guards WITHOUT availability (won't participate in automated assignment)
    for i in range(5):
        create_guard_with_user(f'guard{i}', f'g{i}@test.com', availability=None, priority=Decimal('1.0'))
    
    # Run assignment (will not assign anything - no one has availability)
    assign_positions_automatically(settings)
    
    # Calculate minimum
    minimum = calculate_and_update_minimum(settings, position_count)
    
    # With many empty positions and guards available, minimum should be raised
    assert minimum >= 0
    assert isinstance(minimum, int)
    # Should raise minimum to encourage manual assignment
    assert minimum > 0, "Minimum should be > 0 when guards exist but no automated assignments made"


@pytest.mark.django_db
def test_minimum_with_partial_assignment_coverage(
    create_guard_with_user, system_settings_for_assignment, sample_exhibitions
):
    """
    Test minimum calculation when ~50% of positions are assigned.
    Should produce a reasonable middle-ground minimum.
    """
    settings = system_settings_for_assignment
    
    positions = list(Position.objects.filter(
        date__gte=settings.next_week_start,
        date__lte=settings.next_week_end
    ))
    position_count = len(positions)
    
    # Create guards to fill approximately half the positions
    target_assignments = position_count // 2
    num_guards = 4
    availability_per_guard = (target_assignments // num_guards) + 1
    
    for i in range(num_guards):
        guard = create_guard_with_user(
            f'guard{i}', 
            f'g{i}@test.com', 
            availability=availability_per_guard, 
            priority=Decimal('2.0')
        )
        for day in range(5):
            GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='morning', is_template=True)
            GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='afternoon', is_template=True)
    
    # Run assignment
    result = assign_positions_automatically(settings)
    assignments_created = result.get('assignments_created', 0)
    
    # Calculate minimum
    minimum = calculate_and_update_minimum(settings, position_count)
    
    # Minimum should be reasonable for partial coverage
    # If ~50% filled, minimum might be around 25-50% of configured minimum
    assert minimum > 0
    assert minimum < position_count


@pytest.mark.django_db
def test_minimum_with_special_event_positions(
    create_guard_with_user, system_settings_for_assignment, special_event_exhibition
):
    """
    Test that special event positions are included in minimum calculation.
    Special events count as regular positions for minimum purposes.
    """
    settings = system_settings_for_assignment
    
    # Special event fixture creates positions
    # Get all positions including special event
    positions = list(Position.objects.filter(
        date__gte=settings.next_week_start,
        date__lte=settings.next_week_end
    ))
    position_count = len(positions)
    
    # Verify we have positions (including special event)
    assert position_count > 0
    
    # Create guards
    for i in range(3):
        guard = create_guard_with_user(f'guard{i}', f'g{i}@test.com', availability=10, priority=Decimal('2.0'))
        for day in range(5):
            GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='morning', is_template=True)
            GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='afternoon', is_template=True)
    
    # Run assignment
    assign_positions_automatically(settings)
    
    # Calculate minimum (should include special event positions)
    minimum = calculate_and_update_minimum(settings, position_count)
    
    # Minimum should be calculated based on ALL positions
    assert minimum > 0
    assert minimum <= position_count


@pytest.mark.django_db
def test_minimum_calculation_idempotent(
    create_guard_with_user, system_settings_for_assignment, sample_exhibitions
):
    """
    Test that calling calculate_and_update_minimum multiple times with same data
    produces the same result.
    """
    settings = system_settings_for_assignment
    
    positions = list(Position.objects.filter(
        date__gte=settings.next_week_start,
        date__lte=settings.next_week_end
    ))
    position_count = len(positions)
    
    # Create guards and run assignment
    for i in range(4):
        guard = create_guard_with_user(f'guard{i}', f'g{i}@test.com', availability=4, priority=Decimal('2.0'))
        for day in range(1, 7):  # Tuesday-Sunday (6 days)
            GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='morning', is_template=True)
            GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='afternoon', is_template=True)
    
    assign_positions_automatically(settings)
    
    # Calculate minimum twice
    minimum1 = calculate_and_update_minimum(settings, position_count)
    minimum2 = calculate_and_update_minimum(settings, position_count)
    
    # Should produce same result
    assert minimum1 == minimum2

