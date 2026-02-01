"""
Integration tests for admin using system_settings current endpoint.

Tests admin-specific functionality:
- Admin can get current system settings
- Returns settings object
"""
import pytest


@pytest.mark.django_db
class TestAdminSystemSettingsCurrent:
    """Integration tests for admin using GET /api/system-settings/current/"""
    
    def test_admin_can_get_current_system_settings(self, authenticated_admin, system_settings):
        """
        Admin gets current system settings.
        
        Expected:
        - 200 OK response
        - Settings object with expected fields
        """
        response = authenticated_admin.get('/api/system-settings/current/')
        
        assert response.status_code == 200
        assert 'id' in response.data
        assert 'workdays' in response.data
        assert 'minimal_number_of_positions_in_week' in response.data
    
    def test_current_system_settings_contains_required_fields(self, authenticated_admin, system_settings):
        """
        Current system settings contain all expected fields.
        
        Expected:
        - All critical settings fields present
        """
        response = authenticated_admin.get('/api/system-settings/current/')
        
        assert response.status_code == 200
        expected_fields = [
            'workdays',
            'minimal_number_of_positions_in_week',
            'this_week_start',
            'this_week_end',
            'next_week_start',
            'next_week_end'
        ]
        for field in expected_fields:
            assert field in response.data
    
    def test_current_system_settings_without_authentication_fails(self, api_client):
        """
        Getting system settings without authentication fails.
        
        Expected:
        - 401 or 403 response
        """
        response = api_client.get('/api/system-settings/current/')
        
        assert response.status_code in (401, 403)
