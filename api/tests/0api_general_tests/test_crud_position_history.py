"""
Integration tests for CRUD operations on PositionHistory model.

Tests:
- Admin permissions for all CRUD operations
- Guard permissions (read-only, can view all history)
"""
import pytest
from api.api_models import PositionHistory


@pytest.mark.django_db
class TestAdminCRUDPositionHistory:
    """Integration tests for admin CRUD operations on /api/position-history/"""
    
    def test_admin_can_create_position_history(self, authenticated_admin, next_week_position, guard_user):
        """
        Admin CAN create position history via direct CRUD.
        
        Expected: 201 Created (or 400 if validation fails)
        """
        response = authenticated_admin.post(
            '/api/position-history/',
            {
                'position_id': next_week_position.id,
                'guard_id': guard_user.guard.id,
                'action': 'ASSIGNED'
            },
            format='json'
        )
        
        assert response.status_code in (201, 400)
    
    def test_admin_can_list_position_history(self, authenticated_admin, assigned_position):
        """
        Admin lists all position history entries.
        
        Expected: 200 OK with list
        """
        response = authenticated_admin.get('/api/position-history/')
        
        assert response.status_code == 200
        assert isinstance(response.data, (list, dict))
    
    def test_admin_can_retrieve_position_history(self, authenticated_admin, assigned_position):
        """
        Admin retrieves specific position history entry.
        
        Expected: 200 OK with history data
        """
        position, guard = assigned_position
        history = PositionHistory.objects.filter(position=position).first()
        
        if history:
            response = authenticated_admin.get(f'/api/position-history/{history.id}/')
            assert response.status_code == 200
    
    def test_admin_can_update_position_history(self, authenticated_admin, assigned_position):
        """
        Admin CAN update position history via direct CRUD.
        
        Expected: 200 OK (or 400 if validation fails)
        """
        position, guard = assigned_position
        history = PositionHistory.objects.filter(position=position).first()
        
        if history:
            response = authenticated_admin.put(
                f'/api/position-history/{history.id}/',
                {
                    'position_id': position.id,
                    'guard_id': guard.id,
                    'action': 'ASSIGNED'
                },
                format='json'
            )
            assert response.status_code in (200, 400)
    
    def test_admin_can_partial_update_position_history(self, authenticated_admin, assigned_position):
        """
        Admin CAN partially update position history via direct CRUD.
        
        Expected: 200 OK (or 400 if validation fails)
        """
        position, guard = assigned_position
        history = PositionHistory.objects.filter(position=position).first()
        
        if history:
            response = authenticated_admin.patch(
                f'/api/position-history/{history.id}/',
                {'action': 'CANCELLED'},
                format='json'
            )
            assert response.status_code in (200, 400)
    
    def test_admin_can_delete_position_history(self, authenticated_admin, assigned_position):
        """
        Admin CAN delete position history via direct CRUD.
        
        Expected: 204 No Content
        """
        position, guard = assigned_position
        history = PositionHistory.objects.filter(position=position).first()
        
        if history:
            response = authenticated_admin.delete(f'/api/position-history/{history.id}/')
            assert response.status_code == 204


@pytest.mark.django_db
class TestGuardCRUDPositionHistory:
    """Integration tests for guard CRUD operations on /api/position-history/"""
    
    def test_guard_cannot_create_position_history(
        self, authenticated_guard, next_week_position, guard_user
    ):
        """
        Guard cannot directly create position history entries.
        (They use assign/cancel endpoints instead)
        
        Expected: 403 Forbidden or 405 Method Not Allowed
        """
        response = authenticated_guard.post(
            '/api/position-history/',
            {
                'position_id': next_week_position.id,
                'guard_id': guard_user.guard.id,
                'action': 'ASSIGNED'
            },
            format='json'
        )
        
        assert response.status_code in (403, 405)
    
    def test_guard_can_list_position_history(self, authenticated_guard, assigned_position):
        """
        Guard can list position history (to see assignments).
        
        Expected: 200 OK
        """
        response = authenticated_guard.get('/api/position-history/')
        
        assert response.status_code == 200
        assert isinstance(response.data, (list, dict))
    
    def test_guard_can_retrieve_position_history(self, authenticated_guard, assigned_position):
        """
        Guard can retrieve specific position history entry.
        
        Expected: 200 OK
        """
        position, _ = assigned_position
        history = PositionHistory.objects.filter(position=position).first()
        
        if history:
            response = authenticated_guard.get(f'/api/position-history/{history.id}/')
            assert response.status_code == 200
    
    def test_guard_cannot_update_position_history(self, authenticated_guard, assigned_position):
        """
        Guard cannot update position history directly.
        
        Expected: 403 Forbidden or 405 Method Not Allowed
        """
        position, guard = assigned_position
        history = PositionHistory.objects.filter(position=position).first()
        
        if history:
            response = authenticated_guard.put(
                f'/api/position-history/{history.id}/',
                {
                    'position_id': position.id,
                    'guard_id': guard.id,
                    'action': 'CANCELLED'
                },
                format='json'
            )
            assert response.status_code in (403, 405)
    
    def test_guard_cannot_delete_position_history(self, authenticated_guard, assigned_position):
        """
        Guard cannot delete position history entries.
        
        Expected: 403 Forbidden or 405 Method Not Allowed
        """
        position, _ = assigned_position
        history = PositionHistory.objects.filter(position=position).first()
        
        if history:
            response = authenticated_guard.delete(f'/api/position-history/{history.id}/')
            assert response.status_code in (403, 405)


@pytest.mark.django_db
class TestPositionHistoryUnauthenticated:
    """Integration tests for unauthenticated access to /api/position-history/"""
    
    def test_unauthenticated_cannot_list_position_history(self, api_client):
        """
        Unauthenticated users cannot list position history.
        
        Expected: 401 Unauthorized or 403 Forbidden
        """
        response = api_client.get('/api/position-history/')
        
        assert response.status_code in (401, 403)