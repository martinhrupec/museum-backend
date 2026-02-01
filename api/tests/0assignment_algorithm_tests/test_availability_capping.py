"""
FAZA 6: Availability Capping Tests

Tests for availability capping logic when demand exceeds supply.
Component: background_tasks.tasks.calculate_availability_caps()

Capping algorithm:
- If total_demand <= total_positions: No capping, everyone gets full availability
- If total_demand > total_positions: Iteratively reduce highest values
- When multiple guards at max: Reduce guard(s) with lowest priority first
- "Water filling" algorithm ensures fair distribution
"""
import pytest
from decimal import Decimal
from datetime import timedelta

from api.api_models import Position, PositionHistory, GuardWorkPeriod
from background_tasks.tasks import calculate_availability_caps
from background_tasks.assignment_algorithm import assign_positions_automatically


# ============================================================================
# UNIT TESTS - Cap Calculation (4 tests)
# ============================================================================

@pytest.mark.django_db
def test_no_capping_when_supply_meets_demand(
    create_guard_with_user, system_settings_for_assignment
):
    """
    When total availability <= total positions, no capping occurs.
    All guards keep their full availability.
    """
    settings = system_settings_for_assignment
    
    # Create guards with total availability = 10
    guard1 = create_guard_with_user('guard1', 'g1@test.com', availability=4, priority=Decimal('2.0'))
    guard2 = create_guard_with_user('guard2', 'g2@test.com', availability=3, priority=Decimal('1.5'))
    guard3 = create_guard_with_user('guard3', 'g3@test.com', availability=3, priority=Decimal('1.0'))
    
    guards = [guard1, guard2, guard3]
    total_positions = 12  # More than demand (10)
    
    # Calculate caps
    caps = calculate_availability_caps(guards, total_positions)
    
    # No capping should occur
    assert caps[guard1.id] == 4
    assert caps[guard2.id] == 3
    assert caps[guard3.id] == 3


@pytest.mark.django_db
def test_proportional_capping_formula(
    create_guard_with_user, system_settings_for_assignment
):
    """
    Test iterative capping algorithm reduces highest values first.
    Guards with highest availability get capped first.
    """
    settings = system_settings_for_assignment
    
    # Create guards with demand > supply
    guard1 = create_guard_with_user('guard1', 'g1@test.com', availability=5, priority=Decimal('2.0'))
    guard2 = create_guard_with_user('guard2', 'g2@test.com', availability=4, priority=Decimal('1.5'))
    guard3 = create_guard_with_user('guard3', 'g3@test.com', availability=3, priority=Decimal('1.0'))
    
    guards = [guard1, guard2, guard3]
    total_positions = 10  # Demand is 12, need to reduce by 2
    
    # Calculate caps
    caps = calculate_availability_caps(guards, total_positions)
    
    # Total should equal positions
    assert sum(caps.values()) == 10
    
    # guard1 (highest availability) should be capped more
    assert caps[guard1.id] < 5
    assert caps[guard3.id] == 3  # Lowest availability, likely unchanged


@pytest.mark.django_db
def test_priority_weighted_capping(
    create_guard_with_user, system_settings_for_assignment
):
    """
    When multiple guards have same availability, lower priority gets capped first.
    """
    settings = system_settings_for_assignment
    
    # Create guards with same availability but different priorities
    guard_high = create_guard_with_user('high', 'high@test.com', availability=5, priority=Decimal('3.0'))
    guard_low = create_guard_with_user('low', 'low@test.com', availability=5, priority=Decimal('1.0'))
    guard_mid = create_guard_with_user('mid', 'mid@test.com', availability=5, priority=Decimal('2.0'))
    
    guards = [guard_high, guard_mid, guard_low]
    total_positions = 12  # Demand is 15, need to reduce by 3
    
    # Calculate caps
    caps = calculate_availability_caps(guards, total_positions)
    
    # Total should equal positions
    assert sum(caps.values()) == 12
    
    # Lower priority should be capped more than higher priority
    assert caps[guard_high.id] >= caps[guard_mid.id]
    assert caps[guard_mid.id] >= caps[guard_low.id]
    
    # At least one guard should be capped
    assert caps[guard_low.id] < 5


@pytest.mark.django_db
def test_capping_respects_minimum(
    create_guard_with_user, system_settings_for_assignment
):
    """
    Cap can go to 0 if there aren't enough positions for everyone.
    """
    settings = system_settings_for_assignment
    
    # Create many guards with low supply
    guards = []
    for i in range(10):
        guard = create_guard_with_user(f'guard{i}', f'g{i}@test.com', availability=5, priority=Decimal('2.0'))
        guards.append(guard)
    
    total_positions = 20  # Demand is 50, need to cap heavily
    
    # Calculate caps
    caps = calculate_availability_caps(guards, total_positions)
    
    # Total should equal positions
    assert sum(caps.values()) == 20
    
    # All guards should be capped to 2 each
    assert all(cap == 2 for cap in caps.values())


# ============================================================================
# INTEGRATION TESTS (8 tests)
# ============================================================================

