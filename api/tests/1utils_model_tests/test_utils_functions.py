"""
Tests for utility functions in api/utils/.

These tests cover:
- guard_matches_multicast() - notification matching logic
- calculate_max_availability_for_week() - availability calculation
- get_positions_for_guard_periods() - position matching for work periods
"""
import pytest
from datetime import datetime, date, time, timedelta
from decimal import Decimal
from django.utils import timezone
from freezegun import freeze_time

from api.utils.notification_matching import guard_matches_multicast
from api.utils.position_calculation import get_positions_for_guard_periods
from api.api_models import (
    Guard, 
    Exhibition, 
    Position, 
    SystemSettings,
    AdminNotification,
    PositionHistory,
    GuardWorkPeriod
)
from django.contrib.auth import get_user_model

User = get_user_model()


# ============================================================================
# Tests for guard_matches_multicast
# ============================================================================

@pytest.mark.django_db
class TestGuardMatchesMulticast:
    """Tests for guard_matches_multicast function."""
    
    @freeze_time("2026-02-03 10:00:00")  # Tuesday
    def test_matches_guard_assigned_on_notification_date(self, system_settings, guard_user, admin_user):
        """Test that guard assigned on notification_date matches."""
        guard = Guard.objects.get(user=guard_user)
        
        exhibition = Exhibition.objects.create(
            name='Multicast Test',
            number_of_positions=1,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            open_on=[1, 2, 3, 4]
        )
        
        # Create position on notification date
        position = Position.objects.create(
            exhibition=exhibition,
            date=date(2026, 2, 3),  # Tuesday
            start_time=time(10, 0),
            end_time=time(14, 0)
        )
        
        # Assign guard
        PositionHistory.objects.create(
            position=position,
            guard=guard,
            action=PositionHistory.Action.ASSIGNED
        )
        
        # Create notification for that date
        notification = AdminNotification.objects.create(
            cast_type=AdminNotification.CAST_MULTICAST,
            created_by=admin_user,
            title='Test',
            message='Test multicast',
            notification_date=date(2026, 2, 3)
        )
        
        result = guard_matches_multicast(guard, notification)
        
        assert result is True
    
    @freeze_time("2026-02-03 10:00:00")
    def test_not_matches_guard_on_different_date(self, system_settings, guard_user, admin_user):
        """Test that guard NOT assigned on notification_date doesn't match."""
        guard = Guard.objects.get(user=guard_user)
        
        exhibition = Exhibition.objects.create(
            name='Multicast Test 2',
            number_of_positions=1,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            open_on=[1, 2, 3, 4]
        )
        
        # Create position on DIFFERENT date than notification
        position = Position.objects.create(
            exhibition=exhibition,
            date=date(2026, 2, 4),  # Wednesday
            start_time=time(10, 0),
            end_time=time(14, 0)
        )
        
        PositionHistory.objects.create(
            position=position,
            guard=guard,
            action=PositionHistory.Action.ASSIGNED
        )
        
        # Notification for Tuesday
        notification = AdminNotification.objects.create(
            cast_type=AdminNotification.CAST_MULTICAST,
            created_by=admin_user,
            title='Test',
            message='Test',
            notification_date=date(2026, 2, 3)  # Different day
        )
        
        result = guard_matches_multicast(guard, notification)
        
        assert result is False
    
    @freeze_time("2026-02-03 10:00:00")
    def test_matches_specific_exhibition(self, system_settings, guard_user, admin_user):
        """Test that notification with exhibition filter matches only that exhibition."""
        guard = Guard.objects.get(user=guard_user)
        
        exhibition1 = Exhibition.objects.create(
            name='Target Exhibition',
            number_of_positions=1,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            open_on=[1, 2, 3, 4]
        )
        
        exhibition2 = Exhibition.objects.create(
            name='Other Exhibition',
            number_of_positions=1,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            open_on=[1, 2, 3, 4]
        )
        
        # Guard assigned to exhibition2
        position = Position.objects.create(
            exhibition=exhibition2,
            date=date(2026, 2, 3),
            start_time=time(10, 0),
            end_time=time(14, 0)
        )
        
        PositionHistory.objects.create(
            position=position,
            guard=guard,
            action=PositionHistory.Action.ASSIGNED
        )
        
        # Notification for exhibition1 only
        notification = AdminNotification.objects.create(
            cast_type=AdminNotification.CAST_MULTICAST,
            created_by=admin_user,
            title='Test',
            message='Test',
            notification_date=date(2026, 2, 3),
            exhibition=exhibition1  # Different exhibition
        )
        
        result = guard_matches_multicast(guard, notification)
        
        # Should NOT match - guard is on different exhibition
        assert result is False


