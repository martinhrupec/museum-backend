"""
Integration tests for admin using position_swap_request all_active endpoint.

Tests admin-specific functionality:
- Admin can view all active swap requests (pending, not expired)
- Filters out cancelled/expired requests
"""
import pytest


@pytest.mark.django_db
class TestAdminPositionSwapRequestAllActive:
    """Integration tests for admin using GET /api/position-swap-requests/all_active/"""
    
    def test_admin_can_get_all_active_swap_requests_empty(self, authenticated_admin):
        """
        Admin gets empty list when no active swap requests exist.
        
        Expected:
        - 200 OK response
        - Empty list
        """
        response = authenticated_admin.get('/api/position-swap-requests/all_active/')
        
        assert response.status_code == 200
        assert isinstance(response.data, list)
        assert len(response.data) == 0
    
    def test_admin_can_get_all_active_swap_requests_with_data(
        self,
        authenticated_admin,
        guard_user,
        assigned_position
    ):
        """
        Admin gets list of active swap requests.
        
        Expected:
        - 200 OK response
        - List contains only pending requests
        """
        from api.api_models import PositionSwapRequest
        from django.utils import timezone
        from datetime import timedelta
        
        position, _ = assigned_position
        
        # Create active swap request
        swap = PositionSwapRequest.objects.create(
            requesting_guard=guard_user.guard,
            position_to_swap=position,
            status='pending',
            expires_at=timezone.now() + timedelta(days=1)
        )
        
        response = authenticated_admin.get('/api/position-swap-requests/all_active/')
        
        assert response.status_code == 200
        assert isinstance(response.data, list)
        assert len(response.data) >= 1
        assert any(s['id'] == swap.id for s in response.data)
    
    def test_all_active_excludes_cancelled_requests(
        self,
        authenticated_admin,
        guard_user,
        assigned_position
    ):
        """
        Admin does not see cancelled swap requests in all_active.
        
        Expected:
        - 200 OK response
        - Cancelled requests excluded
        """
        from api.api_models import PositionSwapRequest
        from django.utils import timezone
        from datetime import timedelta
        
        position, _ = assigned_position
        
        # Create pending and cancelled requests
        pending_swap = PositionSwapRequest.objects.create(
            requesting_guard=guard_user.guard,
            position_to_swap=position,
            status='pending',
            expires_at=timezone.now() + timedelta(days=1)
        )
        cancelled_swap = PositionSwapRequest.objects.create(
            requesting_guard=guard_user.guard,
            position_to_swap=position,
            status='cancelled',
            expires_at=timezone.now() + timedelta(days=1)
        )
        
        response = authenticated_admin.get('/api/position-swap-requests/all_active/')
        
        assert response.status_code == 200
        # Should contain pending but not cancelled
        swap_ids = [s['id'] for s in response.data]
        assert pending_swap.id in swap_ids
        assert cancelled_swap.id not in swap_ids
    
    def test_all_active_swap_requests_without_admin_fails(self, api_client):
        """
        Non-admin cannot access all_active swap requests.
        
        Expected:
        - 401 or 403 response
        """
        response = api_client.get('/api/position-swap-requests/all_active/')
        
        assert response.status_code in (401, 403)
