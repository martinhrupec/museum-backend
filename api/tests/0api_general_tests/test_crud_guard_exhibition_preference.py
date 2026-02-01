"""
Integration tests for CRUD operations on GuardExhibitionPreference model.

Tests admin and guard permissions for:
- Creating guard exhibition preferences
- Reading guard exhibition preferences (list and detail)
- Updating guard exhibition preferences (full and partial)
- Deleting guard exhibition preferences
"""
import pytest
from datetime import date, timedelta
from api.api_models import GuardExhibitionPreference

def get_next_monday():
    today = date.today()
    days_ahead = 0 - today.weekday() + 7
    if days_ahead <= 0:
        days_ahead += 7
    return today + timedelta(days=days_ahead)


@pytest.mark.django_db
class TestAdminCRUDGuardExhibitionPreference:
    """Integration tests for admin CRUD operations on /api/guard-exhibition-preferences/"""
    
    def test_admin_can_create_guard_exhibition_preference(self, authenticated_admin, guard_user, sample_exhibition):
        """
        Admin CANNOT create exhibition preference directly.
        Guard sets preferences via: POST /api/guards/me/set_exhibition_preferences/
        
        Expected: 405 Method Not Allowed
        """
        response = authenticated_admin.post(
            '/api/guard-exhibition-preferences/',
            {
                'guard': guard_user.guard.id,
                'exhibition': sample_exhibition.id,
                'preference_level': 5
            },
            format='json'
        )
        
        assert response.status_code == 405
    
    def test_admin_can_list_guard_exhibition_preferences(self, authenticated_admin, guard_user, multiple_exhibitions):
        """
        Admin lists all guard exhibition preferences.
        
        Expected: 200 OK with list
        """
        next_monday = get_next_monday()
        exhibition_ids = [ex.id for ex in multiple_exhibitions]
        GuardExhibitionPreference.objects.create(
            guard=guard_user.guard,
            exhibition_order=exhibition_ids,
            is_template=False,
            next_week_start=next_monday
        )
        
        response = authenticated_admin.get('/api/guard-exhibition-preferences/')
        
        assert response.status_code == 200
        assert isinstance(response.data, (list, dict))
    
    def test_admin_can_retrieve_guard_exhibition_preference(self, authenticated_admin, guard_user, sample_exhibition):
        """
        Admin retrieves specific guard exhibition preference.
        
        Expected: 200 OK with preference data
        """
        next_monday = get_next_monday()
        preference = GuardExhibitionPreference.objects.create(
            guard=guard_user.guard,
            exhibition_order=[sample_exhibition.id],
            is_template=False,
            next_week_start=next_monday
        )
        
        response = authenticated_admin.get(f'/api/guard-exhibition-preferences/{preference.id}/')
        
        assert response.status_code == 200
        assert response.data['id'] == preference.id
    
    def test_admin_can_update_guard_exhibition_preference(self, authenticated_admin, guard_user, sample_exhibition):
        """
        Admin CANNOT update exhibition preference.
        ViewSet is ReadOnly.
        
        Expected: 405 Method Not Allowed
        """
        next_monday = get_next_monday()
        preference = GuardExhibitionPreference.objects.create(
            guard=guard_user.guard,
            exhibition_order=[sample_exhibition.id],
            is_template=False,
            next_week_start=next_monday
        )
        
        response = authenticated_admin.put(
            f'/api/guard-exhibition-preferences/{preference.id}/',
            {
                'guard': guard_user.guard.id,
                'exhibition_order': [sample_exhibition.id],
                'is_template': False,
                'next_week_start': str(next_monday)
            },
            format='json'
        )
        
        assert response.status_code == 405
    
    def test_admin_can_partial_update_guard_exhibition_preference(self, authenticated_admin, guard_user, sample_exhibition):
        """
        Admin CANNOT partially update exhibition preference.
        ViewSet is ReadOnly.
        
        Expected: 405 Method Not Allowed
        """
        next_monday = get_next_monday()
        preference = GuardExhibitionPreference.objects.create(
            guard=guard_user.guard,
            exhibition_order=[sample_exhibition.id],
            is_template=False,
            next_week_start=next_monday
        )
        
        response = authenticated_admin.patch(
            f'/api/guard-exhibition-preferences/{preference.id}/',
            {'exhibition_order': [sample_exhibition.id]},
            format='json'
        )
        
        assert response.status_code == 405
    
    def test_admin_can_delete_guard_exhibition_preference(self, authenticated_admin, guard_user, sample_exhibition):
        """
        Admin CANNOT delete exhibition preference.
        ViewSet is ReadOnly.
        
        Expected: 405 Method Not Allowed
        """
        next_monday = get_next_monday()
        preference = GuardExhibitionPreference.objects.create(
            guard=guard_user.guard,
            exhibition_order=[sample_exhibition.id],
            is_template=False,
            next_week_start=next_monday
        )
        
        response = authenticated_admin.delete(f'/api/guard-exhibition-preferences/{preference.id}/')
        
        assert response.status_code == 405


