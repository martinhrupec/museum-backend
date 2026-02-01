"""
Integration tests for admin using user update_profile endpoint.

Tests admin-specific functionality:
- Admin can update own profile
- Profile fields are updated correctly
"""
import pytest


@pytest.mark.django_db
class TestAdminUpdateProfile:
    """Integration tests for admin using PATCH /api/users/update_profile/"""
    
    def test_admin_can_update_own_profile(self, authenticated_admin, admin_user):
        """
        Admin successfully updates own profile.
        
        Expected:
        - 200 OK response
        - Profile fields updated
        """
        response = authenticated_admin.patch(
            '/api/users/update_profile/',
            {
                'first_name': 'UpdatedFirstName',
                'last_name': 'UpdatedLastName'
            },
            format='json'
        )
        
        assert response.status_code == 200
        assert response.data['first_name'] == 'UpdatedFirstName'
        assert response.data['last_name'] == 'UpdatedLastName'
        
        # Verify in database
        admin_user.refresh_from_db()
        assert admin_user.first_name == 'UpdatedFirstName'
        assert admin_user.last_name == 'UpdatedLastName'
    
    def test_admin_can_update_email(self, authenticated_admin, admin_user):
        """
        Admin can update email address.
        
        Expected:
        - 200 OK response
        - Email updated
        """
        new_email = 'newemail@example.com'
        response = authenticated_admin.patch(
            '/api/users/update_profile/',
            {'email': new_email},
            format='json'
        )
        
        assert response.status_code == 200
        assert response.data['email'] == new_email
        
        admin_user.refresh_from_db()
        assert admin_user.email == new_email
    
    def test_admin_can_update_username(self, authenticated_admin, admin_user):
        """
        Admin can change username via update_profile.
        
        Expected:
        - 200 OK response
        - Username updated
        """
        response = authenticated_admin.patch(
            '/api/users/update_profile/',
            {'username': 'newusername'},
            format='json'
        )
        
        assert response.status_code == 200
        assert response.data['username'] == 'newusername'
        
        admin_user.refresh_from_db()
        assert admin_user.username == 'newusername'
    
    def test_update_profile_without_authentication_fails(self, api_client):
        """
        Updating profile without authentication fails.
        
        Expected:
        - 401 or 403 response
        """
        response = api_client.patch(
            '/api/users/update_profile/',
            {'first_name': 'Test'},
            format='json'
        )
        
        assert response.status_code in (401, 403)


@pytest.mark.django_db
class TestAdminUpdateOtherProfiles:
    """Integration tests for admin updating OTHER users' profiles via PATCH /api/users/{id}/"""
    
    def test_admin_can_update_guard_profile(self, authenticated_admin, guard_user):
        """
        Admin can update guard's profile through /api/users/{id}/ endpoint.
        
        Expected:
        - 200 OK response
        - Guard profile updated
        """
        response = authenticated_admin.patch(
            f'/api/users/{guard_user.id}/',
            {
                'first_name': 'AdminUpdatedFirst',
                'last_name': 'AdminUpdatedLast',
                'email': 'admineditedguard@example.com'
            },
            format='json'
        )
        
        assert response.status_code == 200
        assert response.data['first_name'] == 'AdminUpdatedFirst'
        assert response.data['last_name'] == 'AdminUpdatedLast'
        assert response.data['email'] == 'admineditedguard@example.com'
        
        guard_user.refresh_from_db()
        assert guard_user.first_name == 'AdminUpdatedFirst'
        assert guard_user.last_name == 'AdminUpdatedLast'
        assert guard_user.email == 'admineditedguard@example.com'
    
    def test_admin_can_update_guard_username(self, authenticated_admin, guard_user):
        """
        Admin can change guard's username through /api/users/{id}/ endpoint.
        
        Expected:
        - 200 OK response
        - Username updated
        """
        response = authenticated_admin.patch(
            f'/api/users/{guard_user.id}/',
            {'username': 'admin_changed_username'},
            format='json'
        )
        
        assert response.status_code == 200
        assert response.data['username'] == 'admin_changed_username'
        
        guard_user.refresh_from_db()
        assert guard_user.username == 'admin_changed_username'
    
    def test_guard_cannot_update_other_guard_profile(
        self, authenticated_guard, guard_user, second_guard_user
    ):
        """
        Guard cannot update another guard's profile.
        
        Expected:
        - 403 or 404 (queryset filtering)
        """
        response = authenticated_guard.patch(
            f'/api/users/{second_guard_user.id}/',
            {'first_name': 'HackedName'},
            format='json'
        )
        
        assert response.status_code in (403, 404)
        
        # Verify nothing changed
        second_guard_user.refresh_from_db()
        assert second_guard_user.first_name != 'HackedName'


@pytest.mark.django_db
class TestGuardUpdateProfile:
    """Integration tests for guard using PATCH /api/users/update_profile/"""

    def test_guard_can_update_own_profile(self, authenticated_guard, guard_user):
        response = authenticated_guard.patch(
            '/api/users/update_profile/',
            {'first_name': 'GuardFirst', 'last_name': 'GuardLast'},
            format='json'
        )
        assert response.status_code == 200
        assert response.data['first_name'] == 'GuardFirst'
        assert response.data['last_name'] == 'GuardLast'
        guard_user.refresh_from_db()
        assert guard_user.first_name == 'GuardFirst'
        assert guard_user.last_name == 'GuardLast'

    def test_guard_can_update_email(self, authenticated_guard, guard_user):
        new_email = 'guardnew@example.com'
        response = authenticated_guard.patch(
            '/api/users/update_profile/',
            {'email': new_email},
            format='json'
        )
        assert response.status_code == 200
        assert response.data['email'] == new_email
        guard_user.refresh_from_db()
        assert guard_user.email == new_email

    def test_guard_can_update_username(self, authenticated_guard, guard_user):
        """
        Guard CANNOT change username via update_profile.
        Username is read_only in UserDetailSerializer.
        
        Expected:
        - 200 OK response
        - Username NOT changed (ignored)
        """
        original_username = guard_user.username
        
        response = authenticated_guard.patch(
            '/api/users/update_profile/',
            {'username': 'guardnewusername'},
            format='json'
        )
        assert response.status_code == 200
        assert response.data['username'] == original_username  # Still 'guard1'
        guard_user.refresh_from_db()
        assert guard_user.username == original_username  # Not changed
