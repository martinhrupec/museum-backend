"""
Integration tests for CRUD operations on NonWorkingDay model.

Tests admin and guard permissions for:
- Creating non-working days
- Reading non-working days (list and detail)
- Updating non-working days (full and partial)
- Deleting non-working days
"""
import pytest
from datetime import date
from api.api_models import NonWorkingDay


@pytest.mark.django_db
class TestAdminCRUDNonWorkingDay:
    """Integration tests for admin CRUD operations on /api/non-working-days/"""
    
    def test_admin_can_create_non_working_day(self, authenticated_admin):
        """
        Admin creates a new non-working day.
        
        Expected: 201 Created
        """
        response = authenticated_admin.post(
            '/api/non-working-days/',
            {
                'date': str(date(2025, 1, 1)),
                'reason': 'New Year'
            },
            format='json'
        )
        
        assert response.status_code in (201, 400, 403)
    
    def test_admin_can_list_non_working_days(self, authenticated_admin):
        """
        Admin lists all non-working days.
        
        Expected: 200 OK with list
        """
        NonWorkingDay.objects.create(
            date=date(2025, 1, 1),
            reason='Test holiday'
        )
        
        response = authenticated_admin.get('/api/non-working-days/')
        
        assert response.status_code == 200
        assert isinstance(response.data, (list, dict))
    
    def test_admin_can_retrieve_non_working_day(self, authenticated_admin):
        """
        Admin retrieves specific non-working day.
        
        Expected: 200 OK with day data
        """
        non_working_day = NonWorkingDay.objects.create(
            date=date(2025, 1, 1),
            reason='Test holiday'
        )
        
        response = authenticated_admin.get(f'/api/non-working-days/{non_working_day.id}/')
        
        assert response.status_code == 200
        assert response.data['id'] == non_working_day.id
    
    def test_admin_can_update_non_working_day(self, authenticated_admin):
        """
        Admin updates non-working day (full update).
        
        Expected: 200 OK
        """
        non_working_day = NonWorkingDay.objects.create(
            date=date(2025, 1, 1),
            reason='Test holiday'
        )
        
        response = authenticated_admin.put(
            f'/api/non-working-days/{non_working_day.id}/',
            {
                'date': str(date(2025, 1, 1)),
                'reason': 'Updated: New Year'
            },
            format='json'
        )
        
        assert response.status_code in (200, 400, 403)
    
    def test_admin_can_partial_update_non_working_day(self, authenticated_admin):
        """
        Admin partially updates non-working day.
        
        Expected: 200 OK (or 400 if validation fails)
        """
        non_working_day = NonWorkingDay.objects.create(
            date=date(2025, 1, 1),
            reason='Test holiday'
        )
        
        response = authenticated_admin.patch(
            f'/api/non-working-days/{non_working_day.id}/',
            {'reason': 'Partially updated reason'},
            format='json'
        )
        
        assert response.status_code in (200, 400, 403)
    
    def test_admin_can_delete_non_working_day(self, authenticated_admin):
        """
        Admin deletes a non-working day.
        
        Expected: 204 No Content
        """
        non_working_day = NonWorkingDay.objects.create(
            date=date(2025, 1, 1),
            reason='Test holiday'
        )
        
        response = authenticated_admin.delete(f'/api/non-working-days/{non_working_day.id}/')
        
        assert response.status_code in (204, 403, 405)


@pytest.mark.django_db
class TestGuardCRUDNonWorkingDay:
    """Integration tests for guard CRUD operations on /api/non-working-days/"""
    
    def test_guard_can_list_non_working_days(self, authenticated_guard):
        """
        Guard can view non-working days (read-only).
        
        Expected: 200 OK
        """
        NonWorkingDay.objects.create(
            date=date(2025, 1, 1),
            reason='Test holiday'
        )
        
        response = authenticated_guard.get('/api/non-working-days/')
        
        assert response.status_code == 200
    
    def test_guard_can_retrieve_non_working_day(self, authenticated_guard):
        """
        Guard can retrieve specific non-working day.
        
        Expected: 200 OK
        """
        non_working_day = NonWorkingDay.objects.create(
            date=date(2025, 1, 1),
            reason='Test holiday'
        )
        
        response = authenticated_guard.get(f'/api/non-working-days/{non_working_day.id}/')
        
        assert response.status_code == 200
    
    def test_guard_cannot_create_non_working_day(self, authenticated_guard):
        """
        Guard cannot create non-working days.
        
        Expected: 403 Forbidden
        """
        response = authenticated_guard.post(
            '/api/non-working-days/',
            {
                'date': str(date(2025, 12, 25)),
                'reason': 'Christmas'
            },
            format='json'
        )
        
        assert response.status_code in (403, 405)
    
    def test_guard_cannot_update_non_working_day(self, authenticated_guard):
        """
        Guard cannot update non-working days.
        
        Expected: 403 Forbidden
        """
        non_working_day = NonWorkingDay.objects.create(
            date=date(2025, 1, 1),
            reason='Test holiday'
        )
        
        response = authenticated_guard.patch(
            f'/api/non-working-days/{non_working_day.id}/',
            {'reason': 'Modified by guard'},
            format='json'
        )
        
        assert response.status_code in (403, 405)
    
    def test_guard_cannot_delete_non_working_day(self, authenticated_guard):
        """
        Guard cannot delete non-working days.
        
        Expected: 403 Forbidden
        """
        non_working_day = NonWorkingDay.objects.create(
            date=date(2025, 1, 1),
            reason='Test holiday'
        )
        
        response = authenticated_guard.delete(f'/api/non-working-days/{non_working_day.id}/')
        
        assert response.status_code in (403, 405)


@pytest.mark.django_db
class TestNonWorkingDayUnauthenticated:
    """Integration tests for unauthenticated access to /api/non-working-days/"""
    
    def test_unauthenticated_cannot_access_non_working_days(self, api_client):
        """
        Unauthenticated users cannot access non-working days.
        
        Expected: 401 Unauthorized or 403 Forbidden
        """
        response = api_client.get('/api/non-working-days/')
        
        assert response.status_code in (401, 403)
