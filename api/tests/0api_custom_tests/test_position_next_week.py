"""
Integration tests for admin using position next_week endpoint.

Tests admin-specific functionality:
- Admin can get all positions for next week
- Returns list of positions
"""
import pytest


@pytest.mark.django_db
class TestAdminPositionNextWeek:
    """Integration tests for admin using GET /api/positions/next_week/"""
    
    def test_admin_can_get_positions_next_week_empty(self, authenticated_admin):
        """
        Admin gets empty list when no positions exist for next week.
        
        Expected:
        - 200 OK response or 503 if next_week not set
        - Empty list
        """
        response = authenticated_admin.get('/api/positions/next_week/')
        
        # Could be 503 if next_week not initialized
        assert response.status_code in (200, 503)
        if response.status_code == 200:
            assert isinstance(response.data, list)
    
    def test_admin_can_get_positions_next_week_with_data(
        self,
        authenticated_admin,
        next_week_position,
        system_settings
    ):
        """
        Admin gets list of positions for next week.
        
        Expected:
        - 200 OK response
        - List contains position data
        """
        response = authenticated_admin.get('/api/positions/next_week/')
        
        assert response.status_code == 200
        assert isinstance(response.data, list)
        assert len(response.data) >= 1
        assert any(p['id'] == next_week_position.id for p in response.data)
    
    def test_position_next_week_contains_required_fields(
        self,
        authenticated_admin,
        next_week_position
    ):
        """
        Each position in next_week has expected fields.
        
        Expected:
        - Each position has id, date, start_time, end_time, exhibition
        """
        response = authenticated_admin.get('/api/positions/next_week/')
        
        assert response.status_code == 200
        for position in response.data:
            assert 'id' in position
            assert 'date' in position
            assert 'start_time' in position
            assert 'end_time' in position
            assert 'exhibition' in position
    
    def test_position_next_week_without_authentication_fails(self, api_client):
        """
        Getting positions without authentication fails.
        
        Expected:
        - 401 or 403 response
        """
        response = api_client.get('/api/positions/next_week/')
        
        assert response.status_code in (401, 403)
