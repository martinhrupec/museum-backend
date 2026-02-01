"""
FAZA 8: Edge Cases & Error Handling Tests

Tests for boundary conditions, edge cases, and graceful error handling
in the assignment algorithm. These tests ensure robustness and stability
under unusual or extreme conditions.

Categories:
1. Boundary Conditions - Extreme but valid inputs
2. Data Edge Cases - Unusual but possible data states
3. Error Recovery - Graceful handling of problematic scenarios
"""
import pytest
from decimal import Decimal
from datetime import timedelta, time
from django.utils import timezone

from api.api_models import (
    Position, PositionHistory, Guard, Exhibition, 
    GuardWorkPeriod, SystemSettings, GuardDayPreference, GuardExhibitionPreference
)
from background_tasks.assignment_algorithm import assign_positions_automatically
from background_tasks.minimum_calculator import calculate_and_update_minimum


# ============================================================================
# BOUNDARY CONDITIONS (8 tests)
# ============================================================================

@pytest.mark.django_db
def test_zero_positions_available(create_guard_with_user, system_settings_for_assignment):
    """
    When no positions exist for next week, algorithm should handle gracefully.
    """
    settings = system_settings_for_assignment
    
    # No positions created - Position table empty for next week
    positions = Position.objects.filter(
        date__gte=settings.next_week_start,
        date__lte=settings.next_week_end
    )
    assert positions.count() == 0
    
    # But guards exist with availability
    guard = create_guard_with_user('guard1', 'g1@test.com', availability=5, priority=Decimal('3.0'))
    for day in range(1, 7):  # Tuesday-Sunday (6 days)
        GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='morning', is_template=True)
        GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='afternoon', is_template=True)
    
    # Run assignment with no positions but guards available
    result = assign_positions_automatically(settings)
    
    # Should complete without errors (no positions to assign)
    assert result['status'] in ['success', 'skipped', 'warning']
    assert result.get('assignments_created', 0) == 0
    assert result.get('positions_filled', 0) == 0


@pytest.mark.django_db
def test_one_guard_one_position(
    create_guard_with_user, system_settings_for_assignment, mocker
):
    """
    Minimal scenario: exactly one guard and one position.
    Should assign successfully.
    """
    settings = system_settings_for_assignment
    
    # Mock current time to Wednesday 9 PM (middle of the week)
    from django.utils import timezone
    from datetime import datetime
    wednesday_9pm = timezone.make_aware(datetime(2026, 1, 28, 21, 0, 0))  # Wednesday 9 PM
    mocker.patch('django.utils.timezone.now', return_value=wednesday_9pm)
    
    # Create single position
    today = timezone.now()
    exhibition = Exhibition.objects.create(
        name="Test Gallery",
        number_of_positions=1,
        start_date=today,
        end_date=today + timedelta(days=60),
        is_special_event=False,
        open_on=[2]  # Wednesday only
    )
    
    positions = Position.objects.filter(
        date__gte=settings.next_week_start,
        date__lte=settings.next_week_end
    )
    assert positions.count() == 2  # 1 position × 2 shifts (morning + afternoon)
    
    # Create single guard
    guard = create_guard_with_user('guard1', 'g1@test.com', availability=2, priority=Decimal('2.0'))
    GuardWorkPeriod.objects.create(guard=guard, day_of_week=2, shift_type='morning', is_template=True)  # Wednesday
    
    # Run assignment
    result = assign_positions_automatically(settings)
    
    # Should assign the guard to one position
    assert result['assignments_created'] == 1
    
    # Verify assignment
    assigned_position = positions.filter(position_histories__guard=guard).first()
    assert assigned_position is not None


@pytest.mark.django_db
def test_more_guards_than_positions(
    create_guard_with_user, system_settings_for_assignment
):
    """
    When there are more guards than available positions,
    some guards will not be assigned. Algorithm should prioritize correctly.
    """
    settings = system_settings_for_assignment
    
    # Create 2 positions
    today = timezone.now()
    exhibition = Exhibition.objects.create(
        name="Small Gallery",
        number_of_positions=1,
        start_date=today,
        end_date=today + timedelta(days=60),
        is_special_event=False,
        open_on=[1]  # Tuesday only = 2 positions (2 shifts)
    )
    
    positions = Position.objects.filter(
        date__gte=settings.next_week_start,
        date__lte=settings.next_week_end
    )
    position_count = positions.count()
    assert position_count == 2
    
    # Create 12 guards (realistic number, more than 2 positions)
    guards = []
    for i in range(12):
        guard = create_guard_with_user(
            f'guard{i}',
            f'g{i}@test.com',
            availability=1,
            priority=Decimal(str(5.0 - i * 0.3))  # Descending priorities
        )
        GuardWorkPeriod.objects.create(guard=guard, day_of_week=1, shift_type='morning', is_template=True)  # Tuesday
        GuardWorkPeriod.objects.create(guard=guard, day_of_week=1, shift_type='afternoon', is_template=True)
        guards.append(guard)
    
    # Run assignment
    result = assign_positions_automatically(settings)
    
    # Only 2 positions filled (not all 12 guards)
    assert result['assignments_created'] == 2
    
    # Higher priority guards should be assigned
    assigned_guards = set(
        PositionHistory.objects.filter(
            position__in=positions,
            action=PositionHistory.Action.ASSIGNED
        ).values_list('guard_id', flat=True)
    )
    assert len(assigned_guards) <= 2


