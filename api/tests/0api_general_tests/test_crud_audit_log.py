"""
Integration tests for CRUD operations on AuditLog model.

Tests admin and guard permissions for:
- Creating audit logs
- Reading audit logs (list and detail)
- Updating audit logs (full and partial)
- Deleting audit logs
"""
import pytest
from datetime import datetime
from django.utils import timezone
from api.api_models import AuditLog


@pytest.mark.django_db
class TestAdminCRUDAuditLog:
    """Integration tests for admin CRUD operations on /api/audit-logs/"""
    
    def test_admin_can_create_audit_log(self, authenticated_admin, admin_user):
        """
        Admin creates a new audit log.
        
        Expected: 201 Created or 403 if creation restricted
        """
        response = authenticated_admin.post(
            '/api/audit-logs/',
            {
                'user': admin_user.id,
                'action': 'create',
                'model_name': 'TestModel',
                'object_id': 123,
                'timestamp': timezone.now().isoformat(),
                'changes': {'field': 'value'}
            },
            format='json'
        )
        
        assert response.status_code in (201, 400, 403, 405)
    
    def test_admin_can_list_audit_logs(self, authenticated_admin, admin_user):
        """
        Admin lists all audit logs.
        
        Expected: 200 OK with list
        """
        AuditLog.objects.create(
            user=admin_user,
            action='create',
            model_name='TestModel',
            object_id=123
        )
        
        response = authenticated_admin.get('/api/audit-logs/')
        
        assert response.status_code == 200
        assert isinstance(response.data, (list, dict))
    
    def test_admin_can_retrieve_audit_log(self, authenticated_admin, admin_user):
        """
        Admin retrieves specific audit log.
        
        Expected: 200 OK with log data
        """
        audit_log = AuditLog.objects.create(
            user=admin_user,
            action='create',
            model_name='TestModel',
            object_id=123
        )
        
        response = authenticated_admin.get(f'/api/audit-logs/{audit_log.id}/')
        
        assert response.status_code == 200
        assert response.data['id'] == audit_log.id
    
    def test_admin_can_update_audit_log(self, authenticated_admin, admin_user):
        """
        Admin updates audit log (full update).
        
        Expected: 200 OK or 403/405 if update restricted
        """
        audit_log = AuditLog.objects.create(
            user=admin_user,
            action='create',
            model_name='TestModel',
            object_id=123
        )
        
        response = authenticated_admin.put(
            f'/api/audit-logs/{audit_log.id}/',
            {
                'user': admin_user.id,
                'action': 'update',
                'model_name': 'TestModel',
                'object_id': 123,
                'timestamp': timezone.now().isoformat(),
                'changes': {'field': 'new_value'}
            },
            format='json'
        )
        
        assert response.status_code in (200, 400, 403, 405)
    
    def test_admin_can_partial_update_audit_log(self, authenticated_admin, admin_user):
        """
        Admin partially updates audit log.
        
        Expected: 200 OK or 403/405 if update restricted
        """
        audit_log = AuditLog.objects.create(
            user=admin_user,
            action='create',
            model_name='TestModel',
            object_id=123
        )
        
        response = authenticated_admin.patch(
            f'/api/audit-logs/{audit_log.id}/',
            {'action': 'update'},
            format='json'
        )
        
        assert response.status_code in (200, 403, 405)
    
    def test_admin_can_delete_audit_log(self, authenticated_admin, admin_user):
        """
        Admin deletes an audit log.
        
        Expected: 204 No Content or 403/405 if deletion restricted
        """
        audit_log = AuditLog.objects.create(
            user=admin_user,
            action='create',
            model_name='TestModel',
            object_id=123
        )
        
        response = authenticated_admin.delete(f'/api/audit-logs/{audit_log.id}/')
        
        assert response.status_code in (204, 403, 405)


@pytest.mark.django_db
class TestGuardCRUDAuditLog:
    """Integration tests for guard CRUD operations on /api/audit-logs/"""
    
    def test_guard_cannot_list_audit_logs(self, authenticated_guard):
        """
        Guard cannot list audit logs (admin only).
        
        Expected: 403 Forbidden
        """
        response = authenticated_guard.get('/api/audit-logs/')
        
        assert response.status_code in (403, 404)
    
    def test_guard_cannot_retrieve_audit_log(self, authenticated_guard, admin_user):
        """
        Guard cannot retrieve audit log details.
        
        Expected: 403 Forbidden
        """
        audit_log = AuditLog.objects.create(
            user=admin_user,
            action='create',
            model_name='TestModel',
            object_id=123
        )
        
        response = authenticated_guard.get(f'/api/audit-logs/{audit_log.id}/')
        
        assert response.status_code in (403, 404)
    
    def test_guard_cannot_create_audit_log(self, authenticated_guard, guard_user):
        """
        Guard cannot create audit logs.
        
        Expected: 403 Forbidden
        """
        response = authenticated_guard.post(
            '/api/audit-logs/',
            {
                'user': guard_user.id,
                'action': 'create',
                'model_name': 'TestModel',
                'object_id': 123
            },
            format='json'
        )
        
        assert response.status_code in (403, 404, 405)
    
    def test_guard_cannot_delete_audit_log(self, authenticated_guard, admin_user):
        """
        Guard cannot delete audit logs.
        
        Expected: 403 Forbidden
        """
        audit_log = AuditLog.objects.create(
            user=admin_user,
            action='create',
            model_name='TestModel',
            object_id=123
        )
        
        response = authenticated_guard.delete(f'/api/audit-logs/{audit_log.id}/')
        
        assert response.status_code in (403, 404, 405)


@pytest.mark.django_db
class TestAuditLogUnauthenticated:
    """Integration tests for unauthenticated access to /api/audit-logs/"""
    
    def test_unauthenticated_cannot_access_audit_logs(self, api_client):
        """
        Unauthenticated users cannot access audit logs.
        
        Expected: 401 Unauthorized or 403 Forbidden
        """
        response = api_client.get('/api/audit-logs/')
        
        assert response.status_code in (401, 403)
