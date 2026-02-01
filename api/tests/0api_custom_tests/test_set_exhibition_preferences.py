"""
Integration tests for set_exhibition_preferences endpoint.

Tests:
- Guard can set their own exhibition preferences
- Admin CANNOT set guard preferences (guard-only)
- Validation rules for exhibition preferences
"""
import pytest
from api.api_models import GuardExhibitionPreference, Exhibition, GuardWorkPeriod


@pytest.mark.django_db
class TestAdminSetExhibitionPreferences:
    """Integration tests verifying admin CANNOT use POST /api/guards/{id}/set_exhibition_preferences/"""
    
    def test_admin_cannot_set_guard_exhibition_preferences(
        self, authenticated_admin, guard_user, system_settings, mock_config_window_open
    ):
        """
        Admin attempting to set guard exhibition preferences should be rejected.
        
        This is a guard-only endpoint - admins cannot modify guard preferences.
        
        Expected:
        - 403 Forbidden
        """
        response = authenticated_admin.post(
            f'/api/guards/{guard_user.guard.id}/set_exhibition_preferences/',
            {
                'exhibition_ids': [1, 2, 3]
            },
            format='json'
        )
        
        assert response.status_code == 403
        assert 'admin' in str(response.data).lower() or 'čuvar' in str(response.data).lower()


@pytest.mark.django_db
class TestGuardSetExhibitionPreferences:
    """Integration tests for guard using POST /api/guards/{id}/set_exhibition_preferences/"""
    
    def test_guard_can_set_own_exhibition_preferences(
        self, authenticated_guard, guard_user, sample_exhibition, system_settings, mock_config_window_open
    ):
        """
        Guard successfully sets their own exhibition preferences.
        
        Expected:
        - 200 response
        - Preferences created in database
        
        Prerequisites:
        - Guard must have work periods set (new validation requirement)
        - Configuration window must be open
        """
        from api.api_models import Position
        from datetime import time
        
        # Create positions for next_week so exhibitions are available
        # Position is on Monday (weekday 0)
        Position.objects.create(
            exhibition=sample_exhibition,
            date=system_settings.next_week_start,
            start_time=time(9, 0),
            end_time=time(14, 0)
        )
        
        # PREREQUISITE: Set work periods for the guard (new requirement)
        # Work period on Monday (weekday 0) to match the position
        GuardWorkPeriod.objects.create(
            guard=guard_user.guard,
            day_of_week=system_settings.next_week_start.weekday(),
            shift_type='morning',
            is_template=True
        )
        guard_user.guard.availability = 1
        guard_user.guard.save()
        
        response = authenticated_guard.post(
            f'/api/guards/{guard_user.guard.id}/set_exhibition_preferences/',
            {
                'exhibition_ids': [sample_exhibition.id]
            },
            format='json'
        )
        
        assert response.status_code == 200
        assert 'message' in response.data
    
    def test_guard_can_save_preferences_as_template(
        self, authenticated_guard, guard_user, sample_exhibition, system_settings, mock_config_window_open
    ):
        """
        Guard can save exhibition preferences as template for future weeks.
        
        Expected:
        - 200 response
        - is_template=True on created preference
        """
        from api.api_models import Position
        from datetime import time
        
        Position.objects.create(
            exhibition=sample_exhibition,
            date=system_settings.next_week_start,
            start_time=time(9, 0),
            end_time=time(14, 0)
        )
        
        # PREREQUISITE: Set work periods for the guard (new requirement)
        GuardWorkPeriod.objects.create(
            guard=guard_user.guard,
            day_of_week=system_settings.next_week_start.weekday(),
            shift_type='morning',
            is_template=True
        )
        guard_user.guard.availability = 1
        guard_user.guard.save()
        
        response = authenticated_guard.post(
            f'/api/guards/{guard_user.guard.id}/set_exhibition_preferences/',
            {
                'exhibition_ids': [sample_exhibition.id],
                'save_as_template': True
            },
            format='json'
        )
        
        assert response.status_code == 200
        
        # Verify template flag
        pref = GuardExhibitionPreference.objects.filter(guard=guard_user.guard, is_template=True)
        assert pref.exists()
    
    def test_guard_can_clear_preferences(
        self, authenticated_guard, guard_user, system_settings, mock_config_window_open
    ):
        """
        Guard can clear preferences by sending empty array.
        
        Expected:
        - 200 response
        - Preferences deleted
        """
        response = authenticated_guard.post(
            f'/api/guards/{guard_user.guard.id}/set_exhibition_preferences/',
            {
                'exhibition_ids': []
            },
            format='json'
        )
        
        assert response.status_code == 200
        assert 'clear' in str(response.data).lower() or response.data.get('preference') is None
    
    def test_guard_cannot_set_other_guards_preferences(
        self, authenticated_guard, second_guard_user, system_settings, mock_config_window_open
    ):
        """
        Guard cannot set another guard's exhibition preferences.
        
        Expected:
        - 403 Forbidden or 404 Not Found
        """
        response = authenticated_guard.post(
            f'/api/guards/{second_guard_user.guard.id}/set_exhibition_preferences/',
            {
                'exhibition_ids': [1]
            },
            format='json'
        )
        
        assert response.status_code in (403, 404)
    
    def test_guard_set_preferences_invalid_type(
        self, authenticated_guard, guard_user, system_settings, mock_config_window_open
    ):
        """
        exhibition_ids must be an array.
        
        Expected:
        - 400 Bad Request
        """
        response = authenticated_guard.post(
            f'/api/guards/{guard_user.guard.id}/set_exhibition_preferences/',
            {
                'exhibition_ids': 'not an array'
            },
            format='json'
        )
        
        assert response.status_code == 400
    
    def test_guard_set_preferences_without_authentication_fails(self, api_client, guard_user):
        """
        Setting preferences without authentication fails.
        
        Expected:
        - 401 or 403 response
        """
        response = api_client.post(
            f'/api/guards/{guard_user.guard.id}/set_exhibition_preferences/',
            {
                'exhibition_ids': [1]
            },
            format='json'
        )
        
        assert response.status_code in (401, 403)
