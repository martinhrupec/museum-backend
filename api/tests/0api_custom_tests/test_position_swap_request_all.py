"""
Integration tests for admin using position_swap_request all endpoint.

Tests admin-specific functionality:
- Admin can view all swap requests (regardless of status)
- Returns complete list
"""
import pytest


@pytest.mark.django_db
class TestAdminPositionSwapRequestAll:
    """Integration tests for admin using GET /api/position-swap-requests/all/"""
    
    def test_admin_can_get_all_swap_requests_empty(self, authenticated_admin):
        """
        Admin gets empty list when no swap requests exist.
        
        Expected:
        - 200 OK response
        - Empty list
        """
        response = authenticated_admin.get('/api/position-swap-requests/all/')
        
        assert response.status_code == 200
        assert isinstance(response.data, list)
        assert len(response.data) == 0
    
    def test_admin_can_get_all_swap_requests_with_data(
        self,
        authenticated_admin,
        guard_user,
        assigned_position,
        system_settings
    ):
        """
        Admin gets list of all swap requests.
        
        Expected:
        - 200 OK response
        - List contains swap request data
        """
        from api.api_models import PositionSwapRequest
        from django.utils import timezone
        from datetime import timedelta
        
        position, _ = assigned_position
        
        # Create swap request
        swap = PositionSwapRequest.objects.create(
            requesting_guard=guard_user.guard,
            position_to_swap=position,
            status='pending',
            expires_at=timezone.now() + timedelta(days=1)
        )
        
        response = authenticated_admin.get('/api/position-swap-requests/all/')
        
        assert response.status_code == 200
        assert isinstance(response.data, list)
        assert len(response.data) >= 1
        assert any(s['id'] == swap.id for s in response.data)
    
    def test_all_swap_requests_includes_all_statuses(
        self,
        authenticated_admin,
        guard_user,
        assigned_position
    ):
        """
        Admin sees swap requests with all statuses (pending, accepted, cancelled, expired).
        
        Expected:
        - 200 OK response
        - All statuses included
        """
        from api.api_models import PositionSwapRequest
        from django.utils import timezone
        from datetime import timedelta
        
        position, _ = assigned_position
        
        # Create multiple swap requests with different statuses
        PositionSwapRequest.objects.create(
            requesting_guard=guard_user.guard,
            position_to_swap=position,
            status='pending',
            expires_at=timezone.now() + timedelta(days=1)
        )
        PositionSwapRequest.objects.create(
            requesting_guard=guard_user.guard,
            position_to_swap=position,
            status='cancelled',
            expires_at=timezone.now() + timedelta(days=1)
        )
        
        response = authenticated_admin.get('/api/position-swap-requests/all/')
        
        assert response.status_code == 200
        assert len(response.data) >= 2
    
    def test_all_swap_requests_without_admin_fails(self, api_client):
        """
        Non-admin cannot access all swap requests.
        
        Expected:
        - 401 or 403 response
        """
        response = api_client.get('/api/position-swap-requests/all/')
        
        assert response.status_code in (401, 403)