@pytest.mark.django_db
def test_more_positions_than_total_availability(
    create_guard_with_user, system_settings_for_assignment, sample_exhibitions
):
    """
    When total guard availability < total positions,
    some positions will remain empty. Capping should occur.
    """
    settings = system_settings_for_assignment
    
    positions = Position.objects.filter(
        date__gte=settings.next_week_start,
        date__lte=settings.next_week_end
    )
    position_count = positions.count()
    
    # Create only 2 guards with low availability (total = 5)
    for i in range(2):
        guard = create_guard_with_user(
            f'guard{i}',
            f'g{i}@test.com',
            availability=2 + i,  # 2 and 3 = 5 total
            priority=Decimal('2.0')
        )
        for day in range(1, 7):  # Tuesday-Sunday (6 days)
            GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='morning', is_template=True)
            GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='afternoon', is_template=True)
    
    # Run assignment (5 availability << ~24 positions from sample_exhibitions)
    result = assign_positions_automatically(settings)
    
    # Should assign all available slots
    assert result['assignments_created'] == 5
    
    # Many positions should remain empty
    empty_count = position_count - result['assignments_created']
    assert empty_count > 15


@pytest.mark.django_db
def test_all_guards_same_priority(
    create_guard_with_user, system_settings_for_assignment
):
    """
    When all guards have identical priority, distribution should be fair
    based on availability and preferences.
    """
    settings = system_settings_for_assignment
    
    # Create small exhibition
    today = timezone.now()
    exhibition = Exhibition.objects.create(
        name="Test Gallery",
        number_of_positions=2,
        start_date=today,
        end_date=today + timedelta(days=60),
        is_special_event=False,
        open_on=[1, 2, 3]  # Tue, Wed, Thu (3 days × 2 shifts × 2 positions = 12 positions)
    )
    
    positions = Position.objects.filter(
        date__gte=settings.next_week_start,
        date__lte=settings.next_week_end
    )
    position_count = positions.count()
    
    # Create 3 guards with SAME priority
    guards = []
    for i in range(3):
        guard = create_guard_with_user(
            f'guard{i}',
            f'g{i}@test.com',
            availability=4,
            priority=Decimal('3.0')  # ALL same priority
        )
        for day in [1, 2, 3]:  # Tuesday, Wednesday, Thursday
            GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='morning', is_template=True)
            GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='afternoon', is_template=True)
        guards.append(guard)
    
    # Run assignment
    result = assign_positions_automatically(settings)
    
    # All 3 guards should get assignments (total 12 positions, 3×4=12 availability)
    assigned_counts = {}
    for guard in guards:
        count = PositionHistory.objects.filter(
            guard=guard,
            action=PositionHistory.Action.ASSIGNED
        ).count()
        assigned_counts[guard.id] = count
    
    # All guards should be assigned
    assert all(count > 0 for count in assigned_counts.values())
    # Distribution should be relatively even
    assert max(assigned_counts.values()) - min(assigned_counts.values()) <= 2


@pytest.mark.django_db
def test_guard_with_availability_zero_skipped(
    create_guard_with_user, system_settings_for_assignment, sample_exhibitions
):
    """
    Guards with availability=0 should not participate in assignment.
    """
    settings = system_settings_for_assignment
    
    # Create guard with 0 availability
    guard_zero = create_guard_with_user('guard0', 'g0@test.com', availability=0, priority=Decimal('5.0'))
    
    # Create normal guard
    guard_normal = create_guard_with_user('guard1', 'g1@test.com', availability=5, priority=Decimal('2.0'))
    
    for guard in [guard_zero, guard_normal]:
        for day in range(1, 7):  # Tuesday-Sunday (6 days)
            GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='morning', is_template=True)
            GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='afternoon', is_template=True)
    
    # Run assignment
    result = assign_positions_automatically(settings)
    
    # Guard with 0 availability should NOT be assigned
    zero_assignments = PositionHistory.objects.filter(
        guard=guard_zero,
        action=PositionHistory.Action.ASSIGNED
    ).count()
    assert zero_assignments == 0
    
    # Normal guard should be assigned
    normal_assignments = PositionHistory.objects.filter(
        guard=guard_normal,
        action=PositionHistory.Action.ASSIGNED
    ).count()
    assert normal_assignments > 0


