"""
Tests for Serializer validation logic.

These tests cover validation in:
- UserAdminSerializer - password required on create
- ChangePasswordSerializer - old password check, password confirmation
- ExhibitionAdminSerializer - open_on days validation
- NonWorkingDaySerializer - date and shift validation
"""
import pytest
from datetime import datetime, date, time, timedelta
from decimal import Decimal
from django.utils import timezone
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.test import APIRequestFactory

from api.serializers import (
    UserAdminSerializer,
    ChangePasswordSerializer,
    ExhibitionAdminSerializer,
    ExhibitionBasicSerializer,
)
from api.api_models import User, Exhibition, SystemSettings
from django.contrib.auth import get_user_model

User = get_user_model()


# ============================================================================
# Tests for UserAdminSerializer validation
# ============================================================================

@pytest.mark.django_db
class TestUserAdminSerializerValidation:
    """Tests for UserAdminSerializer validation logic."""
    
    def test_password_required_on_create(self):
        """Test that password is required when creating new user."""
        data = {
            'username': 'newuser',
            'email': 'new@test.com',
            'role': User.ROLE_GUARD,
            # password missing!
        }
        
        serializer = UserAdminSerializer(data=data)
        
        assert serializer.is_valid() is False
        assert 'password' in serializer.errors
    
    def test_password_not_required_on_update(self, admin_user):
        """Test that password is optional when updating existing user."""
        data = {
            'first_name': 'Updated',
            'last_name': 'Name',
            # password not provided - should be OK for update
        }
        
        serializer = UserAdminSerializer(instance=admin_user, data=data, partial=True)
        
        assert serializer.is_valid() is True
    
    def test_valid_create_with_password(self):
        """Test that user can be created with valid password."""
        data = {
            'username': 'validuser',
            'email': 'valid@test.com',
            'role': User.ROLE_GUARD,
            'password': 'securepass123'
        }
        
        serializer = UserAdminSerializer(data=data)
        
        assert serializer.is_valid() is True
    
    def test_password_update_hashes_password(self, admin_user):
        """Test that password update properly hashes the password."""
        new_password = 'newpassword123'
        data = {'password': new_password}
        
        serializer = UserAdminSerializer(instance=admin_user, data=data, partial=True)
        assert serializer.is_valid() is True
        
        updated_user = serializer.save()
        
        # Password should be hashed, not stored as plain text
        assert updated_user.password != new_password
        assert updated_user.check_password(new_password) is True


# ============================================================================
# Tests for ChangePasswordSerializer validation
# ============================================================================

@pytest.mark.django_db
class TestChangePasswordSerializerValidation:
    """Tests for ChangePasswordSerializer validation logic."""
    
    def test_old_password_must_be_correct(self, guard_user):
        """Test that old password must match current password."""
        factory = APIRequestFactory()
        request = factory.post('/fake/')
        request.user = guard_user
        
        data = {
            'old_password': 'wrongpassword',
            'new_password': 'newpassword123',
            'new_password_confirm': 'newpassword123'
        }
        
        serializer = ChangePasswordSerializer(data=data, context={'request': request})
        
        assert serializer.is_valid() is False
        assert 'old_password' in serializer.errors
    
    def test_new_passwords_must_match(self, guard_user):
        """Test that new_password and new_password_confirm must match."""
        factory = APIRequestFactory()
        request = factory.post('/fake/')
        request.user = guard_user
        
        data = {
            'old_password': 'testpass123',  # Correct password from fixture
            'new_password': 'newpassword123',
            'new_password_confirm': 'differentpassword'  # Doesn't match!
        }
        
        serializer = ChangePasswordSerializer(data=data, context={'request': request})
        
        assert serializer.is_valid() is False
        assert 'new_password_confirm' in serializer.errors
    
    def test_new_password_minimum_length(self, guard_user):
        """Test that new password must meet minimum length requirement."""
        factory = APIRequestFactory()
        request = factory.post('/fake/')
        request.user = guard_user
        
        data = {
            'old_password': 'testpass123',
            'new_password': 'short',  # Too short!
            'new_password_confirm': 'short'
        }
        
        serializer = ChangePasswordSerializer(data=data, context={'request': request})
        
        assert serializer.is_valid() is False
        assert 'new_password' in serializer.errors
    
    def test_valid_password_change(self, guard_user):
        """Test that valid password change passes validation."""
        factory = APIRequestFactory()
        request = factory.post('/fake/')
        request.user = guard_user
        
        data = {
            'old_password': 'testpass123',  # Correct password from fixture
            'new_password': 'newvalidpassword123',
            'new_password_confirm': 'newvalidpassword123'
        }
        
        serializer = ChangePasswordSerializer(data=data, context={'request': request})
        
        assert serializer.is_valid() is True


