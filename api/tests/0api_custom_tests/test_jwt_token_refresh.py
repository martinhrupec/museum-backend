"""
Integration tests for JWT token refresh endpoint.

Tests:
- POST /api/token/refresh/ - Get new access token using refresh token
- Validates refresh token
- Returns new access token
"""
import pytest


@pytest.mark.django_db
class TestJWTTokenRefresh:
    """Integration tests for POST /api/token/refresh/"""
    
    def test_valid_refresh_token_returns_new_access(self, api_client, admin_user):
        """
        Valid refresh token returns new access token.
        
        Expected:
        - 200 OK
        - Response contains new 'access' token
        """
        # First, login to get tokens
        login_response = api_client.post(
            '/api/token/',
            {
                'username': 'admin',
                'password': 'testpass123'
            },
            format='json'
        )
        refresh_token = login_response.data['refresh']
        
        # Now refresh
        response = api_client.post(
            '/api/token/refresh/',
            {'refresh': refresh_token},
            format='json'
        )
        
        assert response.status_code == 200
        assert 'access' in response.data
        assert len(response.data['access']) > 50
    
    def test_invalid_refresh_token_fails(self, api_client):
        """
        Invalid refresh token returns 401.
        
        Expected:
        - 401 Unauthorized
        """
        response = api_client.post(
            '/api/token/refresh/',
            {'refresh': 'invalid.token.here'},
            format='json'
        )
        
        assert response.status_code == 401
    
    def test_missing_refresh_token_fails(self, api_client):
        """
        Missing refresh token returns 400.
        
        Expected:
        - 400 Bad Request
        """
        response = api_client.post(
            '/api/token/refresh/',
            {},
            format='json'
        )
        
        assert response.status_code == 400
    
    def test_blacklisted_refresh_token_fails(self, api_client, admin_user):
        """
        Blacklisted (logged out) refresh token cannot be used.
        
        Expected:
        - 401 Unauthorized
        """
        # Login
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
        
        # Logout (blacklist the refresh token - requires Authorization header)
        api_client.post(
            '/api/token/logout/',
            {'refresh': refresh_token},
            format='json',
            HTTP_AUTHORIZATION=f'Bearer {access_token}'
        )
        
        # Try to refresh with blacklisted token
        response = api_client.post(
            '/api/token/refresh/',
            {'refresh': refresh_token},
            format='json'
        )
        
        assert response.status_code == 401
