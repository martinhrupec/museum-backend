"""
Integration tests for report_lateness endpoint.

Tests:
- Guard can report their own lateness
- Admin CANNOT report lateness (guard-only)
- Validation rules
"""
import pytest
from django.utils import timezone
from datetime import time


@pytest.mark.django_db
class TestAdminReportLateness:
    """Integration tests verifying admin CANNOT use POST /api/position-history/{id}/report-lateness/"""
    
    def test_admin_cannot_report_lateness(
        self,
        authenticated_admin,
        guard_user,
        sample_exhibition,
        system_settings
    ):
        """
        Admin attempting to report lateness should be rejected.
        
        This is a guard-only action.
        
        Expected:
        - 403 Forbidden
        """
        from api.api_models import Position, PositionHistory
        
        # Create today's position
        today = timezone.now().date()
        position = Position.objects.create(
            exhibition=sample_exhibition,
            date=today,
            start_time=time(9, 0),
            end_time=time(14, 0)
        )
        
        # Assign to guard
        PositionHistory.objects.create(
            position=position,
            guard=guard_user.guard,
            action=PositionHistory.Action.ASSIGNED
        )
        
        response = authenticated_admin.post(
            f'/api/position-history/{position.id}/report-lateness/',
            {
                'estimated_delay_minutes': 15
            },
            format='json'
        )
        
        assert response.status_code == 403
        assert 'admin' in str(response.data).lower() or 'čuvar' in str(response.data).lower()


@pytest.mark.django_db
class TestGuardReportLateness:
    """Integration tests for guard using POST /api/position-history/{id}/report-lateness/"""
    
    def test_guard_can_report_own_lateness(
        self,
        authenticated_guard,
        guard_user,
        sample_exhibition,
        system_settings
    ):
        """
        Guard successfully reports being late to their position.
        
        Expected:
        - 200 response
        - Penalty applied
        """
        from api.api_models import Position, PositionHistory, Point
        
        today = timezone.now().date()
        position = Position.objects.create(
            exhibition=sample_exhibition,
            date=today,
            start_time=time(9, 0),
            end_time=time(14, 0)
        )
        
        # Assign to guard
        PositionHistory.objects.create(
            position=position,
            guard=guard_user.guard,
            action=PositionHistory.Action.ASSIGNED
        )
        
        initial_points = Point.objects.filter(guard=guard_user.guard).count()
        
        response = authenticated_guard.post(
            f'/api/position-history/{position.id}/report-lateness/',
            {
                'estimated_delay_minutes': 15
            },
            format='json'
        )
        
        assert response.status_code in (200, 201)
        
        # Verify penalty point was created
        final_points = Point.objects.filter(guard=guard_user.guard).count()
        assert final_points > initial_points
    
    def test_guard_cannot_report_lateness_for_other_guards_position(
        self,
        authenticated_guard,
        second_guard_user,
        sample_exhibition,
        system_settings
    ):
        """
        Guard cannot report lateness for position assigned to another guard.
        
        Expected:
        - 403 Forbidden
        """
        from api.api_models import Position, PositionHistory
        
        today = timezone.now().date()
        position = Position.objects.create(
            exhibition=sample_exhibition,
            date=today,
            start_time=time(9, 0),
            end_time=time(14, 0)
        )
        
        # Assign to second guard
        PositionHistory.objects.create(
            position=position,
            guard=second_guard_user.guard,
            action=PositionHistory.Action.ASSIGNED
        )
        
        response = authenticated_guard.post(
            f'/api/position-history/{position.id}/report-lateness/',
            {
                'estimated_delay_minutes': 15
            },
            format='json'
        )
        
        assert response.status_code == 403
    
    def test_guard_cannot_report_lateness_for_past_position(
        self,
        authenticated_guard,
        guard_user,
        sample_exhibition,
        system_settings
    ):
        """
        Guard cannot report lateness for position from another day.
        
        Expected:
        - 400 Bad Request
        """
        from api.api_models import Position, PositionHistory
        from datetime import timedelta
        
        yesterday = timezone.now().date() - timedelta(days=1)
        position = Position.objects.create(
            exhibition=sample_exhibition,
            date=yesterday,
            start_time=time(9, 0),
            end_time=time(14, 0)
        )
        
        # Assign to guard
        PositionHistory.objects.create(
            position=position,
            guard=guard_user.guard,
            action=PositionHistory.Action.ASSIGNED
        )
        
        response = authenticated_guard.post(
            f'/api/position-history/{position.id}/report-lateness/',
            {
                'estimated_delay_minutes': 15
            },
            format='json'
        )
        
        assert response.status_code == 400
        assert 'today' in str(response.data).lower()
    
    def test_guard_cannot_report_lateness_for_unassigned_position(
        self,
        authenticated_guard,
        sample_exhibition,
        system_settings
    ):
        """
        Guard cannot report lateness for position they're not assigned to.
        
        Expected:
        - 400 Bad Request
        """
        from api.api_models import Position
        
        today = timezone.now().date()
        position = Position.objects.create(
            exhibition=sample_exhibition,
            date=today,
            start_time=time(9, 0),
            end_time=time(14, 0)
        )
        
        response = authenticated_guard.post(
            f'/api/position-history/{position.id}/report-lateness/',
            {
                'estimated_delay_minutes': 15
            },
            format='json'
        )
        
        assert response.status_code == 400
    
    def test_report_lateness_without_authentication_fails(
        self, api_client, next_week_position
    ):
        """
        Reporting lateness without authentication fails.
        
        Expected:
        - 401 or 403 response
        """
        response = api_client.post(
            f'/api/position-history/{next_week_position.id}/report-lateness/',
            {
                'estimated_delay_minutes': 15
            },
            format='json'
        )
        
        assert response.status_code in (401, 403)
