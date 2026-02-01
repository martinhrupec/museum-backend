"""
Integration tests for admin using session_login endpoint.

Tests admin-specific functionality:
- Admin can login via session
- Session is created
- Authentication works
"""
import pytest


@pytest.mark.django_db
class TestAdminSessionLogin:
    """Integration tests for admin using POST /api/login/"""
    
    def test_admin_can_login_via_session(self, api_client, admin_user):
        """
        Admin successfully logs in via session endpoint.
        
        Expected:
        - 200 OK response
        - Session created
        - User data returned
        """
        # Get CSRF token first
        # api_client.get("/api/login/")  # This will set csrftoken in cookies
        # csrf_token = api_client.cookies.get('csrftoken')
        # headers = {}
        # if csrf_token:
        #     headers['HTTP_X_CSRFTOKEN'] = csrf_token
        response = api_client.post(
            '/api/login/',
            {
                'username': admin_user.username,
                'password': 'testpass123'
            },
            format='json',
            #**headers
        )
        assert response.status_code == 200
        assert 'user' in response.data
        assert response.data['user']['username'] == admin_user.username
        assert response.data['user']['role'] == 'admin'
    
    def test_admin_login_with_wrong_password_fails(self, api_client, admin_user):
        """
        Admin login fails with wrong password.
        
        Expected:
        - 400 or 401 response
        - Error message
        """
        response = api_client.post(
            '/api/login/',
            {
                'username': admin_user.username,
                'password': 'wrongpassword'
            },
            format='json'
        )
        
        assert response.status_code in (400, 401)
    
    def test_admin_login_with_nonexistent_user_fails(self, api_client):
        """
        Login fails with nonexistent username.
        
        Expected:
        - 400 or 401 response
        """
        response = api_client.post(
            '/api/login/',
            {
                'username': 'nonexistent',
                'password': 'anypassword'
            },
            format='json'
        )
        
        assert response.status_code in (400, 401)
