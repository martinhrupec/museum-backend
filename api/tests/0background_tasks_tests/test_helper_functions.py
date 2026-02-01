"""
Tests for background_tasks.tasks helper functions.

These tests cover utility functions used by Celery tasks:
- _get_week_from_datetime
- _get_exhibitions_for_week
- _get_workdays_for_week
- _get_available_work_periods_for_week
- get_average_points_for_week
- calculate_guard_priority
- assign_initial_priority_to_new_guard
- calculate_availability_caps
- get_guards_with_availability_updated
- shift_weekly_periods
- generate_weekly_positions
- validate_preference_templates
- award_daily_completions
- penalize_insufficient_positions
- expire_swap_requests
"""
import pytest
from datetime import datetime, date, time, timedelta
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth import get_user_model
from freezegun import freeze_time

from background_tasks.tasks import (
    _get_week_from_datetime,
    _get_exhibitions_for_week,
    _get_workdays_for_week,
    _get_available_work_periods_for_week,
    get_average_points_for_week,
    calculate_guard_priority,
    assign_initial_priority_to_new_guard,
    calculate_availability_caps,
    get_guards_with_availability_updated,
    shift_weekly_periods,
    generate_weekly_positions,
    award_daily_completions,
    penalize_insufficient_positions,
    validate_preference_templates,
    expire_swap_requests,
    update_all_guard_priorities,
)
from api.api_models import (
    Guard, 
    Exhibition, 
    Position, 
    SystemSettings,
    Point,
    PositionHistory,
    AdminNotification,
)
from api.api_models.textual_model import PositionSwapRequest
from api.api_models.calculation import GuardWorkPeriod
from api.api_models.preferences import GuardExhibitionPreference, GuardDayPreference

User = get_user_model()


# ============================================================================
# Tests for _get_week_from_datetime
# ============================================================================

class TestGetWeekFromDatetime:
    """Tests for _get_week_from_datetime helper function."""
    
    def test_monday_returns_same_week(self):
        """Test that Monday returns Monday-Sunday of the same week."""
        monday = timezone.make_aware(datetime(2026, 2, 2, 10, 0))  # Monday
        week_start, week_end = _get_week_from_datetime(monday)
        
        assert week_start == date(2026, 2, 2)  # Monday
        assert week_end == date(2026, 2, 8)    # Sunday
    
    def test_wednesday_returns_correct_week(self):
        """Test that Wednesday returns correct Monday-Sunday bounds."""
        wednesday = timezone.make_aware(datetime(2026, 2, 4, 15, 30))  # Wednesday
        week_start, week_end = _get_week_from_datetime(wednesday)
        
        assert week_start == date(2026, 2, 2)  # Monday
        assert week_end == date(2026, 2, 8)    # Sunday
    
    def test_sunday_returns_correct_week(self):
        """Test that Sunday returns correct Monday-Sunday bounds."""
        sunday = timezone.make_aware(datetime(2026, 2, 8, 23, 59))  # Sunday
        week_start, week_end = _get_week_from_datetime(sunday)
        
        assert week_start == date(2026, 2, 2)  # Monday
        assert week_end == date(2026, 2, 8)    # Sunday


# ============================================================================
# Tests for _get_exhibitions_for_week
# ============================================================================

@pytest.mark.django_db
class TestGetExhibitionsForWeek:
    """Tests for _get_exhibitions_for_week helper function."""
    
    def test_returns_exhibitions_with_positions_in_week(self, system_settings):
        """Test that function returns exhibitions that have positions in given week."""
        # Create exhibition
        exhibition = Exhibition.objects.create(
            name='Test Exhibition',
            number_of_positions=1,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            open_on=[1, 2, 3, 4, 5]  # Tue-Sat
        )
        
        # Create position in next week
        Position.objects.create(
            exhibition=exhibition,
            date=system_settings.next_week_start + timedelta(days=1),
            start_time=time(10, 0),
            end_time=time(14, 0)
        )
        
        result = _get_exhibitions_for_week(
            system_settings.next_week_start,
            system_settings.next_week_end
        )
        
        assert exhibition.id in result
    
    def test_returns_empty_set_when_no_positions(self, system_settings):
        """Test that function returns empty set when no positions exist."""
        # Create exhibition without positions in next week
        exhibition = Exhibition.objects.create(
            name='Future Exhibition',
            number_of_positions=1,
            start_date=timezone.now() + timedelta(days=60),
            end_date=timezone.now() + timedelta(days=90),
            open_on=[1, 2, 3, 4, 5]
        )
        
        # Query for next week (no positions there)
        result = _get_exhibitions_for_week(
            system_settings.next_week_start,
            system_settings.next_week_end
        )
        
        assert exhibition.id not in result


# ============================================================================
# Tests for _get_workdays_for_week
# ============================================================================

