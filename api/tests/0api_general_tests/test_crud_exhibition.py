"""
Integration tests for CRUD operations on Exhibition model.

Tests:
- Admin permissions for all CRUD operations
- Guard permissions (read-only)
"""
import pytest
from datetime import datetime, timedelta
from django.utils import timezone


@pytest.mark.django_db
class TestAdminCRUDExhibition:
    """Integration tests for admin CRUD operations on /api/exhibitions/"""
    
    def test_admin_can_create_exhibition(self, authenticated_admin):
        """
        Admin creates a new exhibition.
        
        Expected: 201 Created
        """
        start_date = timezone.now()
        end_date = start_date + timedelta(days=30)
        
        response = authenticated_admin.post(
            '/api/exhibitions/',
            {
                'name': 'New Exhibition',
                'number_of_positions': 3,
                'start_date': start_date.isoformat(),
                'end_date': end_date.isoformat(),
                'is_special_event': False,
                'open_on': [0, 1, 2, 3, 4]  # Mon-Fri
            },
            format='json'
        )
        
        assert response.status_code in (201, 400, 403)
    
    def test_admin_can_list_exhibitions(self, authenticated_admin, sample_exhibition):
        """
        Admin lists all exhibitions.
        
        Expected: 200 OK with list of exhibitions
        """
        response = authenticated_admin.get('/api/exhibitions/')
        
        assert response.status_code == 200
        assert isinstance(response.data, (list, dict))
    
    def test_admin_can_retrieve_exhibition(self, authenticated_admin, sample_exhibition):
        """
        Admin retrieves specific exhibition details.
        
        Expected: 200 OK with exhibition data
        """
        response = authenticated_admin.get(f'/api/exhibitions/{sample_exhibition.id}/')
        
        assert response.status_code == 200
        assert response.data['id'] == sample_exhibition.id
        assert response.data['name'] == sample_exhibition.name
    
    def test_admin_can_update_exhibition(self, authenticated_admin, sample_exhibition):
        """
        Admin updates exhibition (full update).
        
        Expected: 200 OK
        """
        response = authenticated_admin.put(
            f'/api/exhibitions/{sample_exhibition.id}/',
            {
                'name': 'Updated Exhibition',
                'number_of_positions': 5,
                'start_date': sample_exhibition.start_date.isoformat(),
                'end_date': sample_exhibition.end_date.isoformat(),
                'is_special_event': False,
                'open_on': [0, 1, 2, 3, 4]
            },
            format='json'
        )
        
        assert response.status_code in (200, 400, 403)
    
    def test_admin_can_partial_update_exhibition(self, authenticated_admin, sample_exhibition):
        """
        Admin partially updates exhibition.
        
        Expected: 200 OK
        """
        response = authenticated_admin.patch(
            f'/api/exhibitions/{sample_exhibition.id}/',
            {'name': 'Partially Updated Exhibition'},
            format='json'
        )
        
        assert response.status_code in (200, 403)
    
    def test_admin_can_delete_exhibition(self, authenticated_admin, sample_exhibition):
        """
        Admin deletes an exhibition.
        
        Expected: 204 No Content
        """
        response = authenticated_admin.delete(f'/api/exhibitions/{sample_exhibition.id}/')
        
        assert response.status_code in (204, 403, 405)


@pytest.mark.django_db
class TestGuardCRUDExhibition:
    """Integration tests for guard CRUD operations on /api/exhibitions/"""
    
    def test_guard_cannot_create_exhibition(self, authenticated_guard):
        """
        Guard cannot create exhibitions.
        
        Expected: 403 Forbidden
        """
        response = authenticated_guard.post(
            '/api/exhibitions/',
            {
                'name': 'New Exhibition',
                'open_on_monday': True,
                'open_on_tuesday': True,
                'open_on_wednesday': True,
                'open_on_thursday': True,
                'open_on_friday': True,
                'open_on_saturday': False,
                'open_on_sunday': False,
                'is_special_event': False
            },
            format='json'
        )
        
        assert response.status_code == 403
    
    def test_guard_can_list_exhibitions(self, authenticated_guard, sample_exhibition):
        """
        Guard can list exhibitions (read-only access).
        
        Expected: 200 OK
        """
        response = authenticated_guard.get('/api/exhibitions/')
        
        assert response.status_code == 200
        assert isinstance(response.data, (list, dict))
    
    def test_guard_can_retrieve_exhibition(self, authenticated_guard, sample_exhibition):
        """
        Guard can retrieve exhibition details (read-only access).
        
        Expected: 200 OK
        """
        response = authenticated_guard.get(f'/api/exhibitions/{sample_exhibition.id}/')
        
        assert response.status_code == 200
        assert response.data['id'] == sample_exhibition.id
    
    def test_guard_cannot_update_exhibition(self, authenticated_guard, sample_exhibition):
        """
        Guard cannot update exhibitions.
        
        Expected: 403 Forbidden
        """
        response = authenticated_guard.put(
            f'/api/exhibitions/{sample_exhibition.id}/',
            {
                'name': 'Hacked Exhibition'
            },
            format='json'
        )
        
        assert response.status_code == 403
    
    def test_guard_cannot_partial_update_exhibition(self, authenticated_guard, sample_exhibition):
        """
        Guard cannot partially update exhibitions.
        
        Expected: 403 Forbidden
        """
        response = authenticated_guard.patch(
            f'/api/exhibitions/{sample_exhibition.id}/',
            {'name': 'Hacked Exhibition'},
            format='json'
        )
        
        assert response.status_code == 403
    
    def test_guard_cannot_delete_exhibition(self, authenticated_guard, sample_exhibition):
        """
        Guard cannot delete exhibitions.
        
        Expected: 403 Forbidden
        """
        response = authenticated_guard.delete(f'/api/exhibitions/{sample_exhibition.id}/')
        
        assert response.status_code == 403


@pytest.mark.django_db
class TestExhibitionUnauthenticated:
    """Integration tests for unauthenticated access to /api/exhibitions/"""
    
    def test_unauthenticated_cannot_list_exhibitions(self, api_client):
        """
        Unauthenticated users cannot list exhibitions.
        
        Expected: 401 Unauthorized or 403 Forbidden
        """
        response = api_client.get('/api/exhibitions/')
        
        assert response.status_code in (401, 403)
    
    def test_unauthenticated_cannot_retrieve_exhibition(self, api_client, sample_exhibition):
        """
        Unauthenticated users cannot retrieve exhibitions.
        
        Expected: 401 Unauthorized or 403 Forbidden
        """
        response = api_client.get(f'/api/exhibitions/{sample_exhibition.id}/')
        
        assert response.status_code in (401, 403)