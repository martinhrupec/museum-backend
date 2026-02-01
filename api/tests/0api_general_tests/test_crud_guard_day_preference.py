"""
Integration tests for CRUD operations on GuardDayPreference model.

Tests admin and guard permissions for:
- Creating guard day preferences
- Reading guard day preferences (list and detail)
- Updating guard day preferences (full and partial)
- Deleting guard day preferences
"""
import pytest
from datetime import date, timedelta

def get_next_monday():
    today = date.today()
    days_ahead = 0 - today.weekday() + 7  # Monday is 0
    if days_ahead <= 0:
        days_ahead += 7
    return today + timedelta(days=days_ahead)

from api.api_models import GuardDayPreference


@pytest.mark.django_db
class TestAdminCRUDGuardDayPreference:
    """Integration tests for admin CRUD operations on /api/guard-day-preferences/"""
    
    def test_admin_can_create_guard_day_preference(self, authenticated_admin, guard_user):
        """
        Admin CANNOT create day preference directly through /api/guard-day-preferences/.
        Guard sets preferences via: POST /api/guards/me/set_day_preferences/
        
        Expected: 405 Method Not Allowed
        """
        response = authenticated_admin.post(
            '/api/guard-day-preferences/',
            {
                'guard': guard_user.guard.id,
                'date': str(date.today()),
                'preference_level': 5
            },
            format='json'
        )
        
        assert response.status_code == 405
    
    def test_admin_can_list_guard_day_preferences(self, authenticated_admin, guard_user):
        """
        Admin lists all guard day preferences.
        
        Expected: 200 OK with list
        """
        next_monday = get_next_monday()
        GuardDayPreference.objects.create(
            guard=guard_user.guard,
            day_order=[0, 1, 2],
            is_template=False,
            next_week_start=next_monday
        )
        
        response = authenticated_admin.get('/api/guard-day-preferences/')
        
        assert response.status_code == 200
        assert isinstance(response.data, (list, dict))
    
    def test_admin_can_retrieve_guard_day_preference(self, authenticated_admin, guard_user):
        """
        Admin retrieves specific guard day preference.
        
        Expected: 200 OK with preference data
        """
        next_monday = get_next_monday()
        preference = GuardDayPreference.objects.create(
            guard=guard_user.guard,
            day_order=[0, 1, 2],
            is_template=False,
            next_week_start=next_monday
        )
        
        response = authenticated_admin.get(f'/api/guard-day-preferences/{preference.id}/')
        
        assert response.status_code == 200
        assert response.data['id'] == preference.id
    
    def test_admin_can_update_guard_day_preference(self, authenticated_admin, guard_user):
        """
        Admin CANNOT update day preference directly.
        ViewSet is ReadOnly.
        
        Expected: 405 Method Not Allowed
        """
        next_monday = get_next_monday()
        preference = GuardDayPreference.objects.create(
            guard=guard_user.guard,
            day_order=[0, 1, 2],
            is_template=False,
            next_week_start=next_monday
        )
        
        response = authenticated_admin.put(
            f'/api/guard-day-preferences/{preference.id}/',
            {
                'guard': guard_user.guard.id,
                'day_order': [1, 2, 0],
                'is_template': False,
                'next_week_start': str(next_monday)
            },
            format='json'
        )
        
        assert response.status_code == 405
    
    def test_admin_can_partial_update_guard_day_preference(self, authenticated_admin, guard_user):
        """
        Admin CANNOT partially update day preference.
        ViewSet is ReadOnly.
        
        Expected: 405 Method Not Allowed
        """
        next_monday = get_next_monday()
        preference = GuardDayPreference.objects.create(
            guard=guard_user.guard,
            day_order=[0, 1, 2],
            is_template=False,
            next_week_start=next_monday
        )
        
        response = authenticated_admin.patch(
            f'/api/guard-day-preferences/{preference.id}/',
            {'day_order': [2, 1, 0]},
            format='json'
        )
        
        assert response.status_code == 405
    
    def test_admin_can_delete_guard_day_preference(self, authenticated_admin, guard_user):
        """
        Admin CANNOT delete day preference.
        ViewSet is ReadOnly.
        
        Expected: 405 Method Not Allowed
        """
        next_monday = get_next_monday()
        preference = GuardDayPreference.objects.create(
            guard=guard_user.guard,
            day_order=[0, 1, 2],
            is_template=False,
            next_week_start=next_monday
        )
        
        response = authenticated_admin.delete(f'/api/guard-day-preferences/{preference.id}/')
        
        assert response.status_code == 405


@pytest.mark.django_db
class TestGuardCRUDGuardDayPreference:
    """Integration tests for guard CRUD operations on /api/guard-day-preferences/"""
    
    def test_guard_can_list_own_day_preferences(self, authenticated_guard, guard_user):
        """
        Guard can list their own day preferences.
        
        Expected: 200 OK
        """
        next_monday = get_next_monday()
        GuardDayPreference.objects.create(
            guard=guard_user.guard,
            day_order=[0, 1, 2],
            is_template=False,
            next_week_start=next_monday
        )
        
        response = authenticated_guard.get('/api/guard-day-preferences/')
        
        assert response.status_code == 200
    
    def test_guard_cannot_create_via_direct_post(self, authenticated_guard, guard_user):
        """
        Guard cannot create day preferences via direct POST.
        (Should use /guards/{id}/set_day_preferences/ endpoint)
        
        Expected: 403 or 405
        """
        response = authenticated_guard.post(
            '/api/guard-day-preferences/',
            {
                'guard': guard_user.guard.id,
                'date': str(date.today()),
                'preference_level': 5
            },
            format='json'
        )
        
        assert response.status_code in (403, 405)
    
    def test_guard_cannot_update_via_direct_put(self, authenticated_guard, guard_user):
        """
        Guard cannot update day preferences via direct PUT/PATCH.
        
        Expected: 403 or 405
        """
        next_monday = get_next_monday()
        preference = GuardDayPreference.objects.create(
            guard=guard_user.guard,
            day_order=[0, 1, 2],
            is_template=False,
            next_week_start=next_monday
        )
        
        response = authenticated_guard.patch(
            f'/api/guard-day-preferences/{preference.id}/',
            {'day_order': [2, 1, 0]},
            format='json'
        )
        
        assert response.status_code in (403, 405)
    
    def test_guard_cannot_delete_day_preference(self, authenticated_guard, guard_user):
        """
        Guard cannot delete day preferences directly.
        
        Expected: 403 or 405
        """
        next_monday = get_next_monday()
        preference = GuardDayPreference.objects.create(
            guard=guard_user.guard,
            day_order=[0, 1, 2],
            is_template=False,
            next_week_start=next_monday
        )
        
        response = authenticated_guard.delete(f'/api/guard-day-preferences/{preference.id}/')
        
        assert response.status_code in (403, 405)


@pytest.mark.django_db
class TestGuardDayPreferenceUnauthenticated:
    """Integration tests for unauthenticated access to /api/guard-day-preferences/"""
    
    def test_unauthenticated_cannot_access_day_preferences(self, api_client):
        """
        Unauthenticated users cannot access day preferences.
        
        Expected: 401 Unauthorized or 403 Forbidden
        """
        response = api_client.get('/api/guard-day-preferences/')
        
        assert response.status_code in (401, 403)