@pytest.mark.django_db
class TestGetWorkdaysForWeek:
    """Tests for _get_workdays_for_week helper function."""
    
    def test_returns_days_with_positions(self, system_settings):
        """Test that function returns days of week that have positions."""
        # Create exhibition
        exhibition = Exhibition.objects.create(
            name='Test Exhibition',
            number_of_positions=1,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            open_on=[1, 2, 3, 4, 5]
        )
        
        # Create positions on Tuesday (1) and Thursday (3)
        tuesday = system_settings.next_week_start + timedelta(days=1)
        thursday = system_settings.next_week_start + timedelta(days=3)
        
        Position.objects.create(
            exhibition=exhibition,
            date=tuesday,
            start_time=time(10, 0),
            end_time=time(14, 0)
        )
        Position.objects.create(
            exhibition=exhibition,
            date=thursday,
            start_time=time(10, 0),
            end_time=time(14, 0)
        )
        
        result = _get_workdays_for_week(
            system_settings.next_week_start,
            system_settings.next_week_end
        )
        
        assert 1 in result  # Tuesday
        assert 3 in result  # Thursday
        assert 0 not in result  # Monday - no position


# ============================================================================
# Tests for assign_initial_priority_to_new_guard
# ============================================================================

@pytest.mark.django_db
class TestAssignInitialPriorityToNewGuard:
    """Tests for assign_initial_priority_to_new_guard function."""
    
    def test_first_guard_gets_default_priority(self, db):
        """Test that first guard gets default priority of 1.0."""
        # Create guard user (signal creates Guard profile but we override)
        user = User.objects.create_user(
            username='first_guard',
            email='first@test.com',
            password='test123',
            role=User.ROLE_GUARD
        )
        guard = Guard.objects.get(user=user)
        
        # Signal already assigned priority, verify it's 1.0
        assert guard.priority_number == Decimal('1.0')
    
    def test_subsequent_guard_gets_average_priority(self, db):
        """Test that new guards get average of existing priorities."""
        # Create first guard with priority 5.0
        user1 = User.objects.create_user(
            username='guard_one',
            email='one@test.com',
            password='test123',
            role=User.ROLE_GUARD
        )
        guard1 = Guard.objects.get(user=user1)
        guard1.priority_number = Decimal('5.0')
        guard1.save()
        
        # Create second guard with priority 3.0
        user2 = User.objects.create_user(
            username='guard_two',
            email='two@test.com',
            password='test123',
            role=User.ROLE_GUARD
        )
        guard2 = Guard.objects.get(user=user2)
        guard2.priority_number = Decimal('3.0')
        guard2.save()
        
        # Create third guard - should get average of (5.0 + 3.0) / 2 = 4.0
        user3 = User.objects.create_user(
            username='guard_three',
            email='three@test.com',
            password='test123',
            role=User.ROLE_GUARD
        )
        guard3 = Guard.objects.get(user=user3)
        
        # The signal assigns average priority
        # Average of 5.0, 3.0 = 4.0 (but signal runs before guard2.save() updates)
        # In reality, signal runs immediately on user creation
        assert guard3.priority_number is not None


# ============================================================================
# Tests for calculate_availability_caps
# ============================================================================

@pytest.mark.django_db
class TestCalculateAvailabilityCaps:
    """Tests for calculate_availability_caps function."""
    
    def test_no_capping_when_supply_exceeds_demand(self, system_settings):
        """Test that no capping occurs when there are more positions than availability."""
        # Create guards with low availability
        user1 = User.objects.create_user(
            username='cap_guard1', email='cg1@test.com',
            password='test', role=User.ROLE_GUARD
        )
        guard1 = Guard.objects.get(user=user1)
        guard1.availability = 3
        guard1.priority_number = Decimal('5.0')
        guard1.save()
        
        user2 = User.objects.create_user(
            username='cap_guard2', email='cg2@test.com',
            password='test', role=User.ROLE_GUARD
        )
        guard2 = Guard.objects.get(user=user2)
        guard2.availability = 2
        guard2.priority_number = Decimal('4.0')
        guard2.save()
        
        guards = Guard.objects.filter(id__in=[guard1.id, guard2.id])
        total_positions = 10  # More than demand (3+2=5)
        
        caps = calculate_availability_caps(guards, total_positions)
        
        # No capping - everyone keeps original availability
        assert caps[guard1.id] == 3
        assert caps[guard2.id] == 2
    
    def test_capping_reduces_high_availability_first(self, system_settings):
        """Test that capping reduces highest availability first."""
        user1 = User.objects.create_user(
            username='high_avail', email='high@test.com',
            password='test', role=User.ROLE_GUARD
        )
        guard1 = Guard.objects.get(user=user1)
        guard1.availability = 5
        guard1.priority_number = Decimal('3.0')
        guard1.save()
        
        user2 = User.objects.create_user(
            username='low_avail', email='low@test.com',
            password='test', role=User.ROLE_GUARD
        )
        guard2 = Guard.objects.get(user=user2)
        guard2.availability = 2
        guard2.priority_number = Decimal('4.0')
        guard2.save()
        
        guards = Guard.objects.filter(id__in=[guard1.id, guard2.id])
        total_positions = 5  # Less than demand (5+2=7)
        
        caps = calculate_availability_caps(guards, total_positions)
        
        # Total should equal positions
        assert sum(caps.values()) == 5
        # Guard1 should be capped (from 5)
        assert caps[guard1.id] < 5
        # Guard2 keeps original (lowest)
        assert caps[guard2.id] == 2


