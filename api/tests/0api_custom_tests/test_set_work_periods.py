"""
Integration tests for set_work_periods endpoint.

Tests:
- Guard can set their own work periods
- Admin CANNOT set guard work periods (guard-only)
- Validation rules for work periods
"""
import pytest
from api.api_models import GuardWorkPeriod


@pytest.mark.django_db
class TestAdminSetWorkPeriods:
    """Integration tests verifying admin CANNOT use POST /api/guards/{id}/set_work_periods/"""
    
    def test_admin_cannot_set_guard_work_periods(self, authenticated_admin, guard_user, system_settings):
        """
        Admin attempting to set guard work periods should be rejected.
        
        This is a guard-only endpoint - admins cannot modify guard work periods.
        
        Expected:
        - 403 Forbidden
        """
        response = authenticated_admin.post(
            f'/api/guards/{guard_user.guard.id}/set_work_periods/',
            {
                'periods': [
                    {'day_of_week': 0, 'shift_type': 'morning'},
                    {'day_of_week': 1, 'shift_type': 'afternoon'}
                ]
            },
            format='json'
        )
        
        assert response.status_code == 403
        assert 'admin' in str(response.data).lower() or 'čuvar' in str(response.data).lower()


@pytest.mark.django_db
class TestGuardSetWorkPeriods:
    """Integration tests for guard using POST /api/guards/{id}/set_work_periods/"""
    
    def test_guard_can_set_own_work_periods(self, authenticated_guard, guard_user, system_settings, mock_config_window_open):
        """
        Guard successfully sets their own work periods.
        
        Expected:
        - 200 response
        - Work periods created in database
        """
        # First set availability (required)
        guard_user.guard.availability = 2
        guard_user.guard.save()
        
        response = authenticated_guard.post(
            f'/api/guards/{guard_user.guard.id}/set_work_periods/',
            {
                'periods': [
                    {'day_of_week': 0, 'shift_type': 'morning'},
                    {'day_of_week': 1, 'shift_type': 'afternoon'}
                ]
            },
            format='json'
        )
        
        assert response.status_code == 200
        assert 'message' in response.data
        assert 'periods' in response.data
        
        # Verify database
        periods = GuardWorkPeriod.objects.filter(guard=guard_user.guard)
        assert periods.count() == 2
    
    def test_guard_can_save_work_periods_as_template(self, authenticated_guard, guard_user, system_settings, mock_config_window_open):
        """
        Guard can save work periods as template for future weeks.
        
        Expected:
        - 200 response
        - is_template=True on created periods
        """
        guard_user.guard.availability = 2
        guard_user.guard.save()
        
        response = authenticated_guard.post(
            f'/api/guards/{guard_user.guard.id}/set_work_periods/',
            {
                'periods': [
                    {'day_of_week': 0, 'shift_type': 'morning'},
                    {'day_of_week': 1, 'shift_type': 'afternoon'}
                ],
                'save_for_future_weeks': True
            },
            format='json'
        )
        
        assert response.status_code == 200
        
        # Verify template flag
        periods = GuardWorkPeriod.objects.filter(guard=guard_user.guard, is_template=True)
        assert periods.count() == 2
    
    def test_guard_cannot_set_work_periods_without_availability(
        self, authenticated_guard, guard_user, system_settings
    ):
        """
        Guard must set availability before setting work periods.
        
        Expected:
        - 400 Bad Request
        """
        # Ensure no availability set
        guard_user.guard.availability = None
        guard_user.guard.save()
        
        response = authenticated_guard.post(
            f'/api/guards/{guard_user.guard.id}/set_work_periods/',
            {
                'periods': [
                    {'day_of_week': 0, 'shift_type': 'morning'}
                ]
            },
            format='json'
        )
        
        assert response.status_code == 400
        assert 'dostupnost' in str(response.data).lower() or 'availability' in str(response.data).lower()
    
    def test_guard_cannot_set_periods_less_than_availability(
        self, authenticated_guard, guard_user, system_settings
    ):
        """
        Number of periods must be >= availability.
        
        Expected:
        - 400 Bad Request
        """
        guard_user.guard.availability = 5
        guard_user.guard.save()
        
        response = authenticated_guard.post(
            f'/api/guards/{guard_user.guard.id}/set_work_periods/',
            {
                'periods': [
                    {'day_of_week': 0, 'shift_type': 'morning'},
                    {'day_of_week': 1, 'shift_type': 'afternoon'}
                ]  # Only 2 periods, but availability is 5
            },
            format='json'
        )
        
        assert response.status_code == 400
    
    def test_guard_cannot_set_other_guards_work_periods(
        self, authenticated_guard, second_guard_user, system_settings
    ):
        """
        Guard cannot set another guard's work periods.
        
        Expected:
        - 403 Forbidden or 404 Not Found
        """
        response = authenticated_guard.post(
            f'/api/guards/{second_guard_user.guard.id}/set_work_periods/',
            {
                'periods': [
                    {'day_of_week': 0, 'shift_type': 'morning'}
                ]
            },
            format='json'
        )
        
        assert response.status_code in (403, 404)
    
    def test_guard_set_work_periods_invalid_day(self, authenticated_guard, guard_user, system_settings):
        """
        Invalid day_of_week value should be rejected.
        
        Expected:
        - 400 Bad Request
        """
        guard_user.guard.availability = 1
        guard_user.guard.save()
        
        response = authenticated_guard.post(
            f'/api/guards/{guard_user.guard.id}/set_work_periods/',
            {
                'periods': [
                    {'day_of_week': 7, 'shift_type': 'morning'}  # Invalid: should be 0-6
                ]
            },
            format='json'
        )
        
        assert response.status_code == 400
    
    def test_guard_set_work_periods_invalid_shift_type(
        self, authenticated_guard, guard_user, system_settings
    ):
        """
        Invalid shift_type value should be rejected.
        
        Expected:
        - 400 Bad Request
        """
        guard_user.guard.availability = 1
        guard_user.guard.save()
        
        response = authenticated_guard.post(
            f'/api/guards/{guard_user.guard.id}/set_work_periods/',
            {
                'periods': [
                    {'day_of_week': 0, 'shift_type': 'evening'}  # Invalid: should be morning/afternoon
                ]
            },
            format='json'
        )
        
        assert response.status_code == 400
    
    def test_guard_set_work_periods_empty_array(self, authenticated_guard, guard_user, system_settings):
        """
        Empty periods array should be rejected.
        
        Expected:
        - 400 Bad Request
        """
        guard_user.guard.availability = 1
        guard_user.guard.save()
        
        response = authenticated_guard.post(
            f'/api/guards/{guard_user.guard.id}/set_work_periods/',
            {
                'periods': []
            },
            format='json'
        )
        
        assert response.status_code == 400
    
    def test_guard_set_work_periods_without_authentication_fails(self, api_client, guard_user):
        """
        Setting work periods without authentication fails.
        
        Expected:
        - 401 or 403 response
        """
        response = api_client.post(
            f'/api/guards/{guard_user.guard.id}/set_work_periods/',
            {
                'periods': [
                    {'day_of_week': 0, 'shift_type': 'morning'}
                ]
            },
            format='json'
        )
        
        assert response.status_code in (401, 403)
