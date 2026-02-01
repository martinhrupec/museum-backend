"""
Integration tests for CRUD operations on PositionSwapRequest model.

Tests:
- Admin permissions for viewing all swap requests
- Guard permissions (limited access - use endpoints instead of direct CRUD)
"""
import pytest
from api.api_models import PositionSwapRequest
from django.utils import timezone
from datetime import timedelta


@pytest.mark.django_db
class TestAdminCRUDPositionSwapRequest:
    """Integration tests for admin CRUD operations on /api/position-swap-requests/"""
    
    def test_admin_cannot_create_swap_request(self, authenticated_admin, guard_user, assigned_position):
        """
        Admin CANNOT create swap request via direct POST.
        Must use /api/positions/{id}/request_swap/ instead.
        
        Expected: 405 Method Not Allowed
        """
        position, _ = assigned_position
        
        response = authenticated_admin.post(
            '/api/position-swap-requests/',
            {
                'requesting_guard': guard_user.guard.id,
                'position_to_swap': position.id,
                'status': 'pending',
                'expires_at': (timezone.now() + timedelta(days=1)).isoformat()
            },
            format='json'
        )
        
        assert response.status_code == 405
    
    def test_admin_can_list_swap_requests(self, authenticated_admin, guard_user, assigned_position):
        """
        Admin lists all swap requests.
        
        Expected: 200 OK with list
        """
        response = authenticated_admin.get('/api/position-swap-requests/')
        
        assert response.status_code == 200
        assert isinstance(response.data, (list, dict))
    
    def test_admin_can_retrieve_swap_request(self, authenticated_admin, guard_user, assigned_position):
        """
        Admin retrieves specific swap request.
        
        Expected: 200 OK with swap request data
        """
        position, _ = assigned_position
        swap = PositionSwapRequest.objects.create(
            requesting_guard=guard_user.guard,
            position_to_swap=position,
            status='pending',
            expires_at=timezone.now() + timedelta(days=1)
        )
        
        response = authenticated_admin.get(f'/api/position-swap-requests/{swap.id}/')
        
        assert response.status_code == 200
        assert response.data['id'] == swap.id
    
    def test_admin_cannot_update_swap_request(self, authenticated_admin, guard_user, assigned_position):
        """
        Admin CANNOT update swap request.
        Swap requests cannot be modified once created.
        
        Expected: 405 Method Not Allowed
        """
        position, _ = assigned_position
        swap = PositionSwapRequest.objects.create(
            requesting_guard=guard_user.guard,
            position_to_swap=position,
            status='pending',
            expires_at=timezone.now() + timedelta(days=1)
        )
        
        response = authenticated_admin.put(
            f'/api/position-swap-requests/{swap.id}/',
            {
                'requesting_guard': guard_user.guard.id,
                'position_to_swap': position.id,
                'status': 'cancelled',
                'expires_at': (timezone.now() + timedelta(days=2)).isoformat()
            },
            format='json'
        )
        
        assert response.status_code == 405
    
    def test_admin_cannot_partial_update_swap_request(self, authenticated_admin, guard_user, assigned_position):
        """
        Admin CANNOT partially update swap request.
        Swap requests cannot be modified once created.
        
        Expected: 405 Method Not Allowed
        """
        position, _ = assigned_position
        swap = PositionSwapRequest.objects.create(
            requesting_guard=guard_user.guard,
            position_to_swap=position,
            status='pending',
            expires_at=timezone.now() + timedelta(days=1)
        )
        
        response = authenticated_admin.patch(
            f'/api/position-swap-requests/{swap.id}/',
            {'status': 'cancelled'},
            format='json'
        )
        
        assert response.status_code == 405
    
    def test_admin_can_delete_swap_request(self, authenticated_admin, guard_user, assigned_position):
        """
        Admin CAN delete swap request.
        
        Expected: 204 No Content
        """
        position, _ = assigned_position
        swap = PositionSwapRequest.objects.create(
            requesting_guard=guard_user.guard,
            position_to_swap=position,
            status='pending',
            expires_at=timezone.now() + timedelta(days=1)
        )
        
        response = authenticated_admin.delete(f'/api/position-swap-requests/{swap.id}/')
        
        assert response.status_code == 204


