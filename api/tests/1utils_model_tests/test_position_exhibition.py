"""
Tests for Position, Exhibition model methods and helper functions.

These tests cover:
- Position.get_assigned_guard()
- Position.get_start_datetime()
- Position.clean()
- Position.is_special_event
- Position.get_duration_hours()
- Position.get_period()
- Exhibition.is_active()
- Exhibition.is_upcoming
- Exhibition.is_finished
- Exhibition.clean()
- AuditLog.log_create(), log_update(), log_delete()
- NonWorkingDay.delete_affected_positions()
"""
import pytest
from datetime import datetime, date, time, timedelta
from decimal import Decimal
from django.utils import timezone
from django.core.exceptions import ValidationError
from freezegun import freeze_time

from api.api_models import (
    Exhibition, 
    Position, 
    PositionHistory,
    Guard,
    SystemSettings,
    AuditLog,
    NonWorkingDay
)
from django.contrib.auth import get_user_model

User = get_user_model()


# ============================================================================
# Tests for Exhibition model methods
# ============================================================================

@pytest.mark.django_db
class TestExhibitionIsActive:
    """Tests for Exhibition.is_active() method."""
    
    def test_exhibition_is_active_on_start_date(self, system_settings):
        """Test that exhibition is active on its start date."""
        now = timezone.now()
        exhibition = Exhibition.objects.create(
            name='Active Test',
            number_of_positions=1,
            start_date=now,
            end_date=now + timedelta(days=30),
            open_on=[1, 2, 3, 4, 5]
        )
        
        assert exhibition.is_active(now) is True
    
    def test_exhibition_is_active_on_end_date(self, system_settings):
        """Test that exhibition is active on its end date."""
        now = timezone.now()
        start_date = now - timedelta(days=30)
        
        exhibition = Exhibition.objects.create(
            name='Ending Test',
            number_of_positions=1,
            start_date=start_date,
            end_date=now,
            open_on=[1, 2, 3, 4, 5]
        )
        
        assert exhibition.is_active(now) is True
    
    def test_exhibition_not_active_before_start(self, system_settings):
        """Test that exhibition is NOT active before start date."""
        future_start = timezone.now() + timedelta(days=10)
        
        exhibition = Exhibition.objects.create(
            name='Future Test',
            number_of_positions=1,
            start_date=future_start,
            end_date=future_start + timedelta(days=30),
            open_on=[1, 2, 3, 4, 5]
        )
        
        assert exhibition.is_active(timezone.now()) is False
    
    def test_exhibition_not_active_after_end(self, system_settings):
        """Test that exhibition is NOT active after end date."""
        past_end = timezone.now() - timedelta(days=1)
        
        exhibition = Exhibition.objects.create(
            name='Finished Test',
            number_of_positions=1,
            start_date=past_end - timedelta(days=30),
            end_date=past_end,
            open_on=[1, 2, 3, 4, 5]
        )
        
        assert exhibition.is_active(timezone.now()) is False


@pytest.mark.django_db
class TestExhibitionIsUpcoming:
    """Tests for Exhibition.is_upcoming property."""
    
    def test_future_exhibition_is_upcoming(self, system_settings):
        """Test that future exhibition is marked as upcoming."""
        future_start = timezone.now() + timedelta(days=10)
        
        exhibition = Exhibition.objects.create(
            name='Upcoming Test',
            number_of_positions=1,
            start_date=future_start,
            end_date=future_start + timedelta(days=30),
            open_on=[1, 2, 3, 4, 5]
        )
        
        assert exhibition.is_upcoming is True
    
    def test_current_exhibition_not_upcoming(self, system_settings):
        """Test that current exhibition is NOT upcoming."""
        now = timezone.now()
        
        exhibition = Exhibition.objects.create(
            name='Current Test',
            number_of_positions=1,
            start_date=now - timedelta(days=5),
            end_date=now + timedelta(days=30),
            open_on=[1, 2, 3, 4, 5]
        )
        
        assert exhibition.is_upcoming is False


