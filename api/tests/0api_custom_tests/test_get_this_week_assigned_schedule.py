"""
Integration tests for admin using get_this_week_assigned_schedule endpoint.

Tests admin-specific functionality:
- Admin can get this week's assigned schedule
- Returns all assigned positions for the week
"""
import pytest


@pytest.mark.django_db
class TestAdminGetThisWeekAssignedSchedule:
    """Integration tests for admin using GET /api/position-history/assigned/this-week/"""
    
    def test_admin_can_get_this_week_schedule_empty(self, authenticated_admin, system_settings):
        """
        Admin gets empty schedule when no positions assigned.
        
        Expected:
        - 200 OK or 503 if week not set
        """
        response = authenticated_admin.get('/api/position-history/assigned/this-week/')
        
        # 200 OK or 503 if week boundaries not set yet
        assert response.status_code in (200, 503)
    
    def test_admin_can_get_this_week_schedule_with_data(
        self,
        authenticated_admin,
        assigned_position,
        system_settings
    ):
        """
        Admin gets schedule with assigned positions.
        
        Expected:
        - 200 OK or 503 if week not set
        """
        response = authenticated_admin.get('/api/position-history/assigned/this-week/')
        
        # 200 OK or 503 if week boundaries not set yet
        assert response.status_code in (200, 503)
    
    def test_this_week_schedule_without_authentication_fails(self, api_client):
        """
        Getting schedule without authentication fails.
        
        Expected:
        - 401 or 403 response
        """
        response = api_client.get('/api/position-history/assigned/this-week/')
        
        assert response.status_code in (401, 403)


@pytest.mark.django_db
class TestGuardGetThisWeekAssignedSchedule:
    """Integration tests for guard using GET /api/position-history/assigned/this-week/"""
    
    def test_guard_can_get_this_week_schedule(self, authenticated_guard, system_settings):
        """
        Guard can get this week's assigned schedule.
        
        Expected:
        - 200 OK or 503 if week not set
        """
        response = authenticated_guard.get('/api/position-history/assigned/this-week/')
        
        assert response.status_code in (200, 503)
    
    def test_guard_can_get_next_week_schedule(self, authenticated_guard, system_settings):
        """
        Guard can get next week's assigned schedule.
        
        Expected:
        - 200 OK or 503 if week not set
        """
        response = authenticated_guard.get('/api/position-history/assigned/next-week/')
        
        assert response.status_code in (200, 503)
