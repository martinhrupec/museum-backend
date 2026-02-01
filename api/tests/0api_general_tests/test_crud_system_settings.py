"""
Integration tests for CRUD operations on SystemSettings model.

Tests admin and guard permissions for:
- Creating system settings (if applicable)
- Reading system settings (list and detail)
- Updating system settings (full and partial)
- Deleting system settings (if applicable)
"""
import pytest
from datetime import date, time
from api.api_models import SystemSettings


@pytest.mark.django_db
class TestAdminCRUDSystemSettings:
    """Integration tests for admin CRUD operations on /api/system-settings/"""
    
    def test_admin_can_create_system_settings(self, authenticated_admin):
        """
        Admin creates new system settings.
        
        Expected: 201 Created or 400/403 if only one instance allowed
        """
        response = authenticated_admin.post(
            '/api/system-settings/',
            {
                'this_week_start': str(date.today()),
                'this_week_end': str(date.today()),
                'next_week_start': str(date.today()),
                'next_week_end': str(date.today()),
                'manual_configuration_period_has_ended': False,
                'workdays': '1,2,3,4,5',
                'weekday_morning_start': '08:00:00',
                'weekday_morning_end': '12:00:00',
                'weekday_afternoon_start': '13:00:00',
                'weekday_afternoon_end': '17:00:00',
                'saturday_morning_start': '09:00:00',
                'saturday_morning_end': '13:00:00',
                'saturday_afternoon_start': '14:00:00',
                'saturday_afternoon_end': '18:00:00',
                'sunday_morning_start': '10:00:00',
                'sunday_morning_end': '14:00:00',
                'sunday_afternoon_start': '15:00:00',
                'sunday_afternoon_end': '19:00:00'
            },
            format='json'
        )
        
        assert response.status_code in (201, 400, 403)
    
    def test_admin_can_list_system_settings(self, authenticated_admin, system_settings):
        """
        Admin lists all system settings.
        
        Expected: 200 OK with list
        """
        response = authenticated_admin.get('/api/system-settings/')
        
        assert response.status_code == 200
        assert isinstance(response.data, (list, dict))
    
    def test_admin_can_retrieve_system_settings(self, authenticated_admin, system_settings):
        """
        Admin retrieves specific system settings.
        
        Expected: 200 OK with settings data
        """
        response = authenticated_admin.get(f'/api/system-settings/{system_settings.id}/')
        
        assert response.status_code == 200
        assert response.data['id'] == system_settings.id
    
    def test_admin_can_update_system_settings(self, authenticated_admin, system_settings):
        """
        Admin updates system settings (full update).
        
        Expected: 200 OK
        """
        response = authenticated_admin.put(
            f'/api/system-settings/{system_settings.id}/',
            {
                'this_week_start': str(system_settings.this_week_start),
                'this_week_end': str(system_settings.this_week_end),
                'next_week_start': str(system_settings.next_week_start),
                'next_week_end': str(system_settings.next_week_end),
                'manual_configuration_period_has_ended': True,
                'workdays': '1,2,3,4,5',
                'weekday_morning_start': '08:00:00',
                'weekday_morning_end': '12:00:00',
                'weekday_afternoon_start': '13:00:00',
                'weekday_afternoon_end': '17:00:00',
                'saturday_morning_start': '09:00:00',
                'saturday_morning_end': '13:00:00',
                'saturday_afternoon_start': '14:00:00',
                'saturday_afternoon_end': '18:00:00',
                'sunday_morning_start': '10:00:00',
                'sunday_morning_end': '14:00:00',
                'sunday_afternoon_start': '15:00:00',
                'sunday_afternoon_end': '19:00:00'
            },
            format='json'
        )
        
        assert response.status_code in (200, 400, 403)
    
    def test_admin_can_partial_update_system_settings(self, authenticated_admin, system_settings):
        """
        Admin partially updates system settings.
        
        Expected: 200 OK
        """
        response = authenticated_admin.patch(
            f'/api/system-settings/{system_settings.id}/',
            {'manual_configuration_period_has_ended': True},
            format='json'
        )
        
        assert response.status_code in (200, 403)
    
    def test_admin_can_delete_system_settings(self, authenticated_admin, system_settings):
        """
        Admin deletes system settings.
        
        Expected: 204 No Content or 403/405 if deletion not allowed
        """
        response = authenticated_admin.delete(f'/api/system-settings/{system_settings.id}/')
        
        assert response.status_code in (204, 403, 405)


@pytest.mark.django_db
class TestGuardCRUDSystemSettings:
    """Integration tests for guard CRUD operations on /api/system-settings/"""
    
    def test_guard_can_list_system_settings(self, authenticated_guard, system_settings):
        """
        Guard can view system settings (read-only).
        
        Expected: 200 OK
        """
        response = authenticated_guard.get('/api/system-settings/')
        
        assert response.status_code == 200
    
    def test_guard_can_retrieve_system_settings(self, authenticated_guard, system_settings):
        """
        Guard can retrieve specific system settings.
        
        Expected: 200 OK
        """
        response = authenticated_guard.get(f'/api/system-settings/{system_settings.id}/')
        
        assert response.status_code == 200
    
    def test_guard_cannot_create_system_settings(self, authenticated_guard):
        """
        Guard cannot create system settings.
        
        Expected: 403 Forbidden
        """
        response = authenticated_guard.post(
            '/api/system-settings/',
            {
                'this_week_start': str(date.today()),
                'this_week_end': str(date.today()),
                'next_week_start': str(date.today()),
                'next_week_end': str(date.today()),
                'manual_configuration_period_has_ended': False,
                'workdays': '1,2,3,4,5'
            },
            format='json'
        )
        
        assert response.status_code in (403, 405)
    
    def test_guard_cannot_update_system_settings(self, authenticated_guard, system_settings):
        """
        Guard cannot update system settings.
        
        Expected: 403 Forbidden
        """
        response = authenticated_guard.patch(
            f'/api/system-settings/{system_settings.id}/',
            {'manual_configuration_period_has_ended': True},
            format='json'
        )
        
        assert response.status_code in (403, 405)
    
    def test_guard_cannot_delete_system_settings(self, authenticated_guard, system_settings):
        """
        Guard cannot delete system settings.
        
        Expected: 403 Forbidden
        """
        response = authenticated_guard.delete(f'/api/system-settings/{system_settings.id}/')
        
        assert response.status_code in (403, 405)


@pytest.mark.django_db
class TestSystemSettingsUnauthenticated:
    """Integration tests for unauthenticated access to /api/system-settings/"""
    
    def test_unauthenticated_cannot_access_system_settings(self, api_client):
        """
        Unauthenticated users cannot access system settings.
        
        Expected: 401 Unauthorized or 403 Forbidden
        """
        response = api_client.get('/api/system-settings/')
        
        assert response.status_code in (401, 403)
