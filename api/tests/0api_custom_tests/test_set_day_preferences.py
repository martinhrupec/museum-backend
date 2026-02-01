"""
Integration tests for set_day_preferences endpoint.

Tests:
- Guard can set their own day preferences
- Admin CANNOT set guard preferences (guard-only)
- Validation rules for day preferences
"""
import pytest
from api.api_models import GuardDayPreference, Position


@pytest.mark.django_db
class TestAdminSetDayPreferences:
    """Integration tests verifying admin CANNOT use POST /api/guards/{id}/set_day_preferences/"""
    
    def test_admin_cannot_set_guard_day_preferences(
        self, authenticated_admin, guard_user, system_settings, mock_config_window_open
    ):
        """
        Admin attempting to set guard day preferences should be rejected.
        
        This is a guard-only endpoint - admins cannot modify guard preferences.
        
        Expected:
        - 403 Forbidden
        """
        response = authenticated_admin.post(
            f'/api/guards/{guard_user.guard.id}/set_day_preferences/',
            {
                'day_of_week_list': [0, 1, 2, 3, 4]
            },
            format='json'
        )
        
        assert response.status_code == 403
        assert 'admin' in str(response.data).lower() or 'čuvar' in str(response.data).lower()


@pytest.mark.django_db
class TestGuardSetDayPreferences:
    """Integration tests for guard using POST /api/guards/{id}/set_day_preferences/"""
    
    def test_guard_can_set_own_day_preferences(
        self, authenticated_guard, guard_user, sample_exhibition, system_settings, mock_config_window_open
    ):
        """
        Guard successfully sets their own day preferences.
        
        Expected:
        - 200 response
        - Preferences created in database
        
        Prerequisites:
        - Guard must have work periods set (new validation requirement)
        - Configuration window must be open
        """
        from datetime import time, timedelta
        from api.api_models import GuardWorkPeriod
        
        # Create positions for multiple days in next_week
        for i in range(5):  # Monday to Friday
            Position.objects.create(
                exhibition=sample_exhibition,
                date=system_settings.next_week_start + timedelta(days=i),
                start_time=time(9, 0),
                end_time=time(14, 0)
            )
        
        # PREREQUISITE: Set work periods for the guard (new requirement)
        for day in range(5):  # Mon-Fri (0-4)
            GuardWorkPeriod.objects.create(
                guard=guard_user.guard,
                day_of_week=day,
                shift_type='morning',
                is_template=True
            )
        
        # Guard must have availability set
        guard_user.guard.availability = 5
        guard_user.guard.save()
        
        # Get actual workdays from guard's work periods
        expected_days = [0, 1, 2, 3, 4]  # Mon-Fri
        
        response = authenticated_guard.post(
            f'/api/guards/{guard_user.guard.id}/set_day_preferences/',
            {
                'day_of_week_list': expected_days
            },
            format='json'
        )
        
        assert response.status_code == 200
        assert 'message' in response.data
    
    def test_guard_can_save_day_preferences_as_template(
        self, authenticated_guard, guard_user, sample_exhibition, system_settings, mock_config_window_open
    ):
        """
        Guard can save day preferences as template for future weeks.
        
        Expected:
        - 200 response
        - is_template=True on created preference
        """
        from datetime import time, timedelta
        from api.api_models import GuardWorkPeriod
        
        # Create positions for next_week
        for i in range(5):
            Position.objects.create(
                exhibition=sample_exhibition,
                date=system_settings.next_week_start + timedelta(days=i),
                start_time=time(9, 0),
                end_time=time(14, 0)
            )
        
        # PREREQUISITE: Set work periods for the guard (new requirement)
        for day in range(5):
            GuardWorkPeriod.objects.create(
                guard=guard_user.guard,
                day_of_week=day,
                shift_type='morning',
                is_template=True
            )
        guard_user.guard.availability = 5
        guard_user.guard.save()
        
        response = authenticated_guard.post(
            f'/api/guards/{guard_user.guard.id}/set_day_preferences/',
            {
                'day_of_week_list': [0, 1, 2, 3, 4],
                'save_as_template': True
            },
            format='json'
        )
        
        assert response.status_code == 200
        
        # Verify template flag
        pref = GuardDayPreference.objects.filter(guard=guard_user.guard, is_template=True)
        assert pref.exists()
    
    def test_guard_can_clear_day_preferences(
        self, authenticated_guard, guard_user, system_settings, mock_config_window_open
    ):
        """
        Guard can clear preferences by sending empty array.
        
        Expected:
        - 200 response
        """
        response = authenticated_guard.post(
            f'/api/guards/{guard_user.guard.id}/set_day_preferences/',
            {
                'day_of_week_list': []
            },
            format='json'
        )
        
        assert response.status_code == 200
        assert 'clear' in str(response.data).lower() or response.data.get('preference') is None
    
    def test_guard_cannot_set_other_guards_day_preferences(
        self, authenticated_guard, second_guard_user, system_settings, mock_config_window_open
    ):
        """
        Guard cannot set another guard's day preferences.
        
        Expected:
        - 403 Forbidden or 404 Not Found
        """
        response = authenticated_guard.post(
            f'/api/guards/{second_guard_user.guard.id}/set_day_preferences/',
            {
                'day_of_week_list': [0, 1, 2]
            },
            format='json'
        )
        
        assert response.status_code in (403, 404)
    
    def test_guard_set_day_preferences_invalid_type(
        self, authenticated_guard, guard_user, system_settings, mock_config_window_open
    ):
        """
        day_of_week_list must be an array.
        
        Expected:
        - 400 Bad Request
        """
        response = authenticated_guard.post(
            f'/api/guards/{guard_user.guard.id}/set_day_preferences/',
            {
                'day_of_week_list': 'not an array'
            },
            format='json'
        )
        
        assert response.status_code == 400
    
    def test_guard_set_day_preferences_without_authentication_fails(self, api_client, guard_user):
        """
        Setting day preferences without authentication fails.
        
        Expected:
        - 401 or 403 response
        """
        response = api_client.post(
            f'/api/guards/{guard_user.guard.id}/set_day_preferences/',
            {
                'day_of_week_list': [0, 1]
            },
            format='json'
        )
        
        assert response.status_code in (401, 403)
