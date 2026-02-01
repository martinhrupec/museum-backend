"""
Integration tests for my_requests endpoint.

Tests:
- Guard can access their own swap requests
- Admin CANNOT access this endpoint (guard-only)
"""
import pytest
from django.utils import timezone
from datetime import timedelta


@pytest.mark.django_db
class TestAdminMyRequests:
    """Integration tests verifying admin CANNOT use GET /api/position-swap-requests/my_requests/"""
    
    def test_admin_cannot_access_my_requests(self, authenticated_admin):
        """
        Admin attempting to access my_requests should be rejected.
        
        This is a guard-only endpoint.
        
        Expected:
        - 403 Forbidden
        """
        response = authenticated_admin.get('/api/position-swap-requests/my_requests/')
        
        assert response.status_code == 403


@pytest.mark.django_db
class TestGuardMyRequests:
    """Integration tests for guard using GET /api/position-swap-requests/my_requests/"""
    
    def test_guard_can_access_own_swap_requests(
        self,
        authenticated_guard,
        guard_user,
        next_week_position
    ):
        """
        Guard successfully retrieves their own swap requests.
        
        Expected:
        - 200 response
        - Returns list of swap requests
        """
        from api.api_models import PositionSwapRequest, PositionHistory
        
        # Assign position to guard first
        PositionHistory.objects.create(
            position=next_week_position,
            guard=guard_user.guard,
            action=PositionHistory.Action.ASSIGNED
        )
        
        # Create a swap request
        PositionSwapRequest.objects.create(
            requesting_guard=guard_user.guard,
            position_to_swap=next_week_position,
            status='pending',
            expires_at=timezone.now() + timedelta(days=1)
        )
        
        response = authenticated_guard.get('/api/position-swap-requests/my_requests/')
        
        assert response.status_code == 200
        assert isinstance(response.data, list)
        assert len(response.data) >= 1
    
    def test_guard_sees_only_own_requests(
        self,
        authenticated_guard,
        guard_user,
        second_guard_user,
        next_week_position,
        next_week_afternoon_position
    ):
        """
        Guard only sees their own swap requests, not others'.
        
        Expected:
        - Only guard's own requests in response
        """
        from api.api_models import PositionSwapRequest, PositionHistory
        
        # Assign positions
        PositionHistory.objects.create(
            position=next_week_position,
            guard=guard_user.guard,
            action=PositionHistory.Action.ASSIGNED
        )
        PositionHistory.objects.create(
            position=next_week_afternoon_position,
            guard=second_guard_user.guard,
            action=PositionHistory.Action.ASSIGNED
        )
        
        # Create swap request for first guard
        PositionSwapRequest.objects.create(
            requesting_guard=guard_user.guard,
            position_to_swap=next_week_position,
            status='pending',
            expires_at=timezone.now() + timedelta(days=1)
        )
        
        # Create swap request for second guard
        PositionSwapRequest.objects.create(
            requesting_guard=second_guard_user.guard,
            position_to_swap=next_week_afternoon_position,
            status='pending',
            expires_at=timezone.now() + timedelta(days=1)
        )
        
        response = authenticated_guard.get('/api/position-swap-requests/my_requests/')
        
        assert response.status_code == 200
        # Should only see own request
        for request_data in response.data:
            assert request_data.get('requesting_guard') == guard_user.guard.id or \
                   request_data.get('requesting_guard', {}).get('id') == guard_user.guard.id
    
    def test_guard_sees_all_statuses_in_my_requests(
        self,
        authenticated_guard,
        guard_user,
        next_week_position,
        next_week_afternoon_position
    ):
        """
        Guard can see swap requests of all statuses (pending, completed, cancelled).
        
        Expected:
        - All own requests regardless of status
        """
        from api.api_models import PositionSwapRequest, PositionHistory
        
        # Assign positions
        PositionHistory.objects.create(
            position=next_week_position,
            guard=guard_user.guard,
            action=PositionHistory.Action.ASSIGNED
        )
        PositionHistory.objects.create(
            position=next_week_afternoon_position,
            guard=guard_user.guard,
            action=PositionHistory.Action.ASSIGNED
        )
        
        # Create pending request
        PositionSwapRequest.objects.create(
            requesting_guard=guard_user.guard,
            position_to_swap=next_week_position,
            status='pending',
            expires_at=timezone.now() + timedelta(days=1)
        )
        
        # Create completed request
        PositionSwapRequest.objects.create(
            requesting_guard=guard_user.guard,
            position_to_swap=next_week_afternoon_position,
            status='completed',
            expires_at=timezone.now() + timedelta(days=1)
        )
        
        response = authenticated_guard.get('/api/position-swap-requests/my_requests/')
        
        assert response.status_code == 200
        assert len(response.data) >= 2
    
    def test_my_requests_without_authentication_fails(self, api_client):
        """
        Accessing my_requests without authentication fails.
        
        Expected:
        - 401 or 403 response
        """
        response = api_client.get('/api/position-swap-requests/my_requests/')
        
        assert response.status_code in (401, 403)