@pytest.mark.django_db
class TestExhibitionIsFinished:
    """Tests for Exhibition.is_finished property."""
    
    def test_past_exhibition_is_finished(self, system_settings):
        """Test that past exhibition is marked as finished."""
        past_end = timezone.now() - timedelta(days=1)
        
        exhibition = Exhibition.objects.create(
            name='Finished Test',
            number_of_positions=1,
            start_date=past_end - timedelta(days=30),
            end_date=past_end,
            open_on=[1, 2, 3, 4, 5]
        )
        
        assert exhibition.is_finished is True
    
    def test_current_exhibition_not_finished(self, system_settings):
        """Test that current exhibition is NOT finished."""
        now = timezone.now()
        
        exhibition = Exhibition.objects.create(
            name='Current Test',
            number_of_positions=1,
            start_date=now - timedelta(days=5),
            end_date=now + timedelta(days=30),
            open_on=[1, 2, 3, 4, 5]
        )
        
        assert exhibition.is_finished is False


@pytest.mark.django_db
class TestExhibitionClean:
    """Tests for Exhibition.clean() validation."""
    
    def test_special_event_requires_same_day_dates(self, system_settings):
        """Test that special events must have same start/end date."""
        event_date = timezone.now()
        
        exhibition = Exhibition(
            name='Bad Special Event',
            number_of_positions=1,
            start_date=event_date,
            end_date=event_date + timedelta(days=1),  # Different day!
            is_special_event=True,
            event_start_time=time(18, 0),
            event_end_time=time(22, 0)
        )
        
        with pytest.raises(ValidationError) as exc:
            exhibition.clean()
        
        assert "same day" in str(exc.value).lower()
    
    def test_special_event_requires_start_time(self, system_settings):
        """Test that special events require event_start_time."""
        event_date = timezone.now()
        
        exhibition = Exhibition(
            name='Missing Start Time',
            number_of_positions=1,
            start_date=event_date,
            end_date=event_date,
            is_special_event=True,
            # event_start_time missing!
            event_end_time=time(22, 0)
        )
        
        with pytest.raises(ValidationError) as exc:
            exhibition.clean()
        
        assert "start_time" in str(exc.value).lower()


# ============================================================================
# Tests for Position model methods
# ============================================================================

@pytest.mark.django_db
class TestPositionGetAssignedGuard:
    """Tests for Position.get_assigned_guard() method."""
    
    def test_returns_none_for_unassigned_position(self, sample_exhibition, system_settings):
        """Test that unassigned position returns None."""
        position = Position.objects.create(
            exhibition=sample_exhibition,
            date=system_settings.next_week_start,
            start_time=time(10, 0),
            end_time=time(14, 0)
        )
        
        assert position.get_assigned_guard() is None
    
    def test_returns_guard_when_assigned(self, sample_exhibition, system_settings, guard_user):
        """Test that assigned position returns the guard."""
        position = Position.objects.create(
            exhibition=sample_exhibition,
            date=system_settings.next_week_start,
            start_time=time(10, 0),
            end_time=time(14, 0)
        )
        
        guard = Guard.objects.get(user=guard_user)
        PositionHistory.objects.create(
            position=position,
            guard=guard,
            action=PositionHistory.Action.ASSIGNED
        )
        
        assert position.get_assigned_guard() == guard
    
    def test_returns_none_after_cancellation(self, sample_exhibition, system_settings, guard_user, mocker):
        """Test that cancelled position returns None."""
        from freezegun import freeze_time
        
        position = Position.objects.create(
            exhibition=sample_exhibition,
            date=system_settings.next_week_start,
            start_time=time(10, 0),
            end_time=time(14, 0)
        )
        
        guard = Guard.objects.get(user=guard_user)
        
        # First assign at time T
        with freeze_time("2026-02-01 10:00:00"):
            PositionHistory.objects.create(
                position=position,
                guard=guard,
                action=PositionHistory.Action.ASSIGNED
            )
        
        # Then cancel at time T+1 minute
        with freeze_time("2026-02-01 10:01:00"):
            PositionHistory.objects.create(
                position=position,
                guard=guard,
                action=PositionHistory.Action.CANCELLED
            )
        
        assert position.get_assigned_guard() is None


@pytest.mark.django_db
class TestPositionGetDurationHours:
    """Tests for Position.get_duration_hours() method."""
    
    def test_four_hour_shift(self, sample_exhibition, system_settings):
        """Test that 4-hour shift returns 4.0."""
        position = Position.objects.create(
            exhibition=sample_exhibition,
            date=system_settings.next_week_start,
            start_time=time(10, 0),
            end_time=time(14, 0)
        )
        
        assert position.get_duration_hours() == Decimal('4.0')
    
    def test_half_hour_shift(self, sample_exhibition, system_settings):
        """Test that 3.5-hour shift returns 3.5."""
        position = Position.objects.create(
            exhibition=sample_exhibition,
            date=system_settings.next_week_start,
            start_time=time(10, 0),
            end_time=time(13, 30)
        )
        
        assert position.get_duration_hours() == Decimal('3.5')


