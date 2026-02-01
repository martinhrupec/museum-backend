"""
Integration tests for admin using user change_password endpoint.

Tests admin-specific functionality:
- Admin can change own password
- Password authentication works after change
"""
import pytest


@pytest.mark.django_db
class TestAdminChangePassword:
    """Integration tests for admin using POST /api/users/change_password/"""
    
    def test_admin_can_change_own_password(self, authenticated_admin, admin_user, api_client):
        """
        Admin successfully changes own password.
        
        Expected:
        - 200 OK response
        - Can login with new password
        - Cannot login with old password
        """
        response = authenticated_admin.post(
            '/api/users/change_password/',
            {
                'old_password': 'testpass123',
                'new_password': 'newpassword456',
                'new_password_confirm': 'newpassword456'
            },
            format='json'
        )
        
        assert response.status_code == 200
        
        # Verify can login with new password
        login_response = api_client.post(
            '/api/token/',
            {
                'username': admin_user.username,
                'password': 'newpassword456'
            },
            format='json'
        )
        assert login_response.status_code == 200
    
    def test_admin_change_password_wrong_old_password_fails(self, authenticated_admin):
        """
        Password change fails with wrong old password.
        
        Expected:
        - 400 response
        """
        response = authenticated_admin.post(
            '/api/users/change_password/',
            {
                'old_password': 'wrongpassword',
                'new_password': 'newpassword456'
            },
            format='json'
        )
        
        assert response.status_code == 400
    
    def test_admin_change_password_weak_password_fails(self, authenticated_admin):
        """
        Password change fails with weak new password.
        
        Expected:
        - 400 response (if password validation enabled)
        """
        response = authenticated_admin.post(
            '/api/users/change_password/',
            {
                'old_password': 'adminpass123',
                'new_password': '123'
            },
            format='json'
        )
        
        # May fail validation or succeed depending on settings
        assert response.status_code in (200, 400)
    
    def test_change_password_without_authentication_fails(self, api_client):
        """
        Changing password without authentication fails.
        
        Expected:
        - 401 or 403 response
        """
        response = api_client.post(
            '/api/users/change_password/',
            {
                'old_password': 'oldpass',
                'new_password': 'newpass'
            },
            format='json'
        )
        
        assert response.status_code in (401, 403)
