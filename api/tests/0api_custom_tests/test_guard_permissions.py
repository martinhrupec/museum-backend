"""
Tests for Guard permission enforcement - admins vs guards.

Test that admins CANNOT modify guard-specific fields:
- availability
- priority_number
- work_periods
- preferences (exhibition, day)

Only guards themselves can modify these fields.
"""
import pytest
from django.urls import reverse
from rest_framework import status
from api.models import User


@pytest.mark.django_db
class TestAdminGuardPermissions:
    """Test admin permissions on guard-specific fields"""
    
    def test_admin_cannot_set_guard_availability(self, authenticated_admin, guard_user, system_settings):
        """Admin should NOT be able to set guard availability via action endpoint"""
        url = reverse('guard-set-availability', kwargs={'pk': guard_user.guard.id})
        data = {
            'available_shifts': 3,
            'save_for_future': False
        }
        
        response = authenticated_admin.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert 'Administratori ne mogu' in response.data['error']
    
    def test_admin_cannot_set_guard_work_periods(self, authenticated_admin, guard_user, system_settings):
        """Admin should NOT be able to set guard work periods via action endpoint"""
        url = reverse('guard-set-work-periods', kwargs={'pk': guard_user.guard.id})
        data = {
            'periods': [
                {
                    'day_of_week': 0,
                    'shift_type': 'MORNING'
                }
            ],
            'save_for_future': False
        }
        
        response = authenticated_admin.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert 'Administratori ne mogu' in response.data['error']
    
    def test_admin_cannot_set_exhibition_preferences(self, authenticated_admin, guard_user, system_settings, sample_exhibition):
        """Admin should NOT be able to set guard exhibition preferences"""
        url = reverse('guard-set-exhibition-preferences', kwargs={'pk': guard_user.guard.id})
        data = {
            'exhibition_ids': [sample_exhibition.id],
            'save_as_template': False
        }
        
        response = authenticated_admin.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert 'Administratori ne mogu' in response.data['error']
    
    def test_admin_cannot_set_day_preferences(self, authenticated_admin, guard_user, system_settings):
        """Admin should NOT be able to set guard day preferences"""
        url = reverse('guard-set-day-preferences', kwargs={'pk': guard_user.guard.id})
        data = {
            'day_of_week_list': [0, 1, 2],
            'save_as_template': False
        }
        
        response = authenticated_admin.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert 'Administratori ne mogu' in response.data['error']
    
    def test_admin_cannot_update_availability_via_patch(self, authenticated_admin, guard_user, system_settings):
        """Admin should NOT be able to PATCH guard availability field"""
        # Set initial availability explicitly
        guard = guard_user.guard
        guard.availability = 2
        guard.save()
        
        url = reverse('guard-detail', kwargs={'pk': guard.id})
        data = {'availability': 5}
        
        response = authenticated_admin.patch(url, data, format='json')
        
        # PATCH is not allowed on GuardViewSet (http_method_names excludes 'patch')
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
        guard.refresh_from_db()
        assert guard.availability == 2  # Should remain unchanged
    
    def test_admin_cannot_update_priority_via_patch(self, authenticated_admin, guard_user, system_settings):
        """Admin should NOT be able to PATCH guard priority_number field"""
        # Set initial priority explicitly
        guard = guard_user.guard
        guard.priority_number = 5
        guard.save()
        
        url = reverse('guard-detail', kwargs={'pk': guard.id})
        data = {'priority_number': 999}
        
        response = authenticated_admin.patch(url, data, format='json')
        
        # PATCH is not allowed on GuardViewSet (http_method_names excludes 'patch')
        assert response.status_code == status.HTTP_405_METHOD_NOT_ALLOWED
        guard.refresh_from_db()
        assert guard.priority_number == 5  # Should remain unchanged


@pytest.mark.django_db
class TestGuardOwnPermissions:
    """Test that guards CAN modify their own fields"""
    
    def test_guard_can_set_own_availability(self, authenticated_guard, guard_user, mock_config_window_open):
        """Guard should be able to set their own availability"""
        guard = guard_user.guard
        url = reverse('guard-set-availability', kwargs={'pk': guard.id})
        data = {
            'available_shifts': 3,
            'save_for_future': False
        }
        
        response = authenticated_guard.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        guard.refresh_from_db()
        assert guard.availability == 3
    
    def test_guard_cannot_set_other_guard_availability(self, authenticated_guard, second_guard_user, mock_config_window_open):
        """Guard should NOT be able to set another guard's availability"""
        url = reverse('guard-set-availability', kwargs={'pk': second_guard_user.guard.id})
        data = {
            'available_shifts': 3,
            'save_for_future': False
        }
        
        response = authenticated_guard.post(url, data, format='json')
        
        # 404 (queryset filtering hides other guards) or 403 (explicit denial) are both valid
        assert response.status_code in (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND)
    
    def test_guard_can_set_own_work_periods(self, authenticated_guard, guard_user, mock_config_window_open):
        """Guard should be able to set their own work periods"""
        guard = guard_user.guard
        # Set availability first (required before setting work periods)
        guard.availability = 2
        guard.save()
        
        url = reverse('guard-set-work-periods', kwargs={'pk': guard.id})
        data = {
            'periods': [
                {
                    'day_of_week': 0,
                    'shift_type': 'morning'
                },
                {
                    'day_of_week': 1,
                    'shift_type': 'afternoon'
                }
            ],
            'save_for_future': False
        }
        
        response = authenticated_guard.post(url, data, format='json')
        
        assert response.status_code == status.HTTP_200_OK
        assert response.data['count'] == 2
    
    def test_guard_cannot_set_other_guard_work_periods(self, authenticated_guard, second_guard_user, mock_config_window_open):
        """Guard should NOT be able to set another guard's work periods"""
        url = reverse('guard-set-work-periods', kwargs={'pk': second_guard_user.guard.id})
        data = {
            'periods': [
                {
                    'day_of_week': 0,
                    'shift_type': 'morning'
                }
            ],
            'save_for_future': False
        }
        
        response = authenticated_guard.post(url, data, format='json')
        
        # 404 (queryset filtering hides other guards) or 403 (explicit denial) are both valid
        assert response.status_code in (status.HTTP_403_FORBIDDEN, status.HTTP_404_NOT_FOUND)
