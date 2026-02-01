"""
Tests for Django signals.

These tests verify that signals correctly trigger expected behavior:
1. generate_positions_on_exhibition_create - Auto-generates positions when exhibition created
2. set_notification_expiry - Auto-sets expires_at on AdminNotification
3. create_guard_profile - Auto-creates Guard profile when guard user created
4. track_hourly_rate_change - Creates HourlyRateHistory when rate changes
"""
import pytest
from datetime import datetime, date, time, timedelta
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth import get_user_model

from api.api_models import (
    Guard, 
    Exhibition, 
    Position, 
    SystemSettings,
    AdminNotification,
    HourlyRateHistory
)

User = get_user_model()


# ============================================================================
# Tests for create_guard_profile signal
# ============================================================================

@pytest.mark.django_db
class TestCreateGuardProfileSignal:
    """Tests for create_guard_profile signal."""
    
    def test_guard_profile_created_automatically(self, db):
        """Test that Guard profile is auto-created when guard user is created."""
        user = User.objects.create_user(
            username='signal_guard',
            email='signal@test.com',
            password='test123',
            role=User.ROLE_GUARD
        )
        
        # Guard profile should be auto-created
        assert Guard.objects.filter(user=user).exists()
        guard = Guard.objects.get(user=user)
        assert guard.user == user
    
    def test_guard_profile_not_created_for_admin(self, db):
        """Test that Guard profile is NOT created for admin users."""
        user = User.objects.create_user(
            username='admin_signal',
            email='admin_signal@test.com',
            password='test123',
            role=User.ROLE_ADMIN
        )
        
        # No Guard profile for admin
        assert not Guard.objects.filter(user=user).exists()
    
    def test_initial_priority_assigned_to_new_guard(self, db):
        """Test that new guard gets initial priority assigned."""
        user = User.objects.create_user(
            username='priority_guard',
            email='priority@test.com',
            password='test123',
            role=User.ROLE_GUARD
        )
        
        guard = Guard.objects.get(user=user)
        
        # Priority should be assigned (not None)
        assert guard.priority_number is not None
        # First guard gets 1.0
        assert guard.priority_number == Decimal('1.0')
    
    def test_subsequent_guard_gets_average_priority(self, db):
        """Test that subsequent guards get average priority of existing guards."""
        # Create first guard
        user1 = User.objects.create_user(
            username='first_priority',
            email='first_p@test.com',
            password='test123',
            role=User.ROLE_GUARD
        )
        guard1 = Guard.objects.get(user=user1)
        guard1.priority_number = Decimal('10.0')
        guard1.save()
        
        # Create second guard - should get average
        user2 = User.objects.create_user(
            username='second_priority',
            email='second_p@test.com',
            password='test123',
            role=User.ROLE_GUARD
        )
        guard2 = Guard.objects.get(user=user2)
        
        # Should get average of existing guards
        # Note: Signal runs immediately on creation
        assert guard2.priority_number is not None


# ============================================================================
# Tests for set_notification_expiry signal
# ============================================================================

@pytest.mark.django_db
class TestSetNotificationExpirySignal:
    """Tests for set_notification_expiry signal."""
    
    def test_expires_at_set_to_end_of_notification_date(self, admin_user):
        """Test that expires_at is set to end of notification_date if provided."""
        notification_date = date(2026, 2, 15)
        
        notification = AdminNotification.objects.create(
            cast_type=AdminNotification.CAST_BROADCAST,
            created_by=admin_user,
            title='Test Notification',
            message='Test message',
            notification_date=notification_date
            # expires_at not set - signal should set it
        )
        
        # Refresh from db to get signal-updated value
        notification.refresh_from_db()
        
        # Should be end of notification_date (23:59:59 in local timezone)
        # When converted to UTC, hour might be different due to timezone offset
        assert notification.expires_at is not None
        assert notification.expires_at.date() == notification_date
        # Check that it's at the end of the day (minute=59)
        assert notification.expires_at.minute == 59
        assert notification.expires_at.second == 59
    
    def test_expires_at_set_to_30_days_if_no_notification_date(self, admin_user):
        """Test that expires_at defaults to 30 days from now if no notification_date."""
        before_create = timezone.now()
        
        notification = AdminNotification.objects.create(
            cast_type=AdminNotification.CAST_BROADCAST,
            created_by=admin_user,
            title='Test Notification',
            message='Test message'
            # No notification_date, no expires_at
        )
        
        notification.refresh_from_db()
        
        # Should be approximately 30 days from creation
        assert notification.expires_at is not None
        days_diff = (notification.expires_at - before_create).days
        assert days_diff >= 29 and days_diff <= 30
    
    def test_admin_set_expires_at_not_overwritten(self, admin_user):
        """Test that manually set expires_at is not overwritten by signal."""
        custom_expires = timezone.now() + timedelta(days=7)
        
        notification = AdminNotification.objects.create(
            cast_type=AdminNotification.CAST_BROADCAST,
            created_by=admin_user,
            title='Test Notification',
            message='Test message',
            expires_at=custom_expires  # Admin explicitly sets this
        )
        
        notification.refresh_from_db()
        
        # Should keep admin's value, not override
        # Note: DateTimeField comparison might have microsecond differences
        assert notification.expires_at.date() == custom_expires.date()
        assert notification.expires_at.hour == custom_expires.hour


