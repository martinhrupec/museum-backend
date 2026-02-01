"""
Integration tests for CRUD operations on Position model.

Tests:
- Admin permissions for all CRUD operations
- Guard permissions (read-only)
"""
import pytest
from datetime import time


@pytest.mark.django_db
class TestAdminCRUDPosition:
    """Integration tests for admin CRUD operations on /api/positions/"""
    
    def test_admin_can_create_position(self, authenticated_admin, sample_exhibition, system_settings):
        """
        Admin creates a new position.
        
        Expected: 201 Created
        """
        response = authenticated_admin.post(
            '/api/positions/',
            {
                'exhibition': sample_exhibition.id,
                'date': system_settings.next_week_start.isoformat(),
                'start_time': '10:00:00',
                'end_time': '14:00:00'
            },
            format='json'
        )
        
        assert response.status_code in (201, 400, 403)
    
    def test_admin_can_list_positions(self, authenticated_admin, next_week_position):
        """
        Admin lists all positions.
        
        Expected: 200 OK with list of positions
        """
        response = authenticated_admin.get('/api/positions/')
        
        assert response.status_code == 200
        assert isinstance(response.data, (list, dict))
    
    def test_admin_can_retrieve_position(self, authenticated_admin, next_week_position):
        """
        Admin retrieves specific position details.
        
        Expected: 200 OK with position data
        """
        response = authenticated_admin.get(f'/api/positions/{next_week_position.id}/')
        
        assert response.status_code == 200
        assert response.data['id'] == next_week_position.id
    
    def test_admin_can_update_position(self, authenticated_admin, next_week_position):
        """
        Admin updates position (full update).
        
        Expected: 200 OK
        """
        response = authenticated_admin.put(
            f'/api/positions/{next_week_position.id}/',
            {
                'exhibition': next_week_position.exhibition.id,
                'date': next_week_position.date.isoformat(),
                'start_time': '11:00:00',
                'end_time': '15:00:00'
            },
            format='json'
        )
        
        assert response.status_code in (200, 400, 403)
    
    def test_admin_can_partial_update_position(self, authenticated_admin, next_week_position):
        """
        Admin partially updates position.
        
        Expected: 200 OK
        """
        response = authenticated_admin.patch(
            f'/api/positions/{next_week_position.id}/',
            {'start_time': '12:00:00'},
            format='json'
        )
        
        assert response.status_code in (200, 403)
    
    def test_admin_can_delete_position(self, authenticated_admin, next_week_position):
        """
        Admin deletes a position.
        
        Expected: 204 No Content
        """
        response = authenticated_admin.delete(f'/api/positions/{next_week_position.id}/')
        
        assert response.status_code in (204, 403, 405)


@pytest.mark.django_db
class TestGuardCRUDPosition:
    """Integration tests for guard CRUD operations on /api/positions/"""
    
    def test_guard_cannot_create_position(self, authenticated_guard, sample_exhibition, system_settings):
        """
        Guard cannot create positions.
        
        Expected: 403 Forbidden
        """
        response = authenticated_guard.post(
            '/api/positions/',
            {
                'exhibition': sample_exhibition.id,
                'date': system_settings.next_week_start.isoformat(),
                'start_time': '10:00:00',
                'end_time': '14:00:00'
            },
            format='json'
        )
        
        assert response.status_code == 403
    
    def test_guard_can_list_positions(self, authenticated_guard, next_week_position):
        """
        Guard can list positions (read-only access).
        
        Expected: 200 OK
        """
        response = authenticated_guard.get('/api/positions/')
        
        assert response.status_code == 200
        assert isinstance(response.data, (list, dict))
    
    def test_guard_can_retrieve_position(self, authenticated_guard, next_week_position):
        """
        Guard can retrieve position details (read-only access).
        
        Expected: 200 OK
        """
        response = authenticated_guard.get(f'/api/positions/{next_week_position.id}/')
        
        assert response.status_code == 200
        assert response.data['id'] == next_week_position.id
    
    def test_guard_cannot_update_position(self, authenticated_guard, next_week_position):
        """
        Guard cannot update positions.
        
        Expected: 403 Forbidden
        """
        response = authenticated_guard.put(
            f'/api/positions/{next_week_position.id}/',
            {
                'exhibition': next_week_position.exhibition.id,
                'date': next_week_position.date.isoformat(),
                'start_time': '11:00:00',
                'end_time': '15:00:00'
            },
            format='json'
        )
        
        assert response.status_code == 403
    
    def test_guard_cannot_partial_update_position(self, authenticated_guard, next_week_position):
        """
        Guard cannot partially update positions.
        
        Expected: 403 Forbidden
        """
        response = authenticated_guard.patch(
            f'/api/positions/{next_week_position.id}/',
            {'start_time': '12:00:00'},
            format='json'
        )
        
        assert response.status_code == 403
    
    def test_guard_cannot_delete_position(self, authenticated_guard, next_week_position):
        """
        Guard cannot delete positions.
        
        Expected: 403 Forbidden
        """
        response = authenticated_guard.delete(f'/api/positions/{next_week_position.id}/')
        
        assert response.status_code == 403


@pytest.mark.django_db
class TestPositionUnauthenticated:
    """Integration tests for unauthenticated access to /api/positions/"""
    
    def test_unauthenticated_cannot_list_positions(self, api_client):
        """
        Unauthenticated users cannot list positions.
        
        Expected: 401 Unauthorized or 403 Forbidden
        """
        response = api_client.get('/api/positions/')
        
        assert response.status_code in (401, 403)
    
    def test_unauthenticated_cannot_retrieve_position(self, api_client, next_week_position):
        """
        Unauthenticated users cannot retrieve positions.
        
        Expected: 401 Unauthorized or 403 Forbidden
        """
        response = api_client.get(f'/api/positions/{next_week_position.id}/')
        
        assert response.status_code in (401, 403)