@pytest.mark.django_db
class TestPositionGetPeriod:
    """Tests for Position.get_period() method."""
    
    def test_this_week_position_returns_this_week(self, sample_exhibition, system_settings):
        """Test that position in this_week returns 'this_week'."""
        position = Position.objects.create(
            exhibition=sample_exhibition,
            date=system_settings.this_week_start + timedelta(days=1),
            start_time=time(10, 0),
            end_time=time(14, 0)
        )
        
        assert position.get_period(system_settings) == 'this_week'
    
    def test_next_week_position_returns_next_week(self, sample_exhibition, system_settings):
        """Test that position in next_week returns 'next_week'."""
        position = Position.objects.create(
            exhibition=sample_exhibition,
            date=system_settings.next_week_start + timedelta(days=1),
            start_time=time(10, 0),
            end_time=time(14, 0)
        )
        
        assert position.get_period(system_settings) == 'next_week'
    
    def test_future_position_returns_none(self, sample_exhibition, system_settings):
        """Test that position outside both weeks returns None."""
        position = Position.objects.create(
            exhibition=sample_exhibition,
            date=system_settings.next_week_end + timedelta(days=10),
            start_time=time(10, 0),
            end_time=time(14, 0)
        )
        
        assert position.get_period(system_settings) is None


@pytest.mark.django_db
class TestPositionGetStartDatetime:
    """Tests for Position.get_start_datetime() method."""
    
    def test_returns_timezone_aware_datetime(self, sample_exhibition, system_settings):
        """Test that method returns timezone-aware datetime."""
        position = Position.objects.create(
            exhibition=sample_exhibition,
            date=date(2026, 2, 10),
            start_time=time(11, 30),
            end_time=time(15, 30)
        )
        
        start_dt = position.get_start_datetime()
        
        assert timezone.is_aware(start_dt)
        assert start_dt.date() == date(2026, 2, 10)
        assert start_dt.hour == 11
        assert start_dt.minute == 30


@pytest.mark.django_db
class TestPositionClean:
    """Tests for Position.clean() validation."""
    
    def test_start_time_must_be_before_end_time(self, sample_exhibition, system_settings):
        """Test that start_time must be before end_time."""
        position = Position(
            exhibition=sample_exhibition,
            date=system_settings.next_week_start,
            start_time=time(16, 0),
            end_time=time(10, 0)  # Before start!
        )
        
        with pytest.raises(ValidationError) as exc:
            position.clean()
        
        assert "before end time" in str(exc.value).lower()


@pytest.mark.django_db
class TestPositionIsSpecialEvent:
    """Tests for Position.is_special_event property."""
    
    def test_regular_exhibition_position_not_special(self, sample_exhibition, system_settings):
        """Test that regular exhibition position is not special event."""
        position = Position.objects.create(
            exhibition=sample_exhibition,
            date=system_settings.next_week_start,
            start_time=time(10, 0),
            end_time=time(14, 0)
        )
        
        assert position.is_special_event is False
    
    def test_special_event_position_is_special(self, special_event_exhibition, system_settings):
        """Test that special event position is marked as special."""
        position = Position.objects.create(
            exhibition=special_event_exhibition,
            date=special_event_exhibition.start_date.date(),
            start_time=time(18, 0),
            end_time=time(22, 0)
        )
        
        assert position.is_special_event is True


# ============================================================================
# Tests for AuditLog methods
# ============================================================================