# ============================================================================
# Tests for ExhibitionAdminSerializer validation
# ============================================================================

@pytest.mark.django_db
class TestExhibitionAdminSerializerValidation:
    """Tests for ExhibitionAdminSerializer validation logic."""
    
    def test_open_on_must_be_subset_of_workdays(self, system_settings):
        """Test that open_on days must be subset of museum workdays."""
        # system_settings has workdays=[0,1,2,3,4] (Mon-Fri)
        data = {
            'name': 'Weekend Exhibition',
            'number_of_positions': 2,
            'start_date': timezone.now(),
            'end_date': timezone.now() + timedelta(days=30),
            'open_on': [5, 6],  # Saturday, Sunday - NOT in workdays!
        }
        
        serializer = ExhibitionAdminSerializer(data=data)
        
        assert serializer.is_valid() is False
        assert 'open_on' in serializer.errors
    
    def test_valid_open_on_subset(self, system_settings):
        """Test that valid open_on subset passes validation."""
        data = {
            'name': 'Valid Exhibition',
            'number_of_positions': 2,
            'start_date': timezone.now(),
            'end_date': timezone.now() + timedelta(days=30),
            'open_on': [1, 2, 3],  # Tue, Wed, Thu - subset of Mon-Fri
        }
        
        serializer = ExhibitionAdminSerializer(data=data)
        
        assert serializer.is_valid() is True


# ============================================================================
# Tests for ExhibitionBasicSerializer computed fields
# ============================================================================

@pytest.mark.django_db
class TestExhibitionBasicSerializerFields:
    """Tests for ExhibitionBasicSerializer computed fields."""
    
    def test_status_active_for_current_exhibition(self, system_settings):
        """Test that active exhibition shows 'active' status."""
        now = timezone.now()
        exhibition = Exhibition.objects.create(
            name='Active Test',
            number_of_positions=1,
            start_date=now - timedelta(days=5),
            end_date=now + timedelta(days=30),
            open_on=[1, 2, 3, 4]
        )
        
        serializer = ExhibitionBasicSerializer(exhibition)
        
        assert serializer.data['status'] == 'active'
    
    def test_status_upcoming_for_future_exhibition(self, system_settings):
        """Test that future exhibition shows 'upcoming' status."""
        future_start = timezone.now() + timedelta(days=10)
        exhibition = Exhibition.objects.create(
            name='Upcoming Test',
            number_of_positions=1,
            start_date=future_start,
            end_date=future_start + timedelta(days=30),
            open_on=[1, 2, 3, 4]
        )
        
        serializer = ExhibitionBasicSerializer(exhibition)
        
        assert serializer.data['status'] == 'upcoming'
    
    def test_status_finished_for_past_exhibition(self, system_settings):
        """Test that past exhibition shows 'finished' status."""
        past_end = timezone.now() - timedelta(days=1)
        exhibition = Exhibition.objects.create(
            name='Finished Test',
            number_of_positions=1,
            start_date=past_end - timedelta(days=30),
            end_date=past_end,
            open_on=[1, 2, 3, 4]
        )
        
        serializer = ExhibitionBasicSerializer(exhibition)
        
        assert serializer.data['status'] == 'finished'
    
    def test_duration_days_calculation(self, system_settings):
        """Test that duration_days is calculated correctly."""
        start = timezone.now()
        end = start + timedelta(days=9)  # 10 days total (inclusive)
        
        exhibition = Exhibition.objects.create(
            name='Duration Test',
            number_of_positions=1,
            start_date=start,
            end_date=end,
            open_on=[1, 2, 3, 4]
        )
        
        serializer = ExhibitionBasicSerializer(exhibition)
        
        assert serializer.data['duration_days'] == 10


# ============================================================================
# Tests for NonWorkingDaySerializer validation
# ============================================================================