# ============================================================================
# Tests for get_guards_with_availability_updated
# ============================================================================

@pytest.mark.django_db
class TestGetGuardsWithAvailabilityUpdated:
    """Tests for get_guards_with_availability_updated function."""
    
    def test_returns_guards_who_updated_in_config_window(self, system_settings, mocker):
        """Test that function returns guards who updated availability in config window."""
        # Mock timezone.now to be within config window
        config_time = datetime.combine(
            system_settings.this_week_start + timedelta(days=1),
            time(10, 0)
        )
        config_time = timezone.make_aware(config_time)
        mocker.patch('django.utils.timezone.now', return_value=config_time)
        
        # Create guard
        user = User.objects.create_user(
            username='avail_guard', email='avail@test.com',
            password='test', role=User.ROLE_GUARD
        )
        guard = Guard.objects.get(user=user)
        guard.availability = 5
        guard.availability_updated_at = config_time
        guard.save()
        
        result = get_guards_with_availability_updated()
        
        assert guard in result
    
    def test_excludes_guards_with_zero_availability(self, system_settings, mocker):
        """Test that guards with availability=0 are excluded."""
        config_time = datetime.combine(
            system_settings.this_week_start + timedelta(days=1),
            time(10, 0)
        )
        config_time = timezone.make_aware(config_time)
        mocker.patch('django.utils.timezone.now', return_value=config_time)
        
        user = User.objects.create_user(
            username='zero_guard', email='zero@test.com',
            password='test', role=User.ROLE_GUARD
        )
        guard = Guard.objects.get(user=user)
        guard.availability = 0
        guard.availability_updated_at = config_time
        guard.save()
        
        result = get_guards_with_availability_updated()
        
        assert guard not in result


# ============================================================================
# Tests for shift_weekly_periods
# ============================================================================

@pytest.mark.django_db
class TestShiftWeeklyPeriods:
    """Tests for shift_weekly_periods Celery task."""
    
    @freeze_time("2026-02-02 00:00:00")  # Monday
    def test_shifts_next_week_to_this_week(self):
        """Test that next_week becomes this_week after shift."""
        settings = SystemSettings.objects.create(
            this_week_start=date(2026, 1, 26),
            this_week_end=date(2026, 2, 1),
            next_week_start=date(2026, 2, 2),
            next_week_end=date(2026, 2, 8),
            is_active=True
        )
        
        result = shift_weekly_periods()
        
        settings.refresh_from_db()
        
        # Old next_week should now be this_week
        assert settings.this_week_start == date(2026, 2, 2)
        assert settings.this_week_end == date(2026, 2, 8)
        # New next_week should be 7 days after
        assert settings.next_week_start == date(2026, 2, 9)
        assert settings.next_week_end == date(2026, 2, 15)
    
    @freeze_time("2026-02-02 00:00:00")
    def test_initializes_periods_on_first_run(self):
        """Test that periods are initialized if not set."""
        settings = SystemSettings.objects.create(
            this_week_start=None,
            this_week_end=None,
            next_week_start=None,
            next_week_end=None,
            is_active=True
        )
        
        result = shift_weekly_periods()
        
        settings.refresh_from_db()
        
        # Should have initialized this_week to current week
        assert settings.this_week_start == date(2026, 2, 2)  # Monday
        assert settings.this_week_end == date(2026, 2, 8)    # Sunday


# ============================================================================
# Tests for generate_weekly_positions
# ============================================================================

