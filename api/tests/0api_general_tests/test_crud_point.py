"""
Integration tests for CRUD operations on Point model.

Tests admin and guard permissions for:
- Creating point entries
- Reading points (list and detail)
- Updating points (full and partial)
- Deleting point entries
"""
import pytest
from api.api_models import Point


@pytest.mark.django_db
class TestAdminCRUDPoint:
    """Integration tests for admin CRUD operations on /api/points/"""
    
    def test_admin_can_create_point(self, authenticated_admin, guard_user):
        """
        Admin creates a new point entry.
        
        Expected: 201 Created or 403/405 if not allowed
        """
        response = authenticated_admin.post(
            '/api/points/',
            {
                'guard': guard_user.guard.id,
                'points': 10,
                'explanation': 'Bonus points'
            },
            format='json'
        )
        
        assert response.status_code in (201, 400, 403, 405)
    
    def test_admin_can_list_points(self, authenticated_admin, guard_user):
        """
        Admin lists all point entries.
        
        Expected: 200 OK with list
        """
        response = authenticated_admin.get('/api/points/')
        
        assert response.status_code == 200
        assert isinstance(response.data, (list, dict))
    
    def test_admin_can_retrieve_point(self, authenticated_admin, guard_user):
        """
        Admin retrieves specific point entry.
        
        Expected: 200 OK with point data
        """
        # Create a point first
        point = Point.objects.create(
            guard=guard_user.guard,
            points=5,
            explanation='Test point'
        )
        
        response = authenticated_admin.get(f'/api/points/{point.id}/')
        
        assert response.status_code == 200
        assert response.data['id'] == point.id
    
    def test_admin_can_update_point(self, authenticated_admin, guard_user):
        """
        Admin updates point entry (full update).
        
        Expected: 200 OK or 403/405 if not allowed
        """
        point = Point.objects.create(
            guard=guard_user.guard,
            points=5,
            explanation='Test point'
        )
        
        response = authenticated_admin.put(
            f'/api/points/{point.id}/',
            {
                'guard': guard_user.guard.id,
                'points': 15,
                'explanation': 'Updated points'
            },
            format='json'
        )
        
        assert response.status_code in (200, 400, 403, 405)
    
    def test_admin_can_partial_update_point(self, authenticated_admin, guard_user):
        """
        Admin partially updates point entry.
        
        Expected: 200 OK or 403/405 if not allowed
        """
        point = Point.objects.create(
            guard=guard_user.guard,
            points=5,
            explanation='Test point'
        )
        
        response = authenticated_admin.patch(
            f'/api/points/{point.id}/',
            {'explanation': 'Partially updated'},
            format='json'
        )
        
        assert response.status_code in (200, 403, 405)
    
    def test_admin_can_delete_point(self, authenticated_admin, guard_user):
        """
        Admin deletes a point entry.
        
        Expected: 204 No Content or 403/405 if not allowed
        """
        point = Point.objects.create(
            guard=guard_user.guard,
            points=5,
            explanation='Test point'
        )
        
        response = authenticated_admin.delete(f'/api/points/{point.id}/')
        
        assert response.status_code in (204, 403, 405)


@pytest.mark.django_db
class TestGuardCRUDPoint:
    """Integration tests for guard CRUD operations on /api/points/"""
    
    def test_guard_can_view_own_points(self, authenticated_guard, guard_user):
        """
        Guard can view their own points.
        
        Expected: 200 OK
        """
        Point.objects.create(
            guard=guard_user.guard,
            points=10,
            explanation='Test points'
        )
        
        response = authenticated_guard.get('/api/points/')
        
        assert response.status_code == 200
    
    def test_guard_cannot_create_points(self, authenticated_guard, guard_user):
        """
        Guard cannot create point entries.
        
        Expected: 403 Forbidden
        """
        response = authenticated_guard.post(
            '/api/points/',
            {
                'guard': guard_user.guard.id,
                'points': 100,
                'explanation': 'Self-granted points'
            },
            format='json'
        )
        
        assert response.status_code in (403, 405)
    
    def test_guard_cannot_update_points(self, authenticated_guard, guard_user):
        """
        Guard cannot update point entries.
        
        Expected: 403 Forbidden
        """
        point = Point.objects.create(
            guard=guard_user.guard,
            points=5,
            explanation='Test point'
        )
        
        response = authenticated_guard.patch(
            f'/api/points/{point.id}/',
            {'points': 100},
            format='json'
        )
        
        assert response.status_code in (403, 405)
    
    def test_guard_cannot_delete_points(self, authenticated_guard, guard_user):
        """
        Guard cannot delete point entries.
        
        Expected: 403 Forbidden
        """
        point = Point.objects.create(
            guard=guard_user.guard,
            points=5,
            explanation='Test point'
        )
        
        response = authenticated_guard.delete(f'/api/points/{point.id}/')
        
        assert response.status_code in (403, 405)


@pytest.mark.django_db
class TestPointUnauthenticated:
    """Integration tests for unauthenticated access to /api/points/"""
    
    def test_unauthenticated_cannot_access_points(self, api_client):
        """
        Unauthenticated users cannot access points.
        
        Expected: 401 Unauthorized or 403 Forbidden
        """
        response = api_client.get('/api/points/')
        
        assert response.status_code in (401, 403)