# ============================================================================
# Tests for get_positions_for_guard_periods
# ============================================================================

@pytest.mark.django_db
class TestGetPositionsForGuardPeriods:
    """Tests for get_positions_for_guard_periods function."""
    
    def test_returns_positions_matching_work_periods(self, system_settings, guard_user):
        """Test that function returns positions matching guard's work periods."""
        guard = Guard.objects.get(user=guard_user)
        
        exhibition = Exhibition.objects.create(
            name='Work Period Test',
            number_of_positions=1,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            open_on=[1, 2, 3, 4]
        )
        
        # Create work period for Tuesday morning
        GuardWorkPeriod.objects.create(
            guard=guard,
            day_of_week=1,  # Tuesday
            shift_type='morning',
            is_template=True
        )
        
        # Create position matching work period
        tuesday_date = system_settings.next_week_start + timedelta(days=1)
        position = Position.objects.create(
            exhibition=exhibition,
            date=tuesday_date,
            start_time=system_settings.weekday_morning_start,
            end_time=system_settings.weekday_morning_end
        )
        
        result = get_positions_for_guard_periods(guard)
        
        assert position in result
    
    def test_returns_all_positions_if_no_work_periods(self, system_settings, guard_user):
        """Test that function returns all positions if guard has no work periods."""
        guard = Guard.objects.get(user=guard_user)
        
        # Make sure no work periods
        GuardWorkPeriod.objects.filter(guard=guard).delete()
        
        exhibition = Exhibition.objects.create(
            name='No WP Test',
            number_of_positions=1,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            open_on=[1, 2, 3, 4]
        )
        
        position = Position.objects.create(
            exhibition=exhibition,
            date=system_settings.next_week_start + timedelta(days=1),
            start_time=time(10, 0),
            end_time=time(14, 0)
        )
        
        result = get_positions_for_guard_periods(guard)
        
        # Should include position (default: all available)
        assert position in result
    
    def test_excludes_positions_not_in_work_periods(self, system_settings, guard_user):
        """Test that function excludes positions not matching work periods."""
        guard = Guard.objects.get(user=guard_user)
        
        # Clear and set only Tuesday morning
        GuardWorkPeriod.objects.filter(guard=guard).delete()
        GuardWorkPeriod.objects.create(
            guard=guard,
            day_of_week=1,  # Tuesday
            shift_type='morning',
            is_template=True
        )
        
        exhibition = Exhibition.objects.create(
            name='Exclude Test',
            number_of_positions=1,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            open_on=[1, 2, 3, 4]
        )
        
        # Create position on Wednesday (not in work periods)
        wednesday_date = system_settings.next_week_start + timedelta(days=2)
        position_wed = Position.objects.create(
            exhibition=exhibition,
            date=wednesday_date,
            start_time=system_settings.weekday_morning_start,
            end_time=system_settings.weekday_morning_end
        )
        
        result = get_positions_for_guard_periods(guard)
        
        # Wednesday position should NOT be in result
        assert position_wed not in result


# ============================================================================
# Tests for calculate_max_availability_for_week
# ============================================================================