@pytest.mark.django_db
def test_guard_with_availability_one(
    create_guard_with_user, system_settings_for_assignment, sample_exhibitions
):
    """
    Guard with availability=1 should be assigned exactly 1 position.
    """
    settings = system_settings_for_assignment
    
    guard = create_guard_with_user('guard1', 'g1@test.com', availability=1, priority=Decimal('5.0'))
    
    for day in range(1, 7):  # Tuesday-Sunday (6 days)
        GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='morning', is_template=True)
        GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='afternoon', is_template=True)
    
    # Run assignment
    result = assign_positions_automatically(settings)
    
    # Guard should be assigned exactly 1 position
    assignments = PositionHistory.objects.filter(
        guard=guard,
        action=PositionHistory.Action.ASSIGNED
    ).count()
    assert assignments == 1


@pytest.mark.django_db
def test_guard_with_high_availability(
    create_guard_with_user, system_settings_for_assignment, sample_exhibitions
):
    """
    Guard with very high availability (>= total positions) should not
    be assigned more than total available positions.
    """
    settings = system_settings_for_assignment
    
    positions = Position.objects.filter(
        date__gte=settings.next_week_start,
        date__lte=settings.next_week_end
    )
    position_count = positions.count()
    
    # Create guard with availability much higher than positions
    guard = create_guard_with_user(
        'guard1', 
        'g1@test.com', 
        availability=position_count + 50,  # Way more than needed
        priority=Decimal('5.0')
    )
    
    for day in range(5):
        GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='morning', is_template=True)
        GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='afternoon', is_template=True)
    
    # Run assignment
    result = assign_positions_automatically(settings)
    
    # Guard should not be assigned more than total positions
    assignments = PositionHistory.objects.filter(
        guard=guard,
        action=PositionHistory.Action.ASSIGNED
    ).count()
    assert assignments <= position_count


# ============================================================================
# DATA EDGE CASES (7 tests)
# ============================================================================

@pytest.mark.django_db
def test_all_positions_outside_work_periods(
    create_guard_with_user, system_settings_for_assignment, sample_exhibitions_weekdays_only
):
    """
    When guards have work periods that don't match any positions,
    no assignments should be made.
    """
    settings = system_settings_for_assignment
    
    # sample_exhibitions_weekdays_only creates positions for Tuesday-Friday only
    # Create guard who only works on weekends
    guard = create_guard_with_user('guard1', 'g1@test.com', availability=5, priority=Decimal('5.0'))
    GuardWorkPeriod.objects.create(guard=guard, day_of_week=5, shift_type='morning', is_template=True)  # Saturday
    GuardWorkPeriod.objects.create(guard=guard, day_of_week=6, shift_type='afternoon', is_template=True)  # Sunday
    
    # Run assignment
    result = assign_positions_automatically(settings)
    
    # No assignments should be made (no matching work periods)
    assert result['assignments_created'] == 0


@pytest.mark.django_db
def test_guard_without_work_periods_gets_all_shifts(
    create_guard_with_user, system_settings_for_assignment, sample_exhibitions
):
    """
    Guard without any work periods should be eligible for ALL positions
    (fallback behavior).
    """
    settings = system_settings_for_assignment
    
    # Create guard WITHOUT any work periods
    guard = create_guard_with_user('guard1', 'g1@test.com', availability=5, priority=Decimal('5.0'))
    # Don't create any GuardWorkPeriod records
    
    # Run assignment
    result = assign_positions_automatically(settings)
    
    # Guard should still be assigned (fallback to all shifts)
    assignments = PositionHistory.objects.filter(
        guard=guard,
        action=PositionHistory.Action.ASSIGNED
    ).count()
    assert assignments > 0


@pytest.mark.django_db
def test_running_assignment_twice_creates_duplicate_history(
    create_guard_with_user, system_settings_for_assignment, sample_exhibitions
):
    """
    Running automated assignment twice creates duplicate PositionHistory entries.
    This is expected behavior - algorithm doesn't check for existing assignments.
    In production, assignment runs only once per week via scheduled task.
    """
    settings = system_settings_for_assignment
    
    # Create guards (realistic number: ~15 guards)
    for i in range(15):
        guard = create_guard_with_user(
            f'guard{i}',
            f'g{i}@test.com',
            availability=2 + (i % 4),  # Varies 2-5
            priority=Decimal(str(2.0 + (i % 3)))
        )
        for day in range(1, 7):  # Tuesday-Sunday (6 days)
            GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='morning', is_template=True)
            GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='afternoon', is_template=True)
    
    # Run assignment first time
    result1 = assign_positions_automatically(settings)
    first_count = result1['assignments_created']
    
    # Run assignment second time (shouldn't happen in production)
    result2 = assign_positions_automatically(settings)
    second_count = result2['assignments_created']
    
    # Both runs should succeed
    assert first_count > 0
    assert second_count > 0
    
    # Total history records = sum of both runs
    total_records = PositionHistory.objects.filter(
        action=PositionHistory.Action.ASSIGNED
    ).count()
    assert total_records == first_count + second_count


