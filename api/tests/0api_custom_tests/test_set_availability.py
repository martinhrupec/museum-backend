"""
Integration tests for set_availability endpoint.

Tests:
- Guard can set their own availability
- Admin CANNOT set guard availability (guard-only)
- Validation rules for availability values
"""
import pytest
from api.api_models import Guard


@pytest.mark.django_db
class TestAdminSetAvailability:
    """Integration tests verifying admin CANNOT use POST /api/guards/{id}/set_availability/"""
    
    def test_admin_cannot_set_guard_availability(self, authenticated_admin, guard_user, system_settings):
        """
        Admin attempting to set guard availability should be rejected.
        
        This is a guard-only endpoint - admins cannot modify guard availability.
        
        Expected:
        - 403 Forbidden
        - Error message about admin restriction
        """
        response = authenticated_admin.post(
            f'/api/guards/{guard_user.guard.id}/set_availability/',
            {
                'available_shifts': 5
            },
            format='json'
        )
        
        assert response.status_code == 403
        assert 'admin' in str(response.data).lower() or 'čuvar' in str(response.data).lower()
    
    def test_set_availability_without_authentication_fails(self, api_client, guard_user):
        """
        Setting availability without authentication fails.
        
        Expected:
        - 401 or 403 response
        """
        response = api_client.post(
            f'/api/guards/{guard_user.guard.id}/set_availability/',
            {
                'available_shifts': 5
            },
            format='json'
        )
        
        assert response.status_code in (401, 403)


@pytest.mark.django_db
class TestGuardSetAvailability:
    """Integration tests for guard using POST /api/guards/{id}/set_availability/"""
    
    def test_guard_can_set_own_availability(self, authenticated_guard, guard_user, system_settings, mock_config_window_open):
        """
        Guard successfully sets their own availability.
        
        Expected:
        - 200 response
        - Availability updated in database
        - Response contains success message
        """
        response = authenticated_guard.post(
            f'/api/guards/{guard_user.guard.id}/set_availability/',
            {
                'available_shifts': 3
            },
            format='json'
        )
        
        assert response.status_code == 200
        assert 'message' in response.data
        
        # Verify database was updated
        guard_user.guard.refresh_from_db()
        assert guard_user.guard.availability == 3
    
    def test_guard_can_set_maximum_availability(self, authenticated_guard, guard_user, system_settings, mock_config_window_open):
        """
        Guard can set availability up to maximum available shifts.
        
        Expected:
        - 200 response for valid availability
        """
        # Set a reasonable availability value
        response = authenticated_guard.post(
            f'/api/guards/{guard_user.guard.id}/set_availability/',
            {
                'available_shifts': 5
            },
            format='json'
        )
        
        assert response.status_code == 200
        guard_user.guard.refresh_from_db()
        assert guard_user.guard.availability == 5
    
    def test_guard_cannot_set_negative_availability(self, authenticated_guard, guard_user, system_settings):
        """
        Guard cannot set negative availability.
        
        Expected:
        - 400 Bad Request
        - Error about invalid value
        """
        response = authenticated_guard.post(
            f'/api/guards/{guard_user.guard.id}/set_availability/',
            {
                'available_shifts': -1
            },
            format='json'
        )
        
        assert response.status_code == 400
    
    def test_guard_cannot_set_other_guards_availability(
        self, authenticated_guard, second_guard_user, system_settings
    ):
        """
        Guard cannot set another guard's availability.
        
        Expected:
        - 403 Forbidden or 404 Not Found
        """
        response = authenticated_guard.post(
            f'/api/guards/{second_guard_user.guard.id}/set_availability/',
            {
                'available_shifts': 3
            },
            format='json'
        )
        
        assert response.status_code in (403, 404)
    
    def test_guard_set_availability_missing_field(self, authenticated_guard, guard_user, system_settings):
        """
        Guard must provide available_shifts field.
        
        Expected:
        - 400 Bad Request
        """
        response = authenticated_guard.post(
            f'/api/guards/{guard_user.guard.id}/set_availability/',
            {},
            format='json'
        )
        
        assert response.status_code == 400
        assert 'available_shifts' in str(response.data).lower()
    
    def test_guard_set_availability_invalid_type(self, authenticated_guard, guard_user, system_settings):
        """
        Guard must provide integer value for available_shifts.
        
        Expected:
        - 400 Bad Request
        """
        response = authenticated_guard.post(
            f'/api/guards/{guard_user.guard.id}/set_availability/',
            {
                'available_shifts': 'abc'
            },
            format='json'
        )
        
        assert response.status_code == 400
    
    def test_guard_set_zero_availability(self, authenticated_guard, guard_user, system_settings, mock_config_window_open):
        """
        Guard can set availability to zero (unavailable).
        
        Expected:
        - 200 response
        """
        response = authenticated_guard.post(
            f'/api/guards/{guard_user.guard.id}/set_availability/',
            {
                'available_shifts': 0
            },
            format='json'
        )
        
        assert response.status_code == 200
        guard_user.guard.refresh_from_db()
        assert guard_user.guard.availability == 0