@pytest.mark.django_db
class TestCalculateMaxAvailabilityForWeek:
    """Tests for calculate_max_availability_for_week function."""
    
    @freeze_time("2026-02-02 10:00:00")
    def test_calculates_base_availability_from_workdays(self, system_settings):
        """Test that base availability is 2 shifts per workday."""
        from api.utils.position_calculation import calculate_max_availability_for_week
        
        # system_settings has 5 workdays (Mon-Fri)
        week_start = date(2026, 2, 2)
        week_end = date(2026, 2, 8)
        
        max_avail, breakdown = calculate_max_availability_for_week(week_start, week_end)
        
        # 5 workdays * 2 shifts = 10
        assert breakdown['base_workdays'] == 5
        assert breakdown['base_shifts'] == 10
        assert max_avail == 10
    
    @freeze_time("2026-02-02 10:00:00")
    def test_subtracts_full_day_off(self, system_settings, admin_user):
        """Test that full non-working day removes 2 shifts."""
        from api.utils.position_calculation import calculate_max_availability_for_week
        from api.api_models.schedule import NonWorkingDay
        
        week_start = date(2026, 2, 2)
        week_end = date(2026, 2, 8)
        
        # Add full day off on Monday
        NonWorkingDay.objects.create(
            date=date(2026, 2, 3),  # Monday
            is_full_day=True,
            reason='Holiday',
            created_by=admin_user
        )
        
        max_avail, breakdown = calculate_max_availability_for_week(week_start, week_end)
        
        # 10 base shifts - 2 (full day) = 8
        assert breakdown['full_days_off'] == 1
        assert breakdown['shifts_removed'] == 2
        assert max_avail == 8
    
    @freeze_time("2026-02-02 10:00:00")
    def test_subtracts_half_day_off(self, system_settings, admin_user):
        """Test that half non-working day removes 1 shift."""
        from api.utils.position_calculation import calculate_max_availability_for_week
        from api.api_models.schedule import NonWorkingDay
        
        week_start = date(2026, 2, 2)
        week_end = date(2026, 2, 8)
        
        # Add half day off (morning only)
        NonWorkingDay.objects.create(
            date=date(2026, 2, 3),  # Monday
            is_full_day=False,
            non_working_shift=NonWorkingDay.ShiftType.MORNING,
            reason='Partial closure',
            created_by=admin_user
        )
        
        max_avail, breakdown = calculate_max_availability_for_week(week_start, week_end)
        
        # 10 base shifts - 1 (half day) = 9
        assert breakdown['half_days_off'] == 1
        assert breakdown['shifts_removed'] == 1
        assert max_avail == 9
    
    @freeze_time("2026-02-02 10:00:00")
    def test_handles_multiple_non_working_days(self, system_settings, admin_user):
        """Test calculation with multiple non-working days."""
        from api.utils.position_calculation import calculate_max_availability_for_week
        from api.api_models.schedule import NonWorkingDay
        
        week_start = date(2026, 2, 2)
        week_end = date(2026, 2, 8)
        
        # Add 1 full day and 2 half days
        NonWorkingDay.objects.create(
            date=date(2026, 2, 3),  # Monday - full day
            is_full_day=True,
            reason='Holiday',
            created_by=admin_user
        )
        
        NonWorkingDay.objects.create(
            date=date(2026, 2, 4),  # Tuesday - morning only
            is_full_day=False,
            non_working_shift=NonWorkingDay.ShiftType.MORNING,
            reason='Partial',
            created_by=admin_user
        )
        
        NonWorkingDay.objects.create(
            date=date(2026, 2, 5),  # Wednesday - afternoon only
            is_full_day=False,
            non_working_shift=NonWorkingDay.ShiftType.AFTERNOON,
            reason='Partial',
            created_by=admin_user
        )
        
        max_avail, breakdown = calculate_max_availability_for_week(week_start, week_end)
        
        # 10 base - 2 (full) - 1 (half) - 1 (half) = 6
        assert breakdown['full_days_off'] == 1
        assert breakdown['half_days_off'] == 2
        assert breakdown['shifts_removed'] == 4
        assert max_avail == 6

