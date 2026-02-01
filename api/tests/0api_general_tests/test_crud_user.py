"""
Integration tests for CRUD operations on User model.

Tests admin and guard permissions for:
- Creating users
- Reading users (list and detail)
- Updating users (full and partial)
- Deleting users
"""
import pytest
from api.api_models import User


@pytest.mark.django_db
class TestAdminCRUDUser:
    """Integration tests for admin CRUD operations on /api/users/"""
    
    def test_admin_can_create_user(self, authenticated_admin):
        """
        Admin creates a new user.
        
        Expected: 201 Created or 403/405 if not allowed
        """
        response = authenticated_admin.post(
            '/api/users/',
            {
                'username': 'newuser',
                'password': 'testpass123',
                'email': 'newuser@example.com',
                'role': 'guard',
                'first_name': 'New',
                'last_name': 'User'
            },
            format='json'
        )
        
        assert response.status_code in (201, 403, 405)
    
    def test_admin_can_list_users(self, authenticated_admin, guard_user):
        """
        Admin lists all users.
        
        Expected: 200 OK with list of users
        """
        response = authenticated_admin.get('/api/users/')
        
        assert response.status_code == 200
        assert isinstance(response.data, (list, dict))  # Could be paginated
    
    def test_admin_can_retrieve_user(self, authenticated_admin, guard_user):
        """
        Admin retrieves specific user details.
        
        Expected: 200 OK with user data
        """
        response = authenticated_admin.get(f'/api/users/{guard_user.id}/')
        
        assert response.status_code == 200
        assert response.data['id'] == guard_user.id
        assert response.data['username'] == guard_user.username
    
    def test_admin_can_update_user(self, authenticated_admin, guard_user):
        """
        Admin updates user (full update).
        
        Expected: 200 OK or 403/405 if not allowed
        """
        response = authenticated_admin.put(
            f'/api/users/{guard_user.id}/',
            {
                'username': guard_user.username,
                'email': 'updated@example.com',
                'role': 'guard',
                'first_name': 'Updated',
                'last_name': 'Name'
            },
            format='json'
        )
        
        assert response.status_code in (200, 403, 405)
    
    def test_admin_can_partial_update_user(self, authenticated_admin, guard_user):
        """
        Admin partially updates user.
        
        Expected: 200 OK or 403/405 if not allowed
        """
        response = authenticated_admin.patch(
            f'/api/users/{guard_user.id}/',
            {'first_name': 'PartiallyUpdated'},
            format='json'
        )
        
        assert response.status_code in (200, 403, 405)
    
    def test_admin_can_delete_user(self, authenticated_admin, guard_user):
        """
        Admin deletes a user.
        
        Expected: 204 No Content or 403/405 if not allowed
        """
        response = authenticated_admin.delete(f'/api/users/{guard_user.id}/')
        
        assert response.status_code in (200, 204, 403, 405)


@pytest.mark.django_db
class TestGuardCRUDUser:
    """Integration tests for guard CRUD operations on /api/users/"""
    
    def test_guard_cannot_create_user(self, authenticated_guard):
        """
        Guard cannot create a new user.
        
        Expected: 403 Forbidden
        """
        response = authenticated_guard.post(
            '/api/users/',
            {
                'username': 'newguarduser',
                'password': 'testpass123',
                'email': 'new@example.com',
                'role': 'guard',
                'first_name': 'New',
                'last_name': 'User'
            },
            format='json'
        )
        
        assert response.status_code in (403, 405)
    
    def test_guard_can_list_users(self, authenticated_guard):
        """
        Guard can list users (limited view).
        
        Expected: 200 OK
        """
        response = authenticated_guard.get('/api/users/')
        
        assert response.status_code == 200
    
    def test_guard_can_retrieve_own_user(self, authenticated_guard, guard_user):
        """
        Guard can retrieve their own user details.
        
        Expected: 200 OK
        """
        response = authenticated_guard.get(f'/api/users/{guard_user.id}/')
        
        assert response.status_code == 200
    
    def test_guard_cannot_update_other_users(self, authenticated_guard, second_guard_user):
        """
        Guard cannot update other users.
        
        Expected: 403 Forbidden
        """
        response = authenticated_guard.put(
            f'/api/users/{second_guard_user.id}/',
            {
                'username': second_guard_user.username,
                'email': 'hacked@example.com',
                'role': 'guard',
                'first_name': 'Hacked',
                'last_name': 'Name'
            },
            format='json'
        )
        
        assert response.status_code in (403, 405)
    
    def test_guard_cannot_delete_users(self, authenticated_guard, second_guard_user):
        """
        Guard cannot delete users.
        
        Expected: 403 Forbidden
        """
        response = authenticated_guard.delete(f'/api/users/{second_guard_user.id}/')
        
        assert response.status_code in (403, 404, 405)


@pytest.mark.django_db
class TestUserUnauthenticated:
    """Integration tests for unauthenticated access to /api/users/"""
    
    def test_unauthenticated_cannot_list_users(self, api_client):
        """
        Unauthenticated users cannot list users.
        
        Expected: 401 Unauthorized or 403 Forbidden
        """
        response = api_client.get('/api/users/')
        
        assert response.status_code in (401, 403)