@pytest.mark.django_db
class TestAuditLogMethods:
    """Tests for AuditLog class methods."""
    
    def test_log_create_records_creation(self, admin_user, sample_exhibition):
        """Test that log_create properly records object creation."""
        log = AuditLog.log_create(
            user=admin_user,
            instance=sample_exhibition,
            request=None
        )
        
        assert log.action == AuditLog.Action.CREATE
        assert log.model_name == 'Exhibition'
        assert log.object_id == str(sample_exhibition.pk)
        assert log.user == admin_user
    
    def test_log_update_records_changes(self, admin_user, sample_exhibition):
        """Test that log_update records field changes."""
        changes = {
            'name': {'old': 'Old Name', 'new': 'New Name'},
            'number_of_positions': {'old': 2, 'new': 3}
        }
        
        log = AuditLog.log_update(
            user=admin_user,
            instance=sample_exhibition,
            changed_fields=changes,
            request=None
        )
        
        assert log.action == AuditLog.Action.UPDATE
        assert log.changes == changes
        assert 'name' in log.changes
    
    def test_log_delete_records_deletion(self, admin_user, sample_exhibition):
        """Test that log_delete records object deletion."""
        log = AuditLog.log_delete(
            user=admin_user,
            instance=sample_exhibition,
            request=None
        )
        
        assert log.action == AuditLog.Action.DELETE
        assert log.model_name == 'Exhibition'
    
    def test_get_client_ip_extracts_ip_from_request(self, admin_user, sample_exhibition, mocker):
        """Test that _get_client_ip extracts IP from request META."""
        # Mock request object
        mock_request = mocker.MagicMock()
        mock_request.META = {
            'REMOTE_ADDR': '192.168.1.100',
            'HTTP_USER_AGENT': 'Test Browser'
        }
        
        log = AuditLog.log_create(
            user=admin_user,
            instance=sample_exhibition,
            request=mock_request
        )
        
        assert log.ip_address == '192.168.1.100'
        assert log.user_agent == 'Test Browser'
    
    def test_get_client_ip_handles_x_forwarded_for(self, admin_user, sample_exhibition, mocker):
        """Test that _get_client_ip handles proxy X-Forwarded-For header."""
        mock_request = mocker.MagicMock()
        mock_request.META = {
            'HTTP_X_FORWARDED_FOR': '10.0.0.1, 192.168.1.1, 172.16.0.1',
            'REMOTE_ADDR': '192.168.1.100',
            'HTTP_USER_AGENT': ''
        }
        
        log = AuditLog.log_create(
            user=admin_user,
            instance=sample_exhibition,
            request=mock_request
        )
        
        # Should use first IP from X-Forwarded-For
        assert log.ip_address == '10.0.0.1'


# ============================================================================
# Tests for NonWorkingDay.delete_affected_positions
# ============================================================================

@pytest.mark.django_db
class TestNonWorkingDayDeleteAffectedPositions:
    """Tests for NonWorkingDay.delete_affected_positions method."""
    
    def test_deletes_positions_on_full_day(self, system_settings):
        """Test that full-day non-working day deletes all positions on that date."""
        exhibition = Exhibition.objects.create(
            name='NonWorkingDay Test',
            number_of_positions=1,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            open_on=[1, 2, 3, 4]
        )
        
        # Create positions for a specific date
        test_date = date(2026, 2, 10)
        Position.objects.create(
            exhibition=exhibition,
            date=test_date,
            start_time=time(10, 0),
            end_time=time(14, 0)
        )
        Position.objects.create(
            exhibition=exhibition,
            date=test_date,
            start_time=time(14, 0),
            end_time=time(18, 0)
        )
        
        initial_count = Position.objects.filter(date=test_date).count()
        assert initial_count == 2
        
        # Create non-working day
        nwd = NonWorkingDay.objects.create(
            date=test_date,
            is_full_day=True,
            reason='Test Holiday'
        )
        
        # Call delete method
        nwd.delete_affected_positions()
        
        # All positions on that date should be deleted
        final_count = Position.objects.filter(date=test_date).count()
        assert final_count == 0
    
    def test_deletes_only_morning_positions(self, system_settings):
        """Test that morning non-working day deletes only morning positions."""
        exhibition = Exhibition.objects.create(
            name='Morning Test',
            number_of_positions=1,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            open_on=[1, 2, 3, 4]
        )
        
        test_date = date(2026, 2, 11)
        
        # Morning position
        morning_pos = Position.objects.create(
            exhibition=exhibition,
            date=test_date,
            start_time=system_settings.weekday_morning_start,
            end_time=system_settings.weekday_morning_end
        )
        
        # Afternoon position
        afternoon_pos = Position.objects.create(
            exhibition=exhibition,
            date=test_date,
            start_time=system_settings.weekday_afternoon_start,
            end_time=system_settings.weekday_afternoon_end
        )
        
        # Create morning non-working day
        nwd = NonWorkingDay.objects.create(
            date=test_date,
            is_full_day=False,
            non_working_shift=NonWorkingDay.ShiftType.MORNING,
            reason='Morning off'
        )
        
        nwd.delete_affected_positions()
        
        # Morning position should be deleted
        assert not Position.objects.filter(id=morning_pos.id).exists()
        # Afternoon position should remain
        assert Position.objects.filter(id=afternoon_pos.id).exists()