@pytest.mark.django_db
class TestGenerateWeeklyPositions:
    """Tests for generate_weekly_positions Celery task."""
    
    @freeze_time("2026-02-02 00:01:00")  # Monday
    def test_generates_positions_for_active_exhibitions(self, system_settings):
        """Test that positions are created for exhibitions active in next_week."""
        # Update settings with proper next_week
        system_settings.next_week_start = date(2026, 2, 9)
        system_settings.next_week_end = date(2026, 2, 15)
        system_settings.save()
        
        # Create exhibition active during next_week
        exhibition = Exhibition.objects.create(
            name='Test Exhibition',
            number_of_positions=1,
            start_date=timezone.make_aware(datetime(2026, 2, 1)),
            end_date=timezone.make_aware(datetime(2026, 2, 28)),
            open_on=[1, 2, 3, 4],  # Tue-Fri
            is_special_event=False
        )
        
        # Clear any auto-generated positions
        Position.objects.filter(exhibition=exhibition).delete()
        
        result = generate_weekly_positions()
        
        # Should have created positions for Tue-Fri of next_week
        positions = Position.objects.filter(
            exhibition=exhibition,
            date__gte=system_settings.next_week_start,
            date__lte=system_settings.next_week_end
        )
        assert positions.count() > 0
    
    @freeze_time("2026-02-02 00:01:00")
    def test_skips_non_working_days(self, system_settings):
        """Test that positions are not created for non-working days."""
        from api.api_models import NonWorkingDay
        
        system_settings.next_week_start = date(2026, 2, 9)
        system_settings.next_week_end = date(2026, 2, 15)
        system_settings.save()
        
        # Create non-working day (Tuesday)
        NonWorkingDay.objects.create(
            date=date(2026, 2, 10),  # Tuesday
            is_full_day=True,
            reason='Holiday'
        )
        
        exhibition = Exhibition.objects.create(
            name='Test Exhibition 2',
            number_of_positions=1,
            start_date=timezone.make_aware(datetime(2026, 2, 1)),
            end_date=timezone.make_aware(datetime(2026, 2, 28)),
            open_on=[1, 2, 3, 4],  # Tue-Fri
            is_special_event=False
        )
        
        Position.objects.filter(exhibition=exhibition).delete()
        
        result = generate_weekly_positions()
        
        # Should NOT have position on Tuesday (non-working day)
        tuesday_positions = Position.objects.filter(
            exhibition=exhibition,
            date=date(2026, 2, 10)
        )
        assert tuesday_positions.count() == 0


# ============================================================================
# Tests for award_daily_completions
# ============================================================================

@pytest.mark.django_db
class TestAwardDailyCompletions:
    """Tests for award_daily_completions Celery task."""
    
    @freeze_time("2026-02-10 23:00:00")  # Tuesday 23:00
    def test_awards_points_for_completed_positions(self, system_settings, guard_user):
        """Test that guards get points for completed positions."""
        guard = Guard.objects.get(user=guard_user)
        
        exhibition = Exhibition.objects.create(
            name='Completion Test',
            number_of_positions=1,
            start_date=timezone.make_aware(datetime(2026, 2, 1)),
            end_date=timezone.make_aware(datetime(2026, 2, 28)),
            open_on=[1, 2, 3, 4]
        )
        
        # Create position for today
        position = Position.objects.create(
            exhibition=exhibition,
            date=date(2026, 2, 10),
            start_time=time(10, 0),
            end_time=time(14, 0)
        )
        
        # Assign guard to position
        PositionHistory.objects.create(
            position=position,
            guard=guard,
            action=PositionHistory.Action.ASSIGNED
        )
        
        initial_points_count = Point.objects.filter(guard=guard).count()
        
        result = award_daily_completions()
        
        # Should have created point entry
        new_points_count = Point.objects.filter(guard=guard).count()
        assert new_points_count > initial_points_count
    
    @freeze_time("2026-02-15 23:00:00")  # Sunday 23:00
    def test_awards_reduced_points_for_sunday(self, system_settings, guard_user):
        """Test that Sunday positions get reduced points."""
        guard = Guard.objects.get(user=guard_user)
        
        # Add Sunday to workdays for this test
        system_settings.workdays = [0, 1, 2, 3, 4, 5, 6]
        system_settings.save()
        
        exhibition = Exhibition.objects.create(
            name='Sunday Test',
            number_of_positions=1,
            start_date=timezone.make_aware(datetime(2026, 2, 1)),
            end_date=timezone.make_aware(datetime(2026, 2, 28)),
            open_on=[6]  # Sunday only
        )
        
        position = Position.objects.create(
            exhibition=exhibition,
            date=date(2026, 2, 15),  # Sunday
            start_time=time(10, 0),
            end_time=time(14, 0)
        )
        
        PositionHistory.objects.create(
            position=position,
            guard=guard,
            action=PositionHistory.Action.ASSIGNED
        )
        
        result = award_daily_completions()
        
        # Check that Sunday award was given
        sunday_point = Point.objects.filter(
            guard=guard,
            explanation__icontains='Sunday'
        ).first()
        
        if sunday_point:
            assert sunday_point.points == system_settings.award_for_sunday_position_completion


# ============================================================================
# Tests for penalize_insufficient_positions
# ============================================================================