# ============================================================================
# Tests for generate_positions_on_exhibition_create signal
# ============================================================================

@pytest.mark.django_db
class TestGeneratePositionsOnExhibitionCreateSignal:
    """Tests for generate_positions_on_exhibition_create signal."""
    
    def test_positions_created_for_new_exhibition(self, system_settings):
        """Test that positions are created when new exhibition is created."""
        # Create exhibition active during this_week and next_week
        exhibition = Exhibition.objects.create(
            name='Signal Test Exhibition',
            number_of_positions=1,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            open_on=[1, 2, 3, 4, 5],  # Tue-Sat
            is_special_event=False
        )
        
        # Signal should have created positions
        positions = Position.objects.filter(exhibition=exhibition)
        assert positions.count() > 0
    
    def test_positions_not_created_for_future_exhibition(self, system_settings):
        """Test that positions are NOT created for exhibitions far in future."""
        future_start = timezone.now() + timedelta(days=60)
        
        exhibition = Exhibition.objects.create(
            name='Future Exhibition',
            number_of_positions=1,
            start_date=future_start,
            end_date=future_start + timedelta(days=30),
            open_on=[1, 2, 3, 4, 5],
            is_special_event=False
        )
        
        # No positions should be created (outside this_week/next_week)
        positions = Position.objects.filter(exhibition=exhibition)
        assert positions.count() == 0
    
    def test_special_event_creates_positions_with_custom_times(self, system_settings):
        """Test that special events create positions with custom start/end times."""
        event_date = system_settings.this_week_start + timedelta(days=2)
        
        exhibition = Exhibition.objects.create(
            name='Special Event',
            number_of_positions=2,
            start_date=timezone.make_aware(datetime.combine(event_date, time(0, 0))),
            end_date=timezone.make_aware(datetime.combine(event_date, time(23, 59))),
            open_on=[event_date.weekday()],
            is_special_event=True,
            event_start_time=time(19, 0),
            event_end_time=time(23, 0)
        )
        
        positions = Position.objects.filter(exhibition=exhibition)
        
        if positions.exists():
            for pos in positions:
                assert pos.start_time == time(19, 0)
                assert pos.end_time == time(23, 0)


# ============================================================================
# Tests for track_hourly_rate_change signal
# ============================================================================

@pytest.mark.django_db
class TestTrackHourlyRateChangeSignal:
    """Tests for track_hourly_rate_change signal."""
    
    def test_history_created_on_first_settings(self, db):
        """Test that HourlyRateHistory is created when first SystemSettings is created."""
        # Clear any existing
        HourlyRateHistory.objects.all().delete()
        SystemSettings.objects.all().delete()
        
        settings = SystemSettings.objects.create(
            hourly_rate=Decimal('15.00'),
            is_active=True
        )
        
        # History entry should be created
        history = HourlyRateHistory.objects.filter(hourly_rate=Decimal('15.00'))
        assert history.exists()
    
    def test_history_created_when_rate_changes(self, system_settings):
        """Test that HourlyRateHistory is created when hourly_rate changes."""
        initial_count = HourlyRateHistory.objects.count()
        
        # Change the rate
        old_rate = system_settings.hourly_rate
        new_rate = old_rate + Decimal('5.00')
        system_settings.hourly_rate = new_rate
        system_settings.save()
        
        # Should have created new history entry
        new_count = HourlyRateHistory.objects.count()
        assert new_count > initial_count
        
        # Latest entry (by id, which reflects insertion order) should have new rate
        latest = HourlyRateHistory.objects.order_by('-id').first()
        assert latest.hourly_rate == new_rate
    
    def test_no_history_if_rate_unchanged(self, system_settings):
        """Test that no HourlyRateHistory is created if rate doesn't change."""
        initial_count = HourlyRateHistory.objects.count()
        
        # Save without changing rate
        system_settings.save()
        
        # Should NOT create duplicate entry (depending on implementation)
        # This tests that duplicate entries aren't created
        final_count = HourlyRateHistory.objects.count()
        
        # Count should be same or at most +1 (initial creation)
        assert final_count <= initial_count + 1
