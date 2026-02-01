"""
Integration tests for my_work_history endpoint.

Tests:
- Guard can access their own work history
- Admin CANNOT access this endpoint (guard-only)
- Validation rules
"""
import pytest
from django.utils import timezone
from datetime import time, timedelta


@pytest.mark.django_db
class TestAdminMyWorkHistory:
    """Integration tests verifying admin CANNOT use GET /api/position-history/my-work-history/"""
    
    def test_admin_cannot_access_my_work_history(self, authenticated_admin):
        """
        Admin attempting to access my_work_history should be rejected.
        
        This is a guard-only endpoint.
        
        Expected:
        - 400 Bad Request (no guard profile)
        """
        response = authenticated_admin.get('/api/position-history/my-work-history/?year=2026')
        
        assert response.status_code == 400
        assert 'guard' in str(response.data).lower()


@pytest.mark.django_db
class TestGuardMyWorkHistory:
    """Integration tests for guard using GET /api/position-history/my-work-history/"""
    
    def test_guard_can_access_own_work_history(
        self,
        authenticated_guard,
        guard_user,
        sample_exhibition,
        system_settings
    ):
        """
        Guard successfully retrieves their work history.
        
        Expected:
        - 200 response
        - Contains work history data
        """
        from api.api_models import Position, PositionHistory
        
        # Create and assign a position in the past
        past_date = timezone.now().date() - timedelta(days=7)
        position = Position.objects.create(
            exhibition=sample_exhibition,
            date=past_date,
            start_time=time(9, 0),
            end_time=time(14, 0)
        )
        
        PositionHistory.objects.create(
            position=position,
            guard=guard_user.guard,
            action=PositionHistory.Action.ASSIGNED
        )
        
        response = authenticated_guard.get(
            f'/api/position-history/my-work-history/?year={past_date.year}&month={past_date.month}'
        )
        
        assert response.status_code == 200
    
    def test_guard_must_provide_year_parameter(self, authenticated_guard):
        """
        Year parameter is required.
        
        Expected:
        - 400 Bad Request
        """
        response = authenticated_guard.get('/api/position-history/my-work-history/')
        
        assert response.status_code == 400
        assert 'year' in str(response.data).lower()
    
    def test_guard_work_history_invalid_year(self, authenticated_guard):
        """
        Invalid year should be rejected.
        
        Expected:
        - 400 Bad Request
        """
        response = authenticated_guard.get('/api/position-history/my-work-history/?year=invalid')
        
        assert response.status_code == 400
    
    def test_guard_work_history_invalid_month(self, authenticated_guard):
        """
        Invalid month should be rejected.
        
        Expected:
        - 400 Bad Request
        """
        response = authenticated_guard.get('/api/position-history/my-work-history/?year=2026&month=13')
        
        assert response.status_code == 400
    
    def test_guard_work_history_for_full_year(
        self,
        authenticated_guard,
        guard_user
    ):
        """
        Guard can retrieve work history for entire year.
        
        Expected:
        - 200 response
        """
        response = authenticated_guard.get('/api/position-history/my-work-history/?year=2026')
        
        assert response.status_code == 200
    
    def test_my_work_history_without_authentication_fails(self, api_client):
        """
        Accessing work history without authentication fails.
        
        Expected:
        - 401 or 403 response
        """
        response = api_client.get('/api/position-history/my-work-history/?year=2026')
        
        assert response.status_code in (401, 403)
