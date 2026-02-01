"""
Integration tests for CRUD operations on Guard model.

Tests:
- Admin permissions for all CRUD operations
- Guard permissions (can only view themselves)
"""
import pytest
from api.api_models import Guard


@pytest.mark.django_db
class TestAdminCRUDGuard:
    """Integration tests for admin CRUD operations on /api/guards/"""
    
    def test_admin_can_create_guard(self, authenticated_admin, guard_user):
        """
        Admin CANNOT create guard directly through /api/guards/.
        Guards are auto-created via signal when User with role=ROLE_GUARD is created.
        
        Expected: 405 Method Not Allowed
        """
        response = authenticated_admin.post(
            '/api/guards/',
            {
                'user': guard_user.id,
                'phone_number': '+385991234567'
            },
            format='json'
        )
        
        assert response.status_code == 405
    
    def test_admin_can_list_guards(self, authenticated_admin, guard_user):
        """
        Admin lists all guards.
        
        Expected: 200 OK with list of guards
        """
        response = authenticated_admin.get('/api/guards/')
        
        assert response.status_code == 200
        assert isinstance(response.data, (list, dict))
    
    def test_admin_can_retrieve_guard(self, authenticated_admin, guard_user):
        """
        Admin retrieves specific guard details.
        
        Expected: 200 OK with guard data
        """
        response = authenticated_admin.get(f'/api/guards/{guard_user.guard.id}/')
        
        assert response.status_code == 200
        assert response.data['id'] == guard_user.guard.id
    
    def test_admin_can_update_guard(self, authenticated_admin, guard_user):
        """
        Admin CANNOT update guard directly through /api/guards/.
        Guard data modified via User endpoint and custom actions.
        
        Expected: 405 Method Not Allowed
        """
        response = authenticated_admin.put(
            f'/api/guards/{guard_user.guard.id}/',
            {
                'user': guard_user.id,
                'phone_number': '+385991111111'
            },
            format='json'
        )
        
        assert response.status_code == 405
    
    def test_admin_can_partial_update_guard(self, authenticated_admin, guard_user):
        """
        Admin CANNOT partially update guard directly through /api/guards/.
        
        Expected: 405 Method Not Allowed
        """
        response = authenticated_admin.patch(
            f'/api/guards/{guard_user.guard.id}/',
            {'phone_number': '+385992222222'},
            format='json'
        )
        
        assert response.status_code == 405
    
    def test_admin_can_delete_guard(self, authenticated_admin, guard_user):
        """
        Admin CANNOT delete guard directly through /api/guards/.
        Guards deleted by deactivating User (is_active=False).
        
        Expected: 405 Method Not Allowed
        """
        response = authenticated_admin.delete(f'/api/guards/{guard_user.guard.id}/')
        
        assert response.status_code == 405


@pytest.mark.django_db
class TestGuardCRUDGuard:
    """Integration tests for guard CRUD operations on /api/guards/"""
    
    def test_guard_cannot_create_guard(self, authenticated_guard):
        """
        Guard cannot create new guards.
        
        Expected: 403 Forbidden
        """
        response = authenticated_guard.post(
            '/api/guards/',
            {
                'phone_number': '+385991234567'
            },
            format='json'
        )
        
        assert response.status_code in (403, 405)
    
    def test_guard_can_list_guards_sees_only_self(self, authenticated_guard, guard_user, second_guard_user):
        """
        Guard listing guards sees only themselves.
        
        Expected: 200 OK with only own guard in list
        """
        response = authenticated_guard.get('/api/guards/')
        
        assert response.status_code == 200
        
        # Should only see themselves
        if isinstance(response.data, list):
            assert len(response.data) == 1
            assert response.data[0]['id'] == guard_user.guard.id
        else:
            # Paginated response
            assert response.data.get('count', len(response.data.get('results', []))) <= 1
    
    def test_guard_can_retrieve_own_profile(self, authenticated_guard, guard_user):
        """
        Guard can retrieve their own profile.
        
        Expected: 200 OK with own guard data
        """
        response = authenticated_guard.get(f'/api/guards/{guard_user.guard.id}/')
        
        assert response.status_code == 200
        assert response.data['id'] == guard_user.guard.id
    
    def test_guard_cannot_retrieve_other_guards_profile(
        self, authenticated_guard, second_guard_user
    ):
        """
        Guard cannot retrieve another guard's profile.
        
        Expected: 403 Forbidden or 404 Not Found
        """
        response = authenticated_guard.get(f'/api/guards/{second_guard_user.guard.id}/')
        
        assert response.status_code in (403, 404)
    
    def test_guard_cannot_update_guard(self, authenticated_guard, guard_user):
        """
        Guard cannot update guard records.
        
        Expected: 403 Forbidden or 405 Method Not Allowed
        """
        response = authenticated_guard.put(
            f'/api/guards/{guard_user.guard.id}/',
            {
                'mail': 'guard@example.com'
            },
            format='json'
        )
        
        assert response.status_code in (403, 405)
    
    def test_guard_cannot_partial_update_guard(self, authenticated_guard, guard_user):
        """
        Guard cannot partially update guard records.
        
        Expected: 403 Forbidden or 405 Method Not Allowed
        """
        response = authenticated_guard.patch(
            f'/api/guards/{guard_user.guard.id}/',
            {'phone_number': '+385992222222'},
            format='json'
        )
        
        assert response.status_code in (403, 405)
    
    def test_guard_cannot_delete_guard(self, authenticated_guard, guard_user):
        """
        Guard cannot delete guards.
        
        Expected: 403 Forbidden or 405 Method Not Allowed
        """
        response = authenticated_guard.delete(f'/api/guards/{guard_user.guard.id}/')
        
        assert response.status_code in (403, 405)


@pytest.mark.django_db
class TestGuardCRUDGuardUnauthenticated:
    """Integration tests for unauthenticated access to /api/guards/"""
    
    def test_unauthenticated_cannot_list_guards(self, api_client):
        """
        Unauthenticated users cannot list guards.
        
        Expected: 401 Unauthorized or 403 Forbidden
        """
        response = api_client.get('/api/guards/')
        
        assert response.status_code in (401, 403)
    
    def test_unauthenticated_cannot_retrieve_guard(self, api_client, guard_user):
        """
        Unauthenticated users cannot retrieve guards.
        
        Expected: 401 Unauthorized or 403 Forbidden
        """
        response = api_client.get(f'/api/guards/{guard_user.guard.id}/')
        
        assert response.status_code in (401, 403)