@pytest.mark.django_db
class TestGuardCRUDGuardExhibitionPreference:
    """Integration tests for guard CRUD operations on /api/guard-exhibition-preferences/"""
    
    def test_guard_can_list_own_exhibition_preferences(self, authenticated_guard, guard_user, multiple_exhibitions):
        """
        Guard can list their own exhibition preferences.
        
        Expected: 200 OK
        """
        next_monday = get_next_monday()
        exhibition_ids = [ex.id for ex in multiple_exhibitions]
        GuardExhibitionPreference.objects.create(
            guard=guard_user.guard,
            exhibition_order=exhibition_ids,
            is_template=False,
            next_week_start=next_monday
        )
        
        response = authenticated_guard.get('/api/guard-exhibition-preferences/')
        
        assert response.status_code == 200
    
    def test_guard_cannot_create_via_direct_post(self, authenticated_guard, guard_user, sample_exhibition):
        """
        Guard cannot create exhibition preferences via direct POST.
        (Should use /guards/{id}/set_exhibition_preferences/ endpoint)
        
        Expected: 403 or 405
        """
        response = authenticated_guard.post(
            '/api/guard-exhibition-preferences/',
            {
                'guard': guard_user.guard.id,
                'exhibition': sample_exhibition.id,
                'preference_level': 5
            },
            format='json'
        )
        
        assert response.status_code in (403, 405)
    
    def test_guard_cannot_update_via_direct_put(self, authenticated_guard, guard_user, multiple_exhibitions):
        """
        Guard cannot update exhibition preferences via direct PUT/PATCH.
        
        Expected: 403 or 405
        """
        next_monday = get_next_monday()
        exhibition_ids = [ex.id for ex in multiple_exhibitions]
        preference = GuardExhibitionPreference.objects.create(
            guard=guard_user.guard,
            exhibition_order=exhibition_ids,
            is_template=False,
            next_week_start=next_monday
        )
        
        response = authenticated_guard.patch(
            f'/api/guard-exhibition-preferences/{preference.id}/',
            {'exhibition_order': [exhibition_ids[0]]},
            format='json'
        )
        
        assert response.status_code in (403, 405)
    
    def test_guard_cannot_delete_exhibition_preference(self, authenticated_guard, guard_user, multiple_exhibitions):
        """
        Guard cannot delete exhibition preferences directly.
        
        Expected: 403 or 405
        """
        next_monday = get_next_monday()
        exhibition_ids = [ex.id for ex in multiple_exhibitions]
        preference = GuardExhibitionPreference.objects.create(
            guard=guard_user.guard,
            exhibition_order=exhibition_ids,
            is_template=False,
            next_week_start=next_monday
        )
        
        response = authenticated_guard.delete(f'/api/guard-exhibition-preferences/{preference.id}/')
        
        assert response.status_code in (403, 405)


@pytest.mark.django_db
class TestGuardExhibitionPreferenceUnauthenticated:
    """Integration tests for unauthenticated access to /api/guard-exhibition-preferences/"""
    
    def test_unauthenticated_cannot_access_exhibition_preferences(self, api_client):
        """
        Unauthenticated users cannot access exhibition preferences.
        
        Expected: 401 Unauthorized or 403 Forbidden
        """
        response = api_client.get('/api/guard-exhibition-preferences/')
        
        assert response.status_code in (401, 403)