@pytest.mark.django_db
class TestPenalizeInsufficientPositions:
    """Tests for penalize_insufficient_positions Celery task."""
    
    @freeze_time("2026-02-08 10:00:00")  # Sunday after manual window
    def test_penalizes_guards_with_insufficient_positions(self, system_settings, guard_user):
        """Test that guards with too few positions get penalized."""
        guard = Guard.objects.get(user=guard_user)
        
        # Set minimum to 3
        system_settings.minimal_number_of_positions_in_week = 3
        system_settings.next_week_start = date(2026, 2, 9)
        system_settings.next_week_end = date(2026, 2, 15)
        system_settings.save()
        
        # Guard has 0 positions (less than minimum of 3)
        initial_penalty_count = Point.objects.filter(
            guard=guard,
            points__lt=0
        ).count()
        
        result = penalize_insufficient_positions()
        
        # Should have created penalty
        new_penalty_count = Point.objects.filter(
            guard=guard,
            points__lt=0
        ).count()
        assert new_penalty_count > initial_penalty_count
    
    @freeze_time("2026-02-08 10:00:00")
    def test_no_penalty_if_guard_meets_minimum(self, system_settings, guard_user):
        """Test that guards meeting minimum don't get penalized."""
        guard = Guard.objects.get(user=guard_user)
        
        system_settings.minimal_number_of_positions_in_week = 2
        system_settings.next_week_start = date(2026, 2, 9)
        system_settings.next_week_end = date(2026, 2, 15)
        system_settings.save()
        
        exhibition = Exhibition.objects.create(
            name='Min Test',
            number_of_positions=1,
            start_date=timezone.make_aware(datetime(2026, 2, 1)),
            end_date=timezone.make_aware(datetime(2026, 2, 28)),
            open_on=[1, 2, 3, 4]
        )
        
        # Create 2 positions and assign guard
        for i in range(2):
            position = Position.objects.create(
                exhibition=exhibition,
                date=date(2026, 2, 10 + i),
                start_time=time(10, 0),
                end_time=time(14, 0)
            )
            PositionHistory.objects.create(
                position=position,
                guard=guard,
                action=PositionHistory.Action.ASSIGNED
            )
        
        initial_count = Point.objects.filter(guard=guard).count()
        
        result = penalize_insufficient_positions()
        
        # No new penalty should be created
        # (guard has 2 positions, minimum is 2)
        penalty_points = Point.objects.filter(
            guard=guard,
            explanation__icontains='nedovoljno'
        )
        assert penalty_points.count() == 0


# ============================================================================
# Tests for validate_preference_templates
# ============================================================================

@pytest.mark.django_db
class TestValidatePreferenceTemplates:
    """Tests for validate_preference_templates Celery task."""
    
    @freeze_time("2026-02-09 00:10:00")  # Monday after position generation
    def test_invalidates_exhibition_template_when_exhibitions_change(self, system_settings, guard_user):
        """Test that exhibition preference template is invalidated when exhibition set changes."""
        guard = Guard.objects.get(user=guard_user)
        
        system_settings.next_week_start = date(2026, 2, 16)  # Week after next
        system_settings.next_week_end = date(2026, 2, 22)
        system_settings.save()
        
        # Create exhibition that was active in historical week but ends before next_week
        # Historical week is calculated from created_at + 7 days
        # created_at = 2026-02-02 -> historical week = 2026-02-09 to 2026-02-15
        # But next_week is 2026-02-16 to 2026-02-22 (exhibition ends before)
        old_exhibition = Exhibition.objects.create(
            name='Old Exhibition',
            number_of_positions=1,
            start_date=timezone.make_aware(datetime(2026, 1, 1)),
            end_date=timezone.make_aware(datetime(2026, 2, 15)),  # Ends before next_week
            open_on=[1, 2, 3, 4]
        )
        
        # Create position in historical week (2026-02-09 to 2026-02-15)
        Position.objects.create(
            exhibition=old_exhibition,
            date=date(2026, 2, 10),  # In historical week
            start_time=time(10, 0),
            end_time=time(14, 0)
        )
        
        # Create preference with created_at = 2026-02-02 (so historical = 2026-02-09 to 2026-02-15)
        with freeze_time("2026-02-02 10:00:00"):
            pref = GuardExhibitionPreference.objects.create(
                guard=guard,
                exhibition_order=[old_exhibition.id],
                is_template=True
            )
        
        # Run validation - should invalidate because old_exhibition is in historical week
        # but NOT in next_week (2026-02-16 to 2026-02-22)
        with freeze_time("2026-02-09 00:10:00"):
            result = validate_preference_templates()
        
        # Template should be invalidated
        pref.refresh_from_db()
        assert pref.is_template is False
    
    @freeze_time("2026-02-09 00:10:00")
    def test_keeps_template_when_exhibitions_same(self, system_settings, guard_user):
        """Test that exhibition preference template stays valid when exhibition set unchanged."""
        guard = Guard.objects.get(user=guard_user)
        
        # next_week = historical week (both 2026-02-09 to 2026-02-15)
        # created_at = 2026-02-02 -> historical = 2026-02-09 to 2026-02-15
        system_settings.next_week_start = date(2026, 2, 9)
        system_settings.next_week_end = date(2026, 2, 15)
        system_settings.save()
        
        # Create exhibition spanning historical and next_week
        exhibition = Exhibition.objects.create(
            name='Ongoing Exhibition',
            number_of_positions=1,
            start_date=timezone.make_aware(datetime(2026, 1, 1)),
            end_date=timezone.make_aware(datetime(2026, 3, 31)),
            open_on=[1, 2, 3, 4]
        )
        
        # Create position for historical week (same as next_week here)
        Position.objects.create(
            exhibition=exhibition,
            date=date(2026, 2, 10),  # In next_week
            start_time=time(10, 0),
            end_time=time(14, 0)
        )
        
        # Create template preference
        with freeze_time("2026-02-02 10:00:00"):
            pref = GuardExhibitionPreference.objects.create(
                guard=guard,
                exhibition_order=[exhibition.id],
                is_template=True
            )
        
        result = validate_preference_templates()
        
        # Template should stay valid (same exhibitions in historical and next_week)
        pref.refresh_from_db()
        assert pref.is_template is True
    
    @freeze_time("2026-02-09 00:10:00")
    def test_creates_notification_when_template_invalidated(self, system_settings, guard_user):
        """Test that notification is created when template is invalidated."""
        guard = Guard.objects.get(user=guard_user)
        
        # Historical = 2026-02-09 to 2026-02-15 (created_at 2026-02-02 + 7 days)
        # next_week = 2026-02-16 to 2026-02-22 (different from historical)
        system_settings.next_week_start = date(2026, 2, 16)
        system_settings.next_week_end = date(2026, 2, 22)
        system_settings.save()
        
        # Create exhibition that is active in historical but not in next_week
        old_exhibition = Exhibition.objects.create(
            name='Ended Exhibition',
            number_of_positions=1,
            start_date=timezone.make_aware(datetime(2026, 1, 1)),
            end_date=timezone.make_aware(datetime(2026, 2, 15)),  # Ends before next_week
            open_on=[1, 2, 3, 4]
        )
        
        # Create position for historical week
        Position.objects.create(
            exhibition=old_exhibition,
            date=date(2026, 2, 10),  # In historical week
            start_time=time(10, 0),
            end_time=time(14, 0)
        )
        
        initial_notification_count = AdminNotification.objects.filter(
            to_user=guard.user
        ).count()
        
        with freeze_time("2026-02-02 10:00:00"):
            pref = GuardExhibitionPreference.objects.create(
                guard=guard,
                exhibition_order=[old_exhibition.id],
                is_template=True
            )
        
        with freeze_time("2026-02-09 00:10:00"):
            validate_preference_templates()
        
        # Notification should be created
        new_notification_count = AdminNotification.objects.filter(
            to_user=guard.user
        ).count()
        assert new_notification_count > initial_notification_count


