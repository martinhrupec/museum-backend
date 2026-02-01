"""
Integration tests for admin using session_check endpoint.

Tests admin-specific functionality:
- Admin can check session status
- Returns user data if authenticated
"""
import pytest


@pytest.mark.django_db
class TestAdminSessionCheck:
    """Integration tests for admin using GET /api/auth/check/"""
    
    def test_admin_session_check_authenticated(self, authenticated_admin, admin_user):
        """
        Admin checks session and gets user data.
        
        Expected:
        - 200 OK response
        - User data returned
        """
        response = authenticated_admin.get('/api/auth/check/')
        
        assert response.status_code == 200
        assert 'user' in response.data or 'username' in response.data
        # Verify it's the admin user
        if 'user' in response.data:
            assert response.data['user']['username'] == admin_user.username
        else:
            assert response.data['username'] == admin_user.username
    
    def test_session_check_unauthenticated(self, api_client):
        """
        Session check without authentication.
        
        Expected:
        - 401 or 403 response
        """
        response = api_client.get('/api/auth/check/')
        
        assert response.status_code in (401, 403)