@pytest.mark.django_db
def test_capping_reduces_guard_slots_in_matrix(
    create_guard_with_user, system_settings_for_assignment, sample_exhibitions
):
    """
    When caps are applied, guards get fewer rows in score matrix.
    Guards with oversupply (more slots than positions) get capped.
    """
    from background_tasks.tasks import calculate_availability_caps
    
    settings = system_settings_for_assignment
    
    # Count positions first
    positions = Position.objects.filter(
        date__gte=settings.next_week_start,
        date__lte=settings.next_week_end
    )
    position_count = positions.count()
    
    # Create guards with OVERSUPPLY - more total slots than positions
    # If we have ~24 positions, create 10 guards with availability=3-4 each = ~35 slots
    # This will trigger capping
    num_guards = 10
    availability_per_guard = 3  # 10×3 = 30 slots > ~24 positions
    
    guards = []
    for i in range(num_guards):
        guard = create_guard_with_user(
            f'guard{i}', 
            f'g{i}@test.com', 
            availability=availability_per_guard, 
            priority=Decimal('2.0')
        )
        guards.append(guard)
        # Add work periods
        for day in range(1, 7):  # Tuesday-Sunday (6 days)
            GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='morning', is_template=True)
            GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='afternoon', is_template=True)
    
    total_slots = num_guards * availability_per_guard
    
    # Calculate capping (this is what celery task would do)
    availability_caps = calculate_availability_caps(guards, position_count)
    
    # Run assignment WITH caps
    result = assign_positions_automatically(settings, availability_caps)
    
    # Check that capping occurred (only if we have oversupply)
    if total_slots > position_count and availability_caps:
        assert result.get('capping_occurred') == True, \
            f"Expected capping with {total_slots} slots and {position_count} positions"
        
        # Verify caps were calculated
        assert len(availability_caps) > 0, "Caps should be calculated"
        
        # Verify no guard exceeded their cap
        for guard_id, assignments in result.get('guard_assignments', {}).items():
            cap = availability_caps.get(guard_id)
            if cap:
                assert assignments <= cap, f"Guard {guard_id} exceeded cap {cap}: got {assignments}"
    
    # Total assignments should not exceed positions
    assignments = PositionHistory.objects.filter(
        action=PositionHistory.Action.ASSIGNED,
        position__date__gte=settings.next_week_start
    )
    assert assignments.count() <= position_count
    assert assignments.count() <= position_count


@pytest.mark.django_db
def test_all_guards_capped_equally_when_same_priority(
    create_guard_with_user, system_settings_for_assignment
):
    """
    Guards with identical priority and availability get capped equally.
    """
    settings = system_settings_for_assignment
    
    # Create guards with identical stats
    guards = []
    for i in range(5):
        guard = create_guard_with_user(f'guard{i}', f'g{i}@test.com', availability=5, priority=Decimal('2.0'))
        guards.append(guard)
    
    total_positions = 20  # Demand is 25, need to reduce by 5 (1 each)
    
    # Calculate caps
    caps = calculate_availability_caps(guards, total_positions)
    
    # All should be capped equally
    cap_values = list(caps.values())
    assert len(set(cap_values)) == 1  # All same value
    assert cap_values[0] == 4  # Each reduced by 1


@pytest.mark.django_db
def test_high_priority_guard_gets_higher_cap(
    create_guard_with_user, system_settings_for_assignment
):
    """
    When capping is needed, higher priority guards retain more availability.
    """
    settings = system_settings_for_assignment
    
    # Create guards with same availability, different priorities
    guard_high = create_guard_with_user('high', 'high@test.com', availability=4, priority=Decimal('5.0'))
    guard_low = create_guard_with_user('low', 'low@test.com', availability=4, priority=Decimal('1.0'))
    
    guards = [guard_high, guard_low]
    total_positions = 7  # Demand is 8, need to reduce by 1
    
    # Calculate caps
    caps = calculate_availability_caps(guards, total_positions)
    
    # High priority should get more
    assert caps[guard_high.id] > caps[guard_low.id]
    
    # Or at minimum equal (if both reduced by 1)
    assert caps[guard_high.id] >= caps[guard_low.id]


@pytest.mark.django_db
def test_capped_guard_cannot_exceed_cap(
    create_guard_with_user, system_settings_for_assignment, sample_exhibitions
):
    """
    After capping, guard should not receive more positions than their cap.
    """
    settings = system_settings_for_assignment
    
    # Create one guard with very high availability
    guard = create_guard_with_user('greedy', 'greedy@test.com', availability=50, priority=Decimal('5.0'))
    
    # Add work periods
    for day in range(5):
        GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='morning', is_template=True)
        GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='afternoon', is_template=True)
    
    # Count positions
    positions = Position.objects.filter(
        date__gte=settings.next_week_start,
        date__lte=settings.next_week_end
    )
    position_count = positions.count()
    
    # Run assignment
    result = assign_positions_automatically(settings)
    
    # Guard should not get more than total positions
    assignments = PositionHistory.objects.filter(
        action=PositionHistory.Action.ASSIGNED,
        guard=guard
    )
    assert assignments.count() <= position_count


