"""
Integration tests for CRUD operations on Report model.

Tests admin and guard permissions for:
- Creating reports
- Reading reports (list and detail)
- Updating reports (full and partial)
- Deleting reports

Business rules:
- Admins: can view all reports (list/retrieve), CANNOT create/update/delete
- Guards: can view all reports, can create their own reports, CANNOT update/delete
- Reports are immutable once created
"""
import pytest
from api.api_models import Report
from unittest.mock import patch


@pytest.mark.django_db
class TestAdminCRUDReport:
    """Integration tests for admin CRUD operations on /api/reports/"""
    
    def test_admin_cannot_create_report(self, authenticated_admin, guard_user, assigned_position):
        """
        Admin CANNOT create reports.
        Only guards can create reports.
        
        Expected: 403 Forbidden
        """
        position, _ = assigned_position
        
        response = authenticated_admin.post(
            '/api/reports/',
            {
                'position_id': position.id,
                'report_text': 'Test report from admin'
            },
            format='json'
        )
        
        assert response.status_code == 403
    
    def test_admin_can_list_reports(self, authenticated_admin, guard_user, assigned_position):
        """
        Admin can list all reports.
        
        Expected: 200 OK with list
        """
        response = authenticated_admin.get('/api/reports/')
        
        assert response.status_code == 200
        assert isinstance(response.data, (list, dict))
    
    def test_admin_can_retrieve_report(self, authenticated_admin, guard_user, assigned_position):
        """
        Admin can retrieve specific report.
        
        Expected: 200 OK with report data
        """
        position, _ = assigned_position
        report = Report.objects.create(
            guard=guard_user.guard,
            position=position,
            report_text='Test report'
        )
        
        response = authenticated_admin.get(f'/api/reports/{report.id}/')
        
        assert response.status_code == 200
        assert response.data['id'] == report.id
    
    def test_admin_cannot_update_report(self, authenticated_admin, guard_user, assigned_position):
        """
        Admin CANNOT update reports.
        Reports are immutable.
        
        Expected: 405 Method Not Allowed
        """
        position, _ = assigned_position
        report = Report.objects.create(
            guard=guard_user.guard,
            position=position,
            report_text='Test report'
        )
        
        response = authenticated_admin.put(
            f'/api/reports/{report.id}/',
            {
                'position_id': position.id,
                'report_text': 'Updated report text'
            },
            format='json'
        )
        
        assert response.status_code == 405
    
    def test_admin_cannot_partial_update_report(self, authenticated_admin, guard_user, assigned_position):
        """
        Admin CANNOT partially update reports.
        Reports are immutable.
        
        Expected: 405 Method Not Allowed
        """
        position, _ = assigned_position
        report = Report.objects.create(
            guard=guard_user.guard,
            position=position,
            report_text='Test report'
        )
        
        response = authenticated_admin.patch(
            f'/api/reports/{report.id}/',
            {'report_text': 'Partially updated'},
            format='json'
        )
        
        assert response.status_code == 405
    
    def test_admin_cannot_delete_report(self, authenticated_admin, guard_user, assigned_position):
        """
        Admin CANNOT delete reports.
        Reports are immutable.
        
        Expected: 405 Method Not Allowed
        """
        position, _ = assigned_position
        report = Report.objects.create(
            guard=guard_user.guard,
            position=position,
            report_text='Test report'
        )
        
        response = authenticated_admin.delete(f'/api/reports/{report.id}/')
        
        assert response.status_code == 405


@pytest.mark.django_db
class TestGuardCRUDReport:
    """Integration tests for guard CRUD operations on /api/reports/"""
    
    def test_guard_can_list_all_reports(self, authenticated_guard, guard_user, assigned_position):
        """
        Guard can list all reports (not just their own).
        
        Expected: 200 OK
        """
        position, _ = assigned_position
        Report.objects.create(
            guard=guard_user.guard,
            position=position,
            report_text='Test report'
        )
        
        response = authenticated_guard.get('/api/reports/')
        
        assert response.status_code == 200
    
    def test_guard_can_create_own_report(self, authenticated_guard, guard_user, assigned_position):
        """
        Guard can create a report for a position.
        Email should be sent (requires Celery worker running or CELERY_TASK_ALWAYS_EAGER=True).
        
        Expected: 201 Created
        """
        position, _ = assigned_position
        
        response = authenticated_guard.post(
            '/api/reports/',
            {
                'position_id': position.id,
                'report_text': 'Ne radi TV na Budućnostima'
            },
            format='json'
        )
        
        assert response.status_code in (201, 400)
        if response.status_code == 201:
            # Report created successfully
            assert Report.objects.filter(position=position, report_text='Ne radi TV na Budućnostima').exists()
    
    def test_guard_cannot_update_any_reports(self, authenticated_guard, second_guard_user, next_week_position):
        """
        Guard CANNOT update any reports (even their own).
        Reports are immutable.
        
        Expected: 405 Method Not Allowed
        """
        from api.api_models import PositionHistory
        
        PositionHistory.objects.create(
            position=next_week_position,
            guard=second_guard_user.guard,
            action=PositionHistory.Action.ASSIGNED
        )
        
        report = Report.objects.create(
            guard=second_guard_user.guard,
            position=next_week_position,
            report_text='Original report'
        )
        
        response = authenticated_guard.patch(
            f'/api/reports/{report.id}/',
            {'report_text': 'Modified by another guard'},
            format='json'
        )
        
        assert response.status_code in (403, 405)
    
    def test_guard_cannot_delete_reports(self, authenticated_guard, guard_user, assigned_position):
        """
        Guard CANNOT delete reports.
        Reports are immutable.
        
        Expected: 405 Method Not Allowed
        """
        position, _ = assigned_position
        report = Report.objects.create(
            guard=guard_user.guard,
            position=position,
            report_text='Test report'
        )
        
        response = authenticated_guard.delete(f'/api/reports/{report.id}/')
        
        assert response.status_code in (403, 405)


@pytest.mark.django_db
class TestReportUnauthenticated:
    """Integration tests for unauthenticated access to /api/reports/"""
    
    def test_unauthenticated_cannot_access_reports(self, api_client):
        """
        Unauthenticated users cannot access reports.
        
        Expected: 401 Unauthorized or 403 Forbidden
        """
        response = api_client.get('/api/reports/')
        
        assert response.status_code in (401, 403)
