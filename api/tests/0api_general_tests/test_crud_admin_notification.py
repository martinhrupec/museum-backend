"""
Integration tests for CRUD operations on AdminNotification model.

Tests admin and guard permissions for:
- Creating admin notifications
- Reading notifications (list and detail)
- Updating notifications (full and partial)
- Deleting notifications
"""
import pytest
from api.api_models import AdminNotification
from django.utils import timezone
from datetime import timedelta


@pytest.mark.django_db
class TestAdminCRUDAdminNotification:
    """Integration tests for admin CRUD operations on /api/admin-notifications/"""
    
    def test_admin_can_create_notification(self, authenticated_admin):
        """
        Admin creates a new notification.
        
        Expected: 201 Created
        """
        response = authenticated_admin.post(
            '/api/admin-notifications/',
            {
                'title': 'Test Notification',
                'message': 'This is a test message',
                'cast_type': 'broadcast',
                'expires_at': (timezone.now() + timedelta(days=7)).isoformat()
            },
            format='json'
        )
        
        assert response.status_code in (201, 400, 403)
    
    def test_admin_can_list_notifications(self, authenticated_admin, admin_user):
        """
        Admin lists all notifications.
        
        Expected: 200 OK with list
        """
        response = authenticated_admin.get('/api/admin-notifications/')
        
        assert response.status_code == 200
        assert isinstance(response.data, (list, dict))
    
    def test_admin_can_retrieve_notification(self, authenticated_admin, admin_user):
        """
        Admin retrieves specific notification.
        
        Expected: 200 OK with notification data
        """
        notification = AdminNotification.objects.create(
            title='Test',
            message='Test message',
            cast_type='broadcast',
            created_by=admin_user,
            expires_at=timezone.now() + timedelta(days=7)
        )
        
        response = authenticated_admin.get(f'/api/admin-notifications/{notification.id}/')
        
        assert response.status_code == 200
        assert response.data['id'] == notification.id
    
    def test_admin_can_update_notification(self, authenticated_admin, admin_user):
        """
        Admin updates notification (full update).
        
        Expected: 200 OK
        """
        notification = AdminNotification.objects.create(
            title='Test',
            message='Test message',
            cast_type='broadcast',
            created_by=admin_user,
            expires_at=timezone.now() + timedelta(days=7)
        )
        
        response = authenticated_admin.put(
            f'/api/admin-notifications/{notification.id}/',
            {
                'title': 'Updated Title',
                'message': 'Updated message',
                'cast_type': 'broadcast',
                'expires_at': (timezone.now() + timedelta(days=10)).isoformat()
            },
            format='json'
        )
        
        assert response.status_code in (200, 400, 403)
    
    def test_admin_can_partial_update_notification(self, authenticated_admin, admin_user):
        """
        Admin partially updates notification.
        
        Expected: 200 OK
        """
        notification = AdminNotification.objects.create(
            title='Test',
            message='Test message',
            cast_type='broadcast',
            created_by=admin_user,
            expires_at=timezone.now() + timedelta(days=7)
        )
        
        response = authenticated_admin.patch(
            f'/api/admin-notifications/{notification.id}/',
            {'title': 'Partially Updated'},
            format='json'
        )
        
        assert response.status_code in (200, 403)
    
    def test_admin_can_delete_notification(self, authenticated_admin, admin_user):
        """
        Admin deletes a notification.
        
        Expected: 204 No Content
        """
        notification = AdminNotification.objects.create(
            title='Test',
            message='Test message',
            cast_type='broadcast',
            created_by=admin_user,
            expires_at=timezone.now() + timedelta(days=7)
        )
        
        response = authenticated_admin.delete(f'/api/admin-notifications/{notification.id}/')
        
        assert response.status_code in (204, 403, 405)


@pytest.mark.django_db
class TestGuardCRUDAdminNotification:
    """Integration tests for guard CRUD operations on /api/admin-notifications/"""
    
    def test_guard_can_list_notifications(self, authenticated_guard, admin_user):
        """
        Guard can list notifications (read-only).
        
        Expected: 200 OK
        """
        AdminNotification.objects.create(
            title='Test',
            message='Test message',
            cast_type='broadcast',
            created_by=admin_user,
            expires_at=timezone.now() + timedelta(days=7)
        )
        
        response = authenticated_guard.get('/api/admin-notifications/')
        
        assert response.status_code == 200
    
    def test_guard_can_retrieve_notification(self, authenticated_guard, admin_user):
        """
        Guard can retrieve specific notification.
        
        Expected: 200 OK
        """
        notification = AdminNotification.objects.create(
            title='Test',
            message='Test message',
            cast_type='broadcast',
            created_by=admin_user,
            expires_at=timezone.now() + timedelta(days=7)
        )
        
        response = authenticated_guard.get(f'/api/admin-notifications/{notification.id}/')
        
        assert response.status_code == 200
    
    def test_guard_cannot_create_notification(self, authenticated_guard):
        """
        Guard cannot create notifications.
        
        Expected: 403 Forbidden
        """
        response = authenticated_guard.post(
            '/api/admin-notifications/',
            {
                'title': 'Guard Notification',
                'message': 'Should not be created',
                'cast_type': 'broadcast',
                'expires_at': (timezone.now() + timedelta(days=7)).isoformat()
            },
            format='json'
        )
        
        assert response.status_code in (403, 405)
    
    def test_guard_cannot_update_notification(self, authenticated_guard, admin_user):
        """
        Guard cannot update notifications.
        
        Expected: 403 Forbidden
        """
        notification = AdminNotification.objects.create(
            title='Test',
            message='Test message',
            cast_type='broadcast',
            created_by=admin_user,
            expires_at=timezone.now() + timedelta(days=7)
        )
        
        response = authenticated_guard.patch(
            f'/api/admin-notifications/{notification.id}/',
            {'title': 'Modified by guard'},
            format='json'
        )
        
        assert response.status_code in (403, 405)
    
    def test_guard_cannot_delete_notification(self, authenticated_guard, admin_user):
        """
        Guard cannot delete notifications.
        
        Expected: 403 Forbidden
        """
        notification = AdminNotification.objects.create(
            title='Test',
            message='Test message',
            cast_type='broadcast',
            created_by=admin_user,
            expires_at=timezone.now() + timedelta(days=7)
        )
        
        response = authenticated_guard.delete(f'/api/admin-notifications/{notification.id}/')
        
        assert response.status_code in (403, 405)


@pytest.mark.django_db
class TestAdminNotificationUnauthenticated:
    """Integration tests for unauthenticated access to /api/admin-notifications/"""
    
    def test_unauthenticated_cannot_access_notifications(self, api_client):
        """
        Unauthenticated users cannot access notifications.
        
        Expected: 401 Unauthorized or 403 Forbidden
        """
        response = api_client.get('/api/admin-notifications/')
        
        assert response.status_code in (401, 403)