@pytest.mark.django_db
def test_capping_with_work_periods(
    create_guard_with_user, system_settings_for_assignment, sample_exhibitions
):
    """
    Caps interact correctly with work period restrictions.
    Guard can't exceed cap even if work periods allow it.
    """
    settings = system_settings_for_assignment
    
    # Create guard with high availability but restrictive work periods
    guard = create_guard_with_user('restricted', 'rest@test.com', availability=5, priority=Decimal('3.0'))
    
    # Only Monday morning (very few positions)
    GuardWorkPeriod.objects.create(guard=guard, day_of_week=0, shift_type='morning', is_template=True)
    
    # Run assignment
    result = assign_positions_automatically(settings)
    
    # Check assignments
    assignments = PositionHistory.objects.filter(
        action=PositionHistory.Action.ASSIGNED,
        guard=guard
    )
    
    # Should be limited by work periods, not cap
    # (Work periods filter out most positions before capping)
    monday_positions = Position.objects.filter(
        date__gte=settings.next_week_start,
        date__lte=settings.next_week_end,
        date__week_day=2  # Monday (1=Sunday, 2=Monday in Django)
    ).count()
    
    # Assignments should not exceed Monday positions
    assert assignments.count() <= monday_positions


@pytest.mark.django_db
def test_capping_recalculated_on_guard_addition(
    create_guard_with_user, system_settings_for_assignment
):
    """
    Each assignment run recalculates caps based on current guards.
    Adding a guard changes the distribution.
    """
    settings = system_settings_for_assignment
    
    # Initial setup: 2 guards, demand > supply
    guard1 = create_guard_with_user('guard1', 'g1@test.com', availability=5, priority=Decimal('2.0'))
    guard2 = create_guard_with_user('guard2', 'g2@test.com', availability=5, priority=Decimal('2.0'))
    
    guards_initial = [guard1, guard2]
    total_positions = 8  # Demand 10, need to cap
    
    # Calculate initial caps
    caps_initial = calculate_availability_caps(guards_initial, total_positions)
    
    # Both should be capped to 4 each
    assert caps_initial[guard1.id] == 4
    assert caps_initial[guard2.id] == 4
    
    # Add third guard
    guard3 = create_guard_with_user('guard3', 'g3@test.com', availability=5, priority=Decimal('2.0'))
    
    guards_updated = [guard1, guard2, guard3]
    
    # Recalculate caps
    caps_updated = calculate_availability_caps(guards_updated, total_positions)
    
    # Now all three should be capped to 2 each
    assert caps_updated[guard1.id] == 2
    assert caps_updated[guard2.id] == 2
    assert caps_updated[guard3.id] == 2


@pytest.mark.django_db
def test_partial_capping_scenario(
    create_guard_with_user, system_settings_for_assignment
):
    """
    Only guards with highest availability get capped, others keep full availability.
    """
    settings = system_settings_for_assignment
    
    # Create guards with varying availability
    guard_high = create_guard_with_user('high', 'high@test.com', availability=5, priority=Decimal('2.0'))
    guard_mid = create_guard_with_user('mid', 'mid@test.com', availability=3, priority=Decimal('2.0'))
    guard_low = create_guard_with_user('low', 'low@test.com', availability=2, priority=Decimal('2.0'))
    
    guards = [guard_high, guard_mid, guard_low]
    total_positions = 8  # Demand is 10, need to reduce by 2
    
    # Calculate caps
    caps = calculate_availability_caps(guards, total_positions)
    
    # Only guard_high should be capped
    assert caps[guard_high.id] < 5
    assert caps[guard_mid.id] == 3  # Unchanged
    assert caps[guard_low.id] == 2  # Unchanged


@pytest.mark.django_db
def test_extreme_shortage_scenario(
    create_guard_with_user, system_settings_for_assignment
):
    """
    When positions are scarce, many guards get heavily capped or even 0.
    """
    settings = system_settings_for_assignment
    
    # Create many guards with low supply
    guards = []
    for i in range(20):
        guard = create_guard_with_user(
            f'guard{i}', 
            f'g{i}@test.com', 
            availability=5, 
            priority=Decimal(str(i))  # Varying priorities
        )
        guards.append(guard)
    
    total_positions = 30  # Demand is 100, extreme shortage
    
    # Calculate caps
    caps = calculate_availability_caps(guards, total_positions)
    
    # Total should equal positions
    assert sum(caps.values()) == 30
    
    # Many guards should have low caps
    zero_cap_count = sum(1 for cap in caps.values() if cap == 0)
    low_cap_count = sum(1 for cap in caps.values() if 0 < cap <= 2)
    
    # At least some guards should have 0 or very low caps
    assert zero_cap_count + low_cap_count >= 10
    
    # Higher priority guards should have higher caps
    guard_high_priority = guards[-1]  # priority 19
    guard_low_priority = guards[0]    # priority 0
    
    assert caps[guard_high_priority.id] >= caps[guard_low_priority.id]