@pytest.mark.django_db
class TestNonWorkingDaySerializerValidation:
    """Tests for NonWorkingDaySerializer validation logic."""
    
    def test_non_working_shift_required_when_not_full_day(self, admin_user):
        """Test that non_working_shift is required when is_full_day=False."""
        from api.serializers import NonWorkingDaySerializer
        
        data = {
            'date': date.today(),
            'is_full_day': False,
            # non_working_shift missing!
            'reason': 'Partial closure',
            'created_by': admin_user.id
        }
        
        serializer = NonWorkingDaySerializer(data=data)
        
        assert serializer.is_valid() is False
        assert 'non_working_shift' in serializer.errors
    
    def test_non_working_shift_not_required_when_full_day(self, admin_user):
        """Test that non_working_shift is optional when is_full_day=True."""
        from api.serializers import NonWorkingDaySerializer
        
        data = {
            'date': date.today(),
            'is_full_day': True,
            # non_working_shift not provided - should be OK
            'reason': 'Full closure',
            'created_by': admin_user.id
        }
        
        serializer = NonWorkingDaySerializer(data=data)
        
        assert serializer.is_valid() is True
    
    def test_valid_partial_day_with_shift(self, admin_user):
        """Test that partial day with shift passes validation."""
        from api.serializers import NonWorkingDaySerializer
        from api.api_models.schedule import NonWorkingDay
        
        data = {
            'date': date.today(),
            'is_full_day': False,
            'non_working_shift': NonWorkingDay.ShiftType.MORNING,
            'reason': 'Morning closure',
            'created_by': admin_user.id
        }
        
        serializer = NonWorkingDaySerializer(data=data)
        
        assert serializer.is_valid() is True


# ============================================================================
# Tests for GuardWorkPeriodSerializer validation
# ============================================================================

@pytest.mark.django_db
class TestGuardWorkPeriodSerializerValidation:
    """Tests for GuardWorkPeriodSerializer validation logic."""
    
    def test_day_of_week_must_be_0_to_6(self, guard_user):
        """Test that day_of_week must be between 0-6."""
        from api.serializers import GuardWorkPeriodSerializer
        from api.api_models import Guard
        
        guard = Guard.objects.get(user=guard_user)
        
        # Test invalid day (7)
        data = {
            'guard': guard.id,
            'day_of_week': 7,  # Invalid! Must be 0-6
            'shift_type': 'morning',
            'is_template': True
        }
        
        serializer = GuardWorkPeriodSerializer(data=data)
        
        assert serializer.is_valid() is False
        assert 'day_of_week' in serializer.errors
    
    def test_day_of_week_negative_invalid(self, guard_user):
        """Test that negative day_of_week is invalid."""
        from api.serializers import GuardWorkPeriodSerializer
        from api.api_models import Guard
        
        guard = Guard.objects.get(user=guard_user)
        
        data = {
            'guard': guard.id,
            'day_of_week': -1,  # Invalid!
            'shift_type': 'morning',
            'is_template': True
        }
        
        serializer = GuardWorkPeriodSerializer(data=data)
        
        assert serializer.is_valid() is False
        assert 'day_of_week' in serializer.errors
    
    def test_shift_type_must_be_morning_or_afternoon(self, guard_user):
        """Test that shift_type must be 'morning' or 'afternoon'."""
        from api.serializers import GuardWorkPeriodSerializer
        from api.api_models import Guard
        
        guard = Guard.objects.get(user=guard_user)
        
        data = {
            'guard': guard.id,
            'day_of_week': 1,
            'shift_type': 'evening',  # Invalid! Must be 'morning' or 'afternoon'
            'is_template': True
        }
        
        serializer = GuardWorkPeriodSerializer(data=data)
        
        assert serializer.is_valid() is False
        assert 'shift_type' in serializer.errors
    
    def test_valid_morning_shift(self, guard_user):
        """Test that valid morning shift passes validation."""
        from api.serializers import GuardWorkPeriodSerializer
        from api.api_models import Guard
        
        guard = Guard.objects.get(user=guard_user)
        
        data = {
            'guard': guard.id,
            'day_of_week': 1,  # Tuesday
            'shift_type': 'morning',
            'is_template': True
        }
        
        serializer = GuardWorkPeriodSerializer(data=data)
        
        assert serializer.is_valid() is True
    
    def test_valid_afternoon_shift(self, guard_user):
        """Test that valid afternoon shift passes validation."""
        from api.serializers import GuardWorkPeriodSerializer
        from api.api_models import Guard
        
        guard = Guard.objects.get(user=guard_user)
        
        data = {
            'guard': guard.id,
            'day_of_week': 3,  # Thursday
            'shift_type': 'afternoon',
            'is_template': False,
            'next_week_start': date.today()
        }
        
        serializer = GuardWorkPeriodSerializer(data=data)
        
        assert serializer.is_valid() is True

