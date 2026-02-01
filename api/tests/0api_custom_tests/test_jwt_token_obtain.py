"""
Integration tests for JWT token obtain endpoint.

Tests:
- POST /api/token/ - Login and get access + refresh tokens
- Validates credentials
- Returns proper token structure
"""
import pytest
from api.models import User


@pytest.mark.django_db
class TestJWTTokenObtain:
    """Integration tests for POST /api/token/"""
    
    def test_valid_login_returns_tokens(self, api_client, admin_user):
        """
        Valid credentials return access and refresh tokens.
        
        Expected:
        - 200 OK
        - Response contains 'access' and 'refresh' tokens
        """
        response = api_client.post(
            '/api/token/',
            {
                'username': 'admin',
                'password': 'testpass123'
            },
            format='json'
        )
        
        assert response.status_code == 200
        assert 'access' in response.data
        assert 'refresh' in response.data
        assert len(response.data['access']) > 50  # JWT tokens are long strings
        assert len(response.data['refresh']) > 50
    
    def test_invalid_password_fails(self, api_client, admin_user):
        """
        Invalid password returns 401.
        
        Expected:
        - 401 Unauthorized
        """
        response = api_client.post(
            '/api/token/',
            {
                'username': 'admin',
                'password': 'wrongpassword'
            },
            format='json'
        )
        
        assert response.status_code == 401
    
    def test_nonexistent_user_fails(self, api_client):
        """
        Non-existent user returns 401.
        
        Expected:
        - 401 Unauthorized
        """
        response = api_client.post(
            '/api/token/',
            {
                'username': 'nonexistent',
                'password': 'somepassword'
            },
            format='json'
        )
        
        assert response.status_code == 401
    
    def test_inactive_user_cannot_login(self, api_client, inactive_user):
        """
        Inactive user cannot obtain tokens.
        
        Expected:
        - 401 Unauthorized
        """
        response = api_client.post(
            '/api/token/',
            {
                'username': 'inactive',
                'password': 'testpass123'
            },
            format='json'
        )
        
        assert response.status_code == 401
    
    def test_guard_can_login(self, api_client, guard_user):
        """
        Guard user can obtain tokens.
        
        Expected:
        - 200 OK with tokens
        """
        response = api_client.post(
            '/api/token/',
            {
                'username': 'guard1',
                'password': 'testpass123'
            },
            format='json'
        )
        
        assert response.status_code == 200
        assert 'access' in response.data
        assert 'refresh' in response.data
    
    def test_missing_credentials_fails(self, api_client):
        """
        Missing username or password returns 400.
        
        Expected:
        - 400 Bad Request
        """
        # Missing password
        response = api_client.post(
            '/api/token/',
            {'username': 'admin'},
            format='json'
        )
        assert response.status_code == 400
        
        # Missing username
        response = api_client.post(
            '/api/token/',
            {'password': 'testpass123'},
            format='json'
        )
        assert response.status_code == 400
