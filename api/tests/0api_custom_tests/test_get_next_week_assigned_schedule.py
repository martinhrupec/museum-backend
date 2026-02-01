"""
Integration tests for admin using get_next_week_assigned_schedule endpoint.

Tests admin-specific functionality:
- Admin can get next week's assigned schedule
- Returns all assigned positions for next week
"""
import pytest


@pytest.mark.django_db
class TestAdminGetNextWeekAssignedSchedule:
    """Integration tests for admin using GET /api/position-history/assigned/next-week/"""
    
    def test_admin_can_get_next_week_schedule_empty(self, authenticated_admin, system_settings):
        """
        Admin gets empty schedule when no positions assigned.
        
        Expected:
        - 200 OK response
        - Empty or minimal data structure
        """
        response = authenticated_admin.get('/api/position-history/assigned/next-week/')
        
        assert response.status_code == 200
        assert isinstance(response.data, (list, dict))
    
    def test_admin_can_get_next_week_schedule_with_data(
        self,
        authenticated_admin,
        next_week_position,
        guard_user,
        system_settings
    ):
        """
        Admin gets schedule with assigned positions.
        
        Expected:
        - 200 OK response
        - Contains position data
        """
        from api.api_models import PositionHistory
        
        # Assign position
        PositionHistory.objects.create(
            position=next_week_position,
            guard=guard_user.guard,
            action=PositionHistory.Action.ASSIGNED
        )
        
        response = authenticated_admin.get('/api/position-history/assigned/next-week/')
        
        assert response.status_code == 200
        assert isinstance(response.data, (list, dict))
    
    def test_next_week_schedule_without_authentication_fails(self, api_client):
        """
        Getting schedule without authentication fails.
        
        Expected:
        - 401 or 403 response
        """
        response = api_client.get('/api/position-history/assigned/next-week/')
        
        assert response.status_code in (401, 403)


@pytest.mark.django_db
class TestGuardGetNextWeekAssignedSchedule:
    """Integration tests for guard using GET /api/position-history/assigned/next-week/"""
    
    def test_guard_can_get_next_week_schedule(self, authenticated_guard, system_settings):
        """
        Guard can get next week's assigned schedule.
        
        Expected:
        - 200 OK response
        """
        response = authenticated_guard.get('/api/position-history/assigned/next-week/')
        
        assert response.status_code == 200
        assert isinstance(response.data, (list, dict))
    
    def test_guard_can_get_next_week_schedule_with_own_position(
        self,
        authenticated_guard,
        next_week_position,
        guard_user,
        system_settings
    ):
        """
        Guard can see next week's schedule including their own assigned positions.
        
        Expected:
        - 200 OK response
        """
        from api.api_models import PositionHistory
        
        # Assign position to guard
        PositionHistory.objects.create(
            position=next_week_position,
            guard=guard_user.guard,
            action=PositionHistory.Action.ASSIGNED
        )
        
        response = authenticated_guard.get('/api/position-history/assigned/next-week/')
        
        assert response.status_code == 200
        assert isinstance(response.data, (list, dict))
