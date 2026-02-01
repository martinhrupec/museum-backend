"""
Integration tests for admin using user me endpoint.

Tests admin-specific functionality:
- Admin can get own user data
- Returns user object
"""
import pytest


@pytest.mark.django_db
class TestAdminUserMe:
    """Integration tests for admin using GET /api/users/me/"""
    
    def test_admin_can_get_own_user_data(self, authenticated_admin, admin_user):
        """
        Admin gets own user data via /me endpoint.
        
        Expected:
        - 200 OK response
        - User data matches admin_user
        """
        response = authenticated_admin.get('/api/users/me/')
        
        assert response.status_code == 200
        assert response.data['id'] == admin_user.id
        assert response.data['username'] == admin_user.username
        assert response.data['role'] == 'admin'
    
    def test_user_me_contains_required_fields(self, authenticated_admin):
        """
        /me endpoint returns all expected user fields.
        
        Expected:
        - All critical user fields present
        """
        response = authenticated_admin.get('/api/users/me/')
        
        assert response.status_code == 200
        expected_fields = ['id', 'username', 'email', 'first_name', 'last_name', 'role']
        for field in expected_fields:
            assert field in response.data
    
    def test_user_me_without_authentication_fails(self, api_client):
        """
        Getting user data without authentication fails.
        
        Expected:
        - 401 or 403 response
        """
        response = api_client.get('/api/users/me/')
        
        assert response.status_code in (401, 403)