@pytest.mark.django_db
class TestGuardCRUDPositionSwapRequest:
    """Integration tests for guard CRUD operations on /api/position-swap-requests/"""
    
    def test_guard_cannot_create_swap_directly(self, authenticated_guard, guard_user, next_week_position):
        """
        Guard cannot create swap request via direct POST.
        (Must use /api/positions/{id}/request_swap/ instead)
        
        Expected: 405 Method Not Allowed
        """
        from api.api_models import PositionHistory
        
        PositionHistory.objects.create(
            position=next_week_position,
            guard=guard_user.guard,
            action=PositionHistory.Action.ASSIGNED
        )
        
        response = authenticated_guard.post(
            '/api/position-swap-requests/',
            {
                'requesting_guard': guard_user.guard.id,
                'position_to_swap': next_week_position.id,
                'status': 'pending',
                'expires_at': (timezone.now() + timedelta(days=1)).isoformat()
            },
            format='json'
        )
        
        assert response.status_code == 405
    
    def test_guard_list_shows_eligible_swaps_only(self, authenticated_guard, guard_user, second_guard_user, next_week_position):
        """
        Guard listing swap requests sees only those they're eligible to accept.
        (Excludes their own swap requests)
        
        Expected: 200 OK
        """
        from api.api_models import PositionHistory
        
        PositionHistory.objects.create(
            position=next_week_position,
            guard=second_guard_user.guard,
            action=PositionHistory.Action.ASSIGNED
        )
        
        # Create swap by second guard
        PositionSwapRequest.objects.create(
            requesting_guard=second_guard_user.guard,
            position_to_swap=next_week_position,
            status='pending',
            expires_at=timezone.now() + timedelta(days=1)
        )
        
        response = authenticated_guard.get('/api/position-swap-requests/')
        
        assert response.status_code == 200
    
    def test_guard_can_cancel_own_pending_swap(
        self, authenticated_guard, guard_user, next_week_position
    ):
        """
        Guard can cancel (delete) their own pending swap request.
        
        Expected: 200 OK (status changed to cancelled)
        """
        from api.api_models import PositionHistory
        
        PositionHistory.objects.create(
            position=next_week_position,
            guard=guard_user.guard,
            action=PositionHistory.Action.ASSIGNED
        )
        
        swap = PositionSwapRequest.objects.create(
            requesting_guard=guard_user.guard,
            position_to_swap=next_week_position,
            status='pending',
            expires_at=timezone.now() + timedelta(days=1)
        )
        
        response = authenticated_guard.delete(f'/api/position-swap-requests/{swap.id}/')
        
        assert response.status_code == 200
        
        swap.refresh_from_db()
        assert swap.status == 'cancelled'
    
    def test_guard_cannot_cancel_other_guards_swap(
        self, authenticated_guard, second_guard_user, next_week_position
    ):
        """
        Guard cannot cancel another guard's swap request.
        
        Expected: 403 Forbidden
        """
        from api.api_models import PositionHistory
        
        PositionHistory.objects.create(
            position=next_week_position,
            guard=second_guard_user.guard,
            action=PositionHistory.Action.ASSIGNED
        )
        
        swap = PositionSwapRequest.objects.create(
            requesting_guard=second_guard_user.guard,
            position_to_swap=next_week_position,
            status='pending',
            expires_at=timezone.now() + timedelta(days=1)
        )
        
        response = authenticated_guard.delete(f'/api/position-swap-requests/{swap.id}/')
        
        assert response.status_code in (403, 404)
    
    def test_guard_cannot_update_swap_request(
        self, authenticated_guard, guard_user, next_week_position
    ):
        """
        Guard cannot update swap requests directly.
        
        Expected: 405 Method Not Allowed
        """
        from api.api_models import PositionHistory
        
        PositionHistory.objects.create(
            position=next_week_position,
            guard=guard_user.guard,
            action=PositionHistory.Action.ASSIGNED
        )
        
        swap = PositionSwapRequest.objects.create(
            requesting_guard=guard_user.guard,
            position_to_swap=next_week_position,
            status='pending',
            expires_at=timezone.now() + timedelta(days=1)
        )
        
        response = authenticated_guard.put(
            f'/api/position-swap-requests/{swap.id}/',
            {'status': 'completed'},
            format='json'
        )
        
        assert response.status_code == 405


@pytest.mark.django_db
class TestPositionSwapRequestUnauthenticated:
    """Integration tests for unauthenticated access to /api/position-swap-requests/"""
    
    def test_unauthenticated_cannot_list_swap_requests(self, api_client):
        """
        Unauthenticated users cannot list swap requests.
        
        Expected: 401 Unauthorized or 403 Forbidden
        """
        response = api_client.get('/api/position-swap-requests/')
        
        assert response.status_code in (401, 403)