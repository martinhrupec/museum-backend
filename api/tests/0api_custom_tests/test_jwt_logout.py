"""
Integration tests for JWT logout endpoint.

Tests:
- POST /api/token/logout/ - st refresh token on logout
- Validates refresh token
- Prevents reuse after logout
"""
import pytest


@pytest.mark.django_db
class TestJWTLogout:
    """Integration tests for POST /api/token/logout/"""
    
    def test_admin_can_logout_via_jwt(self, api_client, admin_user):
        """
        Admin successfully logs out via JWT endpoint.
        
        Expected:
        - 200 or 204 response
        - Refresh token sted and cannot be reused
        """
        # Login first
        login_response = api_client.post(
            '/api/token/',
            {
                'username': 'admin',
                'password': 'testpass123'
            },
            format='json'
        )
        access_token = login_response.data['access']
        refresh_token = login_response.data['refresh']
        
        # Logout (requires Authorization header)
        response = api_client.post(
            '/api/token/logout/',
            {'refresh': refresh_token},
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {access_token}'
        )
        
        assert response.status_code in (200, 204, 205)
        
        # Verify token is sted - try to refresh
        refresh_response = api_client.post(
            '/api/token/refresh/',
            {'refresh': refresh_token},
            format='json'
        )
        assert refresh_response.status_code == 401
    
    def test_guard_can_logout_via_jwt(self, api_client, guard_user):
        """
        Guard successfully logs out via JWT endpoint.
        
        Expected:
        - 200 or 204 response
        - Refresh token sted
        """
        # Login first
        login_response = api_client.post(
            '/api/token/',
            {
                'username': 'guard1',
                'password': 'testpass123'
            },
            format='json'
        )
        access_token = login_response.data['access']
        refresh_token = login_response.data['refresh']
        
        # Logout (requires Authorization header)
        response = api_client.post(
            '/api/token/logout/',
            {'refresh': refresh_token},
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {access_token}'
        )
        
        assert response.status_code in (200, 204, 205)
    
    def test_jwt_logout_with_invalid_token(self, api_client, admin_user):
        """
        Logout with invalid refresh token.
        
        Expected:
        - 400 or 401
        """
        # Login to get access token for authentication
        login_response = api_client.post(
            '/api/token/',
            {
                'username': 'admin',
                'password': 'testpass123'
            },
            format='json'
        )
        access_token = login_response.data['access']
        
        # Try logout with invalid token
        response = api_client.post(
            '/api/token/logout/',
            {'refresh': 'invalid_token'},
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {access_token}'
        )
        
        assert response.status_code in (400, 401)
    
    def test_logout_with_missing_refresh_token_fails(self, api_client, admin_user):
        """
        Logout without providing refresh token fails.
        
        Expected:
        - 400 Bad Request
        """
        # Login to get access token
        login_response = api_client.post(
            '/api/token/',
            {
                'username': 'admin',
                'password': 'testpass123'
            },
            format='json'
        )
        access_token = login_response.data['access']
        
        # Try logout without refresh token
        response = api_client.post(
            '/api/token/logout/',
            {},
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {access_token}'
        )
        
        assert response.status_code == 400