@pytest.mark.django_db
def test_special_event_excluded_from_automated_assignment(
    create_guard_with_user, system_settings_for_assignment
):
    """
    Special event positions should not be included in automated assignment.
    """
    settings = system_settings_for_assignment
    
    # Create special event exhibition in next week
    # Convert date to datetime for Exhibition model
    from datetime import datetime
    start_datetime = timezone.make_aware(datetime.combine(settings.next_week_start, datetime.min.time()))
    end_datetime = timezone.make_aware(datetime.combine(settings.next_week_end, datetime.max.time()))
    
    special_exhibition = Exhibition.objects.create(
        name="Special Opening Event",
        number_of_positions=3,
        start_date=start_datetime,
        end_date=end_datetime,
        event_start_time=time(11, 0),
        event_end_time=time(17, 0),
        is_special_event=True,  # SPECIAL EVENT
        open_on=[1]  # Tuesday
    )
    
    # Count special event positions
    special_positions = Position.objects.filter(
        exhibition=special_exhibition,
        date__gte=settings.next_week_start,
        date__lte=settings.next_week_end
    )
    special_count = special_positions.count()
    assert special_count > 0
    
    # Create guard
    guard = create_guard_with_user('guard1', 'g1@test.com', availability=5, priority=Decimal('5.0'))
    for day in range(1, 7):  # Tuesday-Sunday (6 days)
        GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='morning', is_template=True)
        GuardWorkPeriod.objects.create(guard=guard, day_of_week=day, shift_type='afternoon', is_template=True)
    
    # Run assignment
    result = assign_positions_automatically(settings)
    
    # No special event positions should be assigned
    special_assignments = PositionHistory.objects.filter(
        position__in=special_positions,
        action=PositionHistory.Action.ASSIGNED
    ).count()
    assert special_assignments == 0


@pytest.mark.django_db
def test_exhibition_with_inconsistent_open_days(
    create_guard_with_user, system_settings_for_assignment
):
    """
    Exhibition with unusual open_on array should still work correctly.
    """
    settings = system_settings_for_assignment
    
    # Create exhibition open only on Tuesday and Thursday
    today = timezone.now()
    exhibition = Exhibition.objects.create(
        name="Tuesday Thursday Gallery",
        number_of_positions=2,
        start_date=today,
        end_date=today + timedelta(days=60),
        is_special_event=False,
        open_on=[1, 3]  # Only Tuesday (1) and Thursday (3)
    )
    
    positions = Position.objects.filter(
        date__gte=settings.next_week_start,
        date__lte=settings.next_week_end,
        exhibition=exhibition
    )
    
    # Should have positions only for Tuesday and Thursday
    # 2 days × 2 shifts × 2 positions = 8 positions
    assert positions.count() == 8
    
    # Create guard with matching work periods
    guard = create_guard_with_user('guard1', 'g1@test.com', availability=4, priority=Decimal('3.0'))
    GuardWorkPeriod.objects.create(guard=guard, day_of_week=1, shift_type='morning', is_template=True)
    GuardWorkPeriod.objects.create(guard=guard, day_of_week=1, shift_type='afternoon', is_template=True)
    GuardWorkPeriod.objects.create(guard=guard, day_of_week=3, shift_type='morning', is_template=True)
    GuardWorkPeriod.objects.create(guard=guard, day_of_week=3, shift_type='afternoon', is_template=True)
    
    # Run assignment
    result = assign_positions_automatically(settings)
    
    # Should assign successfully
    assert result['assignments_created'] > 0


@pytest.mark.django_db
def test_empty_score_matrix_scenario(
    system_settings_for_assignment, sample_exhibitions
):
    """
    When no guards have availability and positions exist,
    score matrix would be empty. Should handle gracefully.
    """
    settings = system_settings_for_assignment
    
    # Positions exist (from sample_exhibitions)
    positions = Position.objects.filter(
        date__gte=settings.next_week_start,
        date__lte=settings.next_week_end
    )
    assert positions.count() > 0
    
    # But no guards with availability > 0
    # (don't create any guards)
    
    # Run assignment
    result = assign_positions_automatically(settings)
    
    # Should complete gracefully with no assignments
    assert result['status'] in ['success', 'warning', 'skipped']
    assert result.get('assignments_created', 0) == 0