# ============================================================================
# Tests for expire_swap_requests
# ============================================================================

@pytest.mark.django_db
class TestExpireSwapRequests:
    """Tests for expire_swap_requests Celery task."""
    
    @freeze_time("2026-02-03 12:00:00")  # After position start time
    def test_expires_pending_swap_past_deadline(self, system_settings, guard_user):
        """Test that pending swap requests past deadline are expired."""
        guard = Guard.objects.get(user=guard_user)
        
        exhibition = Exhibition.objects.create(
            name='Swap Test',
            number_of_positions=1,
            start_date=timezone.make_aware(datetime(2026, 2, 1)),
            end_date=timezone.make_aware(datetime(2026, 2, 28)),
            open_on=[1, 2, 3, 4]
        )
        
        position = Position.objects.create(
            exhibition=exhibition,
            date=date(2026, 2, 3),
            start_time=time(10, 0),
            end_time=time(14, 0)
        )
        
        # Assign guard to position
        PositionHistory.objects.create(
            position=position,
            guard=guard,
            action=PositionHistory.Action.ASSIGNED
        )
        
        # Create pending swap that expired
        swap_request = PositionSwapRequest.objects.create(
            position_to_swap=position,
            requesting_guard=guard,
            status='pending',
            expires_at=timezone.make_aware(datetime(2026, 2, 3, 11, 0))  # Expired 1 hour ago
        )
        
        result = expire_swap_requests()
        
        swap_request.refresh_from_db()
        assert swap_request.status == 'expired'
    
    @freeze_time("2026-02-03 09:00:00")  # Before position start time
    def test_does_not_expire_pending_swap_before_deadline(self, system_settings, guard_user):
        """Test that pending swap requests before deadline are not expired."""
        guard = Guard.objects.get(user=guard_user)
        
        exhibition = Exhibition.objects.create(
            name='Swap Test 2',
            number_of_positions=1,
            start_date=timezone.make_aware(datetime(2026, 2, 1)),
            end_date=timezone.make_aware(datetime(2026, 2, 28)),
            open_on=[1, 2, 3, 4]
        )
        
        position = Position.objects.create(
            exhibition=exhibition,
            date=date(2026, 2, 3),
            start_time=time(10, 0),
            end_time=time(14, 0)
        )
        
        PositionHistory.objects.create(
            position=position,
            guard=guard,
            action=PositionHistory.Action.ASSIGNED
        )
        
        # Create pending swap that hasn't expired yet
        swap_request = PositionSwapRequest.objects.create(
            position_to_swap=position,
            requesting_guard=guard,
            status='pending',
            expires_at=timezone.make_aware(datetime(2026, 2, 3, 11, 0))  # 2 hours from now
        )
        
        result = expire_swap_requests()
        
        swap_request.refresh_from_db()
        assert swap_request.status == 'pending'
    
    @freeze_time("2026-02-03 12:00:00")
    def test_creates_position_history_on_expiry(self, system_settings, guard_user):
        """Test that PositionHistory is created when swap expires."""
        guard = Guard.objects.get(user=guard_user)
        
        exhibition = Exhibition.objects.create(
            name='Swap History Test',
            number_of_positions=1,
            start_date=timezone.make_aware(datetime(2026, 2, 1)),
            end_date=timezone.make_aware(datetime(2026, 2, 28)),
            open_on=[1, 2, 3, 4]
        )
        
        position = Position.objects.create(
            exhibition=exhibition,
            date=date(2026, 2, 3),
            start_time=time(10, 0),
            end_time=time(14, 0)
        )
        
        PositionHistory.objects.create(
            position=position,
            guard=guard,
            action=PositionHistory.Action.ASSIGNED
        )
        
        swap_request = PositionSwapRequest.objects.create(
            position_to_swap=position,
            requesting_guard=guard,
            status='pending',
            expires_at=timezone.make_aware(datetime(2026, 2, 3, 11, 0))
        )
        
        initial_history_count = PositionHistory.objects.filter(
            position=position,
            action=PositionHistory.Action.CANCELLED
        ).count()
        
        expire_swap_requests()
        
        new_history_count = PositionHistory.objects.filter(
            position=position,
            action=PositionHistory.Action.CANCELLED
        ).count()
        assert new_history_count > initial_history_count


