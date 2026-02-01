"""
Integration tests for cancel position endpoint.

Tests:
- Admin can cancel guard's position assignment (requires guard_id)
- Guard can cancel their own position assignment
- Validation rules and permissions
"""
import pytest
from api.api_models import PositionHistory


@pytest.mark.django_db
class TestAdminCancelPosition:
    """Integration tests for admin using POST /api/position-history/{id}/cancel/"""
    
    def test_admin_can_cancel_assigned_position(
        self,
        authenticated_admin,
        assigned_position,
        guard_user,
        mock_manual_window_open
    ):
        """
        Admin successfully cancels an assigned position.
        
        Expected:
        - 200 or 201 OK response
        - PositionHistory created with CANCELLED action
        """
        position, history = assigned_position
        
        response = authenticated_admin.post(
            f'/api/position-history/{position.id}/cancel/',
            {'guard_id': guard_user.guard.id},
            format='json'
        )
        
        assert response.status_code in (200, 201)
        assert 'message' in response.data
        
        # Verify CANCELLED history entry (use -id for deterministic ordering)
        latest_history = PositionHistory.objects.filter(position=position).order_by('-id').first()
        assert latest_history is not None
        assert latest_history.action == PositionHistory.Action.CANCELLED
    
    def test_admin_cancel_requires_guard_id(self, authenticated_admin, assigned_position, mock_manual_window_open):
        """
        Admin must provide guard_id when cancelling.
        
        Expected:
        - 400 response
        """
        position, _ = assigned_position
        
        response = authenticated_admin.post(
            f'/api/position-history/{position.id}/cancel/',
            {},
            format='json'
        )
        
        assert response.status_code == 400
        assert 'guard_id' in str(response.data).lower()
    
    def test_admin_cannot_cancel_unassigned_position(
        self,
        authenticated_admin,
        guard_user,
        next_week_position,
        mock_manual_window_open
    ):
        """
        Admin cannot cancel position that's not assigned.
        
        Expected:
        - 400 response
        """
        response = authenticated_admin.post(
            f'/api/position-history/{next_week_position.id}/cancel/',
            {'guard_id': guard_user.guard.id},
            format='json'
        )
        
        assert response.status_code == 400
        error_msg = str(response.data).lower()
        assert 'not' in error_msg and 'assigned' in error_msg
    
    def test_admin_cannot_cancel_position_that_started(
        self,
        authenticated_admin,
        guard_user,
        sample_exhibition,
        system_settings
    ):
        """
        Admin cannot cancel position that already started.
        
        Expected:
        - 400 response
        """
        from datetime import time, timedelta
        from django.utils import timezone
        from api.api_models import Position
        
        # Create position in the past
        past_date = timezone.now().date() - timedelta(days=1)
        position = Position.objects.create(
            exhibition=sample_exhibition,
            date=past_date,
            start_time=time(10, 0),
            end_time=time(14, 0)
        )
        
        # Assign it
        PositionHistory.objects.create(
            position=position,
            guard=guard_user.guard,
            action=PositionHistory.Action.ASSIGNED
        )
        
        response = authenticated_admin.post(
            f'/api/position-history/{position.id}/cancel/',
            {'guard_id': guard_user.guard.id},
            format='json'
        )
        
        assert response.status_code == 400
        error_msg = str(response.data).lower()
        # API may say 'started', 'past', 'scheduling window', etc.
        assert any(word in error_msg for word in ['started', 'past', 'window', 'cannot'])


@pytest.mark.django_db
class TestGuardCancelPosition:
    """Integration tests for guard using POST /api/position-history/{id}/cancel/"""
    
    def test_guard_can_cancel_own_assigned_position(
        self,
        authenticated_guard,
        guard_user,
        next_week_position,
        mock_manual_window_open
    ):
        """
        Guard successfully cancels their own assigned position.
        
        Expected:
        - 200 or 201 response
        - PositionHistory created with CANCELLED action
        """
        # Assign position to guard first
        PositionHistory.objects.create(
            position=next_week_position,
            guard=guard_user.guard,
            action=PositionHistory.Action.ASSIGNED
        )
        
        response = authenticated_guard.post(
            f'/api/position-history/{next_week_position.id}/cancel/',
            {},  # No guard_id needed for self-cancel
            format='json'
        )
        
        assert response.status_code in (200, 201)
        assert 'message' in response.data
        
        # Verify CANCELLED history entry
        latest_history = PositionHistory.objects.filter(
            position=next_week_position
        ).order_by('-action_time', '-id').first()
        assert latest_history.action == PositionHistory.Action.CANCELLED
    
    def test_guard_cannot_cancel_other_guards_position(
        self,
        authenticated_guard,
        second_guard_user,
        next_week_position,
        mock_manual_window_open
    ):
        """
        Guard cannot cancel position assigned to another guard.
        
        Expected:
        - 403 Forbidden
        """
        # Assign position to second guard
        PositionHistory.objects.create(
            position=next_week_position,
            guard=second_guard_user.guard,
            action=PositionHistory.Action.ASSIGNED
        )
        
        response = authenticated_guard.post(
            f'/api/position-history/{next_week_position.id}/cancel/',
            {},
            format='json'
        )
        
        assert response.status_code == 403
    
    def test_guard_cannot_cancel_unassigned_position(
        self,
        authenticated_guard,
        next_week_position,
        mock_manual_window_open
    ):
        """
        Guard cannot cancel position that's not assigned.
        
        Expected:
        - 400 Bad Request
        """
        response = authenticated_guard.post(
            f'/api/position-history/{next_week_position.id}/cancel/',
            {},
            format='json'
        )
        
        assert response.status_code == 400
    
    def test_guard_cancel_applies_penalty(
        self,
        authenticated_guard,
        guard_user,
        next_week_position,
        mock_manual_window_open
    ):
        """
        Cancelling a next_week position applies penalty.
        
        Expected:
        - penalty_applied in response or 400 if cancellation rules prevent it
        """
        from api.api_models import Point
        
        # Assign position
        PositionHistory.objects.create(
            position=next_week_position,
            guard=guard_user.guard,
            action=PositionHistory.Action.ASSIGNED
        )
        
        initial_points = Point.objects.filter(guard=guard_user.guard).count()
        
        response = authenticated_guard.post(
            f'/api/position-history/{next_week_position.id}/cancel/',
            {},
            format='json'
        )
        
        # If 400 returned, it may be due to timing constraints or position not in cancellable window
        assert response.status_code in (200, 201, 400)
        
        # Verify penalty was applied
        final_points = Point.objects.filter(guard=guard_user.guard).count()
        assert final_points > initial_points or 'penalty_applied' in response.data
    
    def test_cancel_without_authentication_fails(self, api_client, next_week_position, system_settings):
        """
        Cancelling without authentication fails.
        
        Expected:
        - 401 or 403 response
        """
        response = api_client.post(
            f'/api/position-history/{next_week_position.id}/cancel/',
            {},
            format='json'
        )
        
        assert response.status_code in (401, 403)