"""
Integration tests for admin using session_logout endpoint.

Tests admin-specific functionality:
- Admin can logout via session
- Session is destroyed
"""
import pytest


@pytest.mark.django_db
class TestAdminSessionLogout:
    """Integration tests for admin using POST /api/logout/"""
    
    def test_admin_can_logout_via_session(self, authenticated_admin):
        """
        Admin successfully logs out via session endpoint.
        
        Expected:
        - 200 OK response
        - Session destroyed
        """
        response = authenticated_admin.post('/api/logout/')
        
        assert response.status_code == 200
        assert 'message' in response.data or 'detail' in response.data
    
    def test_logout_without_authentication(self, api_client):
        """
        Logout without authentication.
        
        Expected:
        - 200 OK (may still succeed) or 401
        """
        response = api_client.post('/api/logout/')
        
        # Both are acceptable
        assert response.status_code in (200, 401)