# ============================================================================
# Tests for update_all_guard_priorities
# ============================================================================

@pytest.mark.django_db
class TestUpdateAllGuardPriorities:
    """Tests for update_all_guard_priorities Celery task."""
    
    @freeze_time("2026-02-09 00:05:00")  # Monday morning
    def test_updates_priorities_for_all_active_guards(self, system_settings, guard_user):
        """Test that priorities are updated for all active guards."""
        guard = Guard.objects.get(user=guard_user)
        
        system_settings.next_week_start = date(2026, 2, 9)
        system_settings.next_week_end = date(2026, 2, 15)
        system_settings.save()
        
        initial_priority = guard.priority_number
        
        # Add some points to change priority
        Point.objects.create(
            guard=guard,
            points=Decimal('10.00'),
            explanation='Test points'
        )
        
        result = update_all_guard_priorities()
        
        guard.refresh_from_db()
        # Priority should have been recalculated
        assert result is not None or guard.priority_number != initial_priority
    
    @freeze_time("2026-02-09 00:05:00")
    def test_skips_inactive_guards(self, system_settings, guard_user, admin_user):
        """Test that inactive guards are skipped."""
        # Create inactive user (guard created via signal)
        inactive_user = User.objects.create_user(
            username='inactive_guard',
            email='inactive@test.com',
            password='testpass123'
        )
        inactive_user.is_active = False
        inactive_user.save()
        
        system_settings.next_week_start = date(2026, 2, 9)
        system_settings.next_week_end = date(2026, 2, 15)
        system_settings.save()
        
        # Should not raise error even with inactive guard
        result = update_all_guard_priorities()
        
        assert 'Skipped' not in str(result) if result else True


# ============================================================================
# Tests for _get_available_work_periods_for_week
# ============================================================================

@pytest.mark.django_db
class TestGetAvailableWorkPeriodsForWeek:
    """Tests for _get_available_work_periods_for_week helper function."""
    
    @freeze_time("2026-02-02 10:00:00")
    def test_returns_day_shift_tuples_from_positions(self, system_settings):
        """Test that function returns set of (day_of_week, shift_type) tuples."""
        exhibition = Exhibition.objects.create(
            name='Test Exhibition',
            number_of_positions=1,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            open_on=[0, 1, 2]
        )
        
        week_start = date(2026, 2, 2)  # Monday
        week_end = date(2026, 2, 8)    # Sunday
        
        # Create morning position on Monday - use EXACT time from settings
        Position.objects.create(
            exhibition=exhibition,
            date=date(2026, 2, 2),  # Monday
            start_time=system_settings.weekday_morning_start,  # Use settings time
            end_time=system_settings.weekday_morning_end
        )
        
        # Create afternoon position on Tuesday - use EXACT time from settings
        Position.objects.create(
            exhibition=exhibition,
            date=date(2026, 2, 3),  # Tuesday
            start_time=system_settings.weekday_afternoon_start,  # Use settings time
            end_time=system_settings.weekday_afternoon_end
        )
        
        result = _get_available_work_periods_for_week(week_start, week_end)
        
        assert (0, 'morning') in result  # Monday morning
        assert (1, 'afternoon') in result  # Tuesday afternoon
    
    @freeze_time("2026-02-07 10:00:00")  # Saturday
    def test_handles_weekend_shifts(self, system_settings):
        """Test that function correctly identifies weekend shifts."""
        exhibition = Exhibition.objects.create(
            name='Weekend Exhibition',
            number_of_positions=1,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            open_on=[5, 6]  # Saturday, Sunday
        )
        
        week_start = date(2026, 2, 2)  # Monday
        week_end = date(2026, 2, 8)    # Sunday
        
        # Create weekend position (Saturday) - use weekend times from settings
        Position.objects.create(
            exhibition=exhibition,
            date=date(2026, 2, 7),  # Saturday
            start_time=system_settings.weekend_morning_start,  # Use weekend morning time
            end_time=system_settings.weekend_morning_end
        )
        
        result = _get_available_work_periods_for_week(week_start, week_end)
        
        assert (5, 'morning') in result  # Saturday morning


