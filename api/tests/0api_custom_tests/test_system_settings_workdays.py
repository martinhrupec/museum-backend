"""
Integration tests for admin using system_settings workdays endpoint.

Tests admin-specific functionality:
- Admin can get workdays list
- Returns array of workday integers
"""
import pytest


@pytest.mark.django_db
class TestAdminSystemSettingsWorkdays:
    """Integration tests for admin using GET /api/system-settings/workdays/"""
    
    def test_admin_can_get_workdays(self, authenticated_admin, system_settings):
        """
        Admin gets workdays list.
        
        Expected:
        - 200 OK response
        - Workdays array
        """
        response = authenticated_admin.get('/api/system-settings/workdays/')
        
        assert response.status_code == 200
        assert 'workdays' in response.data
        assert isinstance(response.data['workdays'], list)
    
    def test_workdays_contains_valid_day_numbers(self, authenticated_admin, system_settings):
        """
        Workdays array contains valid day numbers (0-6).
        
        Expected:
        - Each day is integer between 0 and 6
        """
        response = authenticated_admin.get('/api/system-settings/workdays/')
        
        assert response.status_code == 200
        workdays = response.data['workdays']
        for day in workdays:
            assert isinstance(day, int)
            assert 0 <= day <= 6
    
    def test_workdays_without_authentication_fails(self, api_client):
        """
        Getting workdays without authentication fails.
        
        Expected:
        - 401 or 403 response
        """
        response = api_client.get('/api/system-settings/workdays/')
        
        assert response.status_code in (401, 403)
