"""
Example unit test for User model save() logic.

This demonstrates:
- Unit testing with pytest
- Using @pytest.mark.django_db for database access
- Parametrized tests
- Testing model business logic
"""
import pytest
from django.contrib.auth import get_user_model

User = get_user_model()


@pytest.mark.django_db
class TestUserModelSaveLogic:
    """Unit tests for User.save() role enforcement logic"""
    
    def test_admin_role_automatically_sets_staff_flag(self):
        """
        When creating admin user, is_staff should be True.
        Tests business rule: ROLE_ADMIN → is_staff=True
        """
        user = User.objects.create_user(
            username='admin1',
            password='testpass',
            role=User.ROLE_ADMIN
        )
        
        assert user.is_staff is True
        assert user.role == User.ROLE_ADMIN
    
    def test_guard_role_automatically_sets_staff_false(self):
        """
        When creating guard user, is_staff should be False.
        Tests business rule: ROLE_GUARD → is_staff=False
        """
        user = User.objects.create_user(
            username='guard1',
            password='testpass',
            role=User.ROLE_GUARD
        )
        
        assert user.is_staff is False
        assert user.role == User.ROLE_GUARD
    
    @pytest.mark.parametrize("role,expected_staff", [
        (User.ROLE_ADMIN, True),
        (User.ROLE_GUARD, False),
    ])
    def test_role_drives_staff_flag_parametrized(self, role, expected_staff):
        """
        Parametrized test: role automatically sets is_staff.
        Covers both roles in single test.
        """
        user = User.objects.create_user(
            username=f'user_{role}',
            password='testpass',
            role=role
        )
        
        assert user.is_staff == expected_staff
    
    def test_changing_role_updates_staff_flag(self):
        """
        When changing user role, is_staff should update automatically.
        Tests role enforcement on save().
        """
        # Create guard
        user = User.objects.create_user(
            username='changeable',
            password='testpass',
            role=User.ROLE_GUARD
        )
        assert user.is_staff is False
        
        # Promote to admin
        user.role = User.ROLE_ADMIN
        user.save()
        
        assert user.is_staff is True
    
    def test_superuser_always_admin_role(self):
        """
        Superusers should always be ROLE_ADMIN regardless of initial role.
        Tests business rule: is_superuser=True → ROLE_ADMIN
        """
        user = User.objects.create_superuser(
            username='superuser',
            password='testpass',
            email='super@museum.com'
        )
        
        assert user.is_superuser is True
        assert user.role == User.ROLE_ADMIN
        assert user.is_staff is True
    
    def test_cannot_manually_set_guard_as_staff(self):
        """
        Attempting to set is_staff=True for guard should be overridden.
        Tests role enforcement prevents inconsistent states.
        """
        user = User(
            username='guard_attempt_staff',
            role=User.ROLE_GUARD
        )
        user.is_staff = True  # Try to force it
        user.set_password('testpass')
        user.save()
        
        # Should be corrected to False
        assert user.is_staff is False


@pytest.mark.django_db
class TestGuardProfileCreation:
    """Unit tests for Guard profile signal"""
    
    def test_guard_profile_created_on_user_creation(self):
        """
        When guard user is created, Guard profile should auto-create via signal.
        """
        user = User.objects.create_user(
            username='newguard',
            password='testpass',
            role=User.ROLE_GUARD
        )
        
        # Check Guard profile exists
        assert hasattr(user, 'guard')
        assert user.guard is not None
        assert user.guard.user == user
    
    def test_admin_user_does_not_get_guard_profile(self):
        """
        Admin users should not have Guard profile.
        """
        user = User.objects.create_user(
            username='admin',
            password='testpass',
            role=User.ROLE_ADMIN
        )
        
        # Check no guard profile
        with pytest.raises(User.guard.RelatedObjectDoesNotExist):
            _ = user.guard
    
    def test_guard_profile_has_default_values(self):
        """
        New Guard profile should have default priority and None for availability.
        Note: priority_number is now auto-assigned via signal (assign_initial_priority_to_new_guard)
        """
        user = User.objects.create_user(
            username='newguard',
            password='testpass',
            role=User.ROLE_GUARD
        )
        
        guard = user.guard
        # priority_number is assigned automatically (1.0 for first guard, average for subsequent)
        assert guard.priority_number is not None
        assert guard.availability is None
        assert guard.availability_updated_at is None