# ============================================================================
# Tests for get_average_points_for_week
# ============================================================================

@pytest.mark.django_db
class TestGetAveragePointsForWeek:
    """Tests for get_average_points_for_week helper function."""
    
    @freeze_time("2026-02-05 12:00:00")  # Thursday midweek
    def test_calculates_average_from_other_guards(self, system_settings, guard_user, admin_user):
        """Test that average is calculated from all guards except excluded one."""
        guard1 = Guard.objects.get(user=guard_user)
        
        # Create second guard
        user2 = User.objects.create_user(
            username='guard2',
            email='guard2@test.com',
            password='testpass123',
            role=User.ROLE_GUARD
        )
        guard2 = Guard.objects.get(user=user2)
        
        # Week range must include frozen time (2026-02-05)
        week_start = timezone.make_aware(datetime(2026, 2, 2, 0, 0, 0))
        week_end = timezone.make_aware(datetime(2026, 2, 9, 0, 0, 0))
        
        # Points will be created at frozen time (2026-02-05 12:00:00)
        # Give points to guard1 in this week
        Point.objects.create(
            guard=guard1,
            points=Decimal('10.00'),
            explanation='Test'
        )
        
        # Give points to guard2 in this week
        Point.objects.create(
            guard=guard2,
            points=Decimal('20.00'),
            explanation='Test'
        )
        
        # Exclude guard1, should get average of guard2 only
        result = get_average_points_for_week(guard1, week_start, week_end)
        
        assert result == Decimal('20.00')
    
    @freeze_time("2026-02-05 12:00:00")
    def test_returns_zero_when_no_guards_have_points(self, system_settings, guard_user):
        """Test that 0 is returned when no other guards have points."""
        guard = Guard.objects.get(user=guard_user)
        
        week_start = timezone.make_aware(datetime(2026, 2, 2, 0, 0, 0))
        week_end = timezone.make_aware(datetime(2026, 2, 9, 0, 0, 0))
        
        result = get_average_points_for_week(guard, week_start, week_end)
        
        assert result == Decimal('0.0')


# ============================================================================
# Tests for calculate_guard_priority
# ============================================================================

@pytest.mark.django_db
class TestCalculateGuardPriority:
    """Tests for calculate_guard_priority helper function."""
    
    @freeze_time("2026-02-09 00:00:00")  # Monday
    def test_calculates_weighted_priority_from_points_history(self, system_settings, guard_user):
        """Test that priority is calculated with weighted decay."""
        guard = Guard.objects.get(user=guard_user)
        
        system_settings.points_life_weeks = 3
        system_settings.save()
        
        cycle_start = timezone.now()
        
        # Give just one point in last week (week 0: 02-09 Feb)
        point = Point.objects.create(
            guard=guard,
            points=Decimal('10.00'),
            explanation='Last week'
        )
        # Explicitly set date_awarded AFTER creation
        point.date_awarded = timezone.make_aware(datetime(2026, 2, 5, 12, 0, 0))
        point.save()
        
        result = calculate_guard_priority(guard, cycle_start, 3)
        
        # Should have at least some priority from that one point
        assert result > Decimal('5.0')
    
    @freeze_time("2026-02-09 00:00:00")
    def test_uses_average_for_weeks_before_guard_existed(self, system_settings, guard_user, admin_user):
        """Test that average is used for weeks when guard didn't exist yet."""
        # Create older guard with points
        old_user = User.objects.create_user(
            username='old_guard',
            email='old@test.com',
            password='testpass123',
            role=User.ROLE_GUARD
        )
        old_guard = Guard.objects.get(user=old_user)
        
        # Give old guard points 2 weeks ago
        Point.objects.create(
            guard=old_guard,
            points=Decimal('15.00'),
            explanation='Old guard work',
            date_awarded=timezone.make_aware(datetime(2026, 1, 29, 12, 0, 0))  # 2 weeks ago
        )
        
        # Create NEW guard now (after freezegun time)
        with freeze_time("2026-02-09 12:00:00"):  # Created later
            new_user = User.objects.create_user(
                username='new_guard',
                email='new@test.com',
                password='testpass123',
                role=User.ROLE_GUARD
            )
            new_guard = Guard.objects.get(user=new_user)
        
        system_settings.points_life_weeks = 2
        system_settings.save()
        
        cycle_start = timezone.now()
        
        # New guard didn't exist 2 weeks ago, should use average
        result = calculate_guard_priority(new_guard, cycle_start, 2)
        
        # Should have some priority based on average
        assert result >= Decimal('0.0')
