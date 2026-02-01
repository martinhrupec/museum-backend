"""
Integration tests for assigning positions via API.

Tests:
- Admin assigning guards to positions (requires guard_id)
- Guard self-assigning to positions
- Validation rules and permissions
"""
import pytest
from api.api_models import Position, PositionHistory


@pytest.mark.django_db
class TestAdminAssignPosition:
    """Integration tests for admin using POST /api/position-history/{id}/assign/"""
    
    def test_admin_can_assign_guard_to_position(
        self,
        authenticated_admin,
        guard_user,
        next_week_position,
        mock_manual_window_open
    ):
        """
        Admin successfully assigns specific guard to position.
        
        Admins must provide guard_id in request body.
        
        Expected:
        - 201 Created response
        - PositionHistory created with ASSIGNED action
        - Correct guard assigned
        """
        response = authenticated_admin.post(
            f'/api/position-history/{next_week_position.id}/assign/',
            {'guard_id': guard_user.guard.id},
            format='json'
        )
        
        assert response.status_code == 201
        assert response.data['message'] == 'Position successfully assigned.'
        
        # Verify correct guard was assigned
        history = PositionHistory.objects.filter(position=next_week_position).first()
        assert history is not None
        assert history.guard == guard_user.guard
        assert history.action == PositionHistory.Action.ASSIGNED
    
    def test_admin_can_assign_different_guards_to_multiple_positions(
        self,
        authenticated_admin,
        guard_user,
        second_guard_user,
        next_week_position,
        next_week_afternoon_position,
        mock_manual_window_open
    ):
        """
        Admin can assign different guards to different positions.
        """
        # Assign guard1 to morning position
        response1 = authenticated_admin.post(
            f'/api/position-history/{next_week_position.id}/assign/',
            {'guard_id': guard_user.guard.id},
            format='json'
        )
        assert response1.status_code == 201
        
        # Assign guard2 to afternoon position
        response2 = authenticated_admin.post(
            f'/api/position-history/{next_week_afternoon_position.id}/assign/',
            {'guard_id': second_guard_user.guard.id},
            format='json'
        )
        assert response2.status_code == 201
        
        # Verify both assignments
        history1 = PositionHistory.objects.filter(position=next_week_position).first()
        history2 = PositionHistory.objects.filter(position=next_week_afternoon_position).first()
        
        assert history1.guard == guard_user.guard
        assert history2.guard == second_guard_user.guard
    
    def test_admin_missing_guard_id_fails(
        self,
        authenticated_admin,
        next_week_position,
        mock_manual_window_open
    ):
        """
        Admin must provide guard_id when assigning.
        
        Expected:
        - 400 Bad Request
        - Error about missing guard_id
        """
        response = authenticated_admin.post(
            f'/api/position-history/{next_week_position.id}/assign/',
            {},  # No guard_id
            format='json'
        )
        
        assert response.status_code == 400
        assert 'guard_id' in str(response.data).lower()
    
    def test_admin_cannot_assign_inactive_guard(
        self,
        authenticated_admin,
        inactive_user,
        next_week_position,
        mock_manual_window_open
    ):
        """
        Admin cannot assign inactive guard to position.
        
        Expected:
        - 400 Bad Request
        - Error about guard being inactive
        """
        response = authenticated_admin.post(
            f'/api/position-history/{next_week_position.id}/assign/',
            {'guard_id': inactive_user.guard.id},
            format='json'
        )
        
        assert response.status_code == 400
        assert 'not active' in str(response.data).lower()
    
    def test_admin_cannot_assign_to_already_taken_position(
        self,
        authenticated_admin,
        guard_user,
        assigned_position,
        mock_manual_window_open
    ):
        """
        Admin cannot assign guard to position that's already taken.
        
        Expected:
        - 409 Conflict
        - Error about position being taken
        """
        position, _ = assigned_position
        
        response = authenticated_admin.post(
            f'/api/position-history/{position.id}/assign/',
            {'guard_id': guard_user.guard.id},
            format='json'
        )
        
        assert response.status_code == 409
        assert 'already taken' in response.data['error'].lower()
    
    def test_admin_cannot_assign_guard_with_time_conflict(
        self,
        authenticated_admin,
        guard_user,
        sample_exhibition,
        system_settings,
        mock_manual_window_open
    ):
        """
        Admin cannot assign guard to overlapping positions.
        
        Scenario:
        - Guard already assigned to 14:00-19:00
        - Admin tries to assign same guard to 18:00-21:00 (overlaps)
        
        Expected:
        - 409 Conflict
        - Error about time conflict
        """
        from datetime import time
        
        position1 = Position.objects.create(
            exhibition=sample_exhibition,
            date=system_settings.next_week_start,
            start_time=time(14, 0),
            end_time=time(19, 0)
        )
        position2 = Position.objects.create(
            exhibition=sample_exhibition,
            date=system_settings.next_week_start,
            start_time=time(18, 0),
            end_time=time(21, 0)
        )
        
        # Assign guard to first position
        PositionHistory.objects.create(
            position=position1,
            guard=guard_user.guard,
            action=PositionHistory.Action.ASSIGNED
        )
        
        # Try to assign same guard to overlapping position
        response = authenticated_admin.post(
            f'/api/position-history/{position2.id}/assign/',
            {'guard_id': guard_user.guard.id},
            format='json'
        )
        
        assert response.status_code == 409
        assert 'time conflict' in response.data['error'].lower()
        assert 'conflicting_position' in response.data


@pytest.mark.django_db
class TestGuardAssignPosition:
    """Integration tests for guard using POST /api/position-history/{id}/assign/"""
    
    def test_guard_can_self_assign_to_position(
        self,
        authenticated_guard,
        guard_user,
        next_week_position,
        mock_manual_window_open
    ):
        """
        Guard successfully assigns themselves to available position.
        
        Guards don't need to provide guard_id - they're auto-assigned.
        
        Expected:
        - 201 Created response
        - PositionHistory created with ASSIGNED action
        """
        response = authenticated_guard.post(
            f'/api/position-history/{next_week_position.id}/assign/',
            {},  # No guard_id needed for self-assignment
            format='json'
        )
        
        assert response.status_code == 201
        assert response.data['message'] == 'Position successfully assigned.'
        
        # Verify guard was assigned
        history = PositionHistory.objects.filter(position=next_week_position).first()
        assert history is not None
        assert history.guard == guard_user.guard
        assert history.action == PositionHistory.Action.ASSIGNED
    
    def test_guard_can_assign_to_multiple_non_overlapping_positions(
        self,
        authenticated_guard,
        guard_user,
        next_week_position,
        next_week_afternoon_position,
        mock_manual_window_open
    ):
        """
        Guard can assign to multiple positions on same day if no time overlap.
        
        Expected:
        - Both assignments succeed
        """
        # Assign to morning position
        response1 = authenticated_guard.post(
            f'/api/position-history/{next_week_position.id}/assign/',
            {},
            format='json'
        )
        assert response1.status_code == 201
        
        # Assign to afternoon position (no overlap)
        response2 = authenticated_guard.post(
            f'/api/position-history/{next_week_afternoon_position.id}/assign/',
            {},
            format='json'
        )
        assert response2.status_code == 201
    
    def test_guard_cannot_assign_to_already_taken_position(
        self,
        authenticated_guard,
        assigned_position,
        mock_manual_window_open
    ):
        """
        Guard cannot assign to position already taken by another guard.
        
        Expected:
        - 409 Conflict
        """
        position, _ = assigned_position
        
        response = authenticated_guard.post(
            f'/api/position-history/{position.id}/assign/',
            {},
            format='json'
        )
        
        assert response.status_code == 409
        assert 'already taken' in response.data['error'].lower()
    
    def test_guard_cannot_assign_with_time_conflict(
        self,
        authenticated_guard,
        guard_user,
        sample_exhibition,
        system_settings,
        mock_manual_window_open
    ):
        """
        Guard cannot assign to overlapping positions.
        
        Expected:
        - 409 Conflict with time conflict error
        """
        from datetime import time
        
        position1 = Position.objects.create(
            exhibition=sample_exhibition,
            date=system_settings.next_week_start,
            start_time=time(14, 0),
            end_time=time(19, 0)
        )
        position2 = Position.objects.create(
            exhibition=sample_exhibition,
            date=system_settings.next_week_start,
            start_time=time(18, 0),
            end_time=time(21, 0)
        )
        
        # Assign to first position
        response1 = authenticated_guard.post(
            f'/api/position-history/{position1.id}/assign/',
            {},
            format='json'
        )
        assert response1.status_code == 201
        
        # Try to assign to overlapping position
        response2 = authenticated_guard.post(
            f'/api/position-history/{position2.id}/assign/',
            {},
            format='json'
        )
        
        assert response2.status_code == 409
        assert 'time conflict' in response2.data['error'].lower()
    
    def test_guard_can_replace_cancelled_position(
        self,
        authenticated_guard,
        guard_user,
        cancelled_position,
        mock_manual_window_open
    ):
        """
        Guard can assign to position that was previously cancelled.
        
        Expected:
        - 201 Created
        - Action is REPLACED (not ASSIGNED)
        """
        position, _ = cancelled_position
        
        response = authenticated_guard.post(
            f'/api/position-history/{position.id}/assign/',
            {},
            format='json'
        )
        
        assert response.status_code == 201
        
        # Get the newest history by id (highest id = most recently created)
        history = PositionHistory.objects.filter(position=position).order_by('-id').first()
        assert history.action == PositionHistory.Action.REPLACED
    
    def test_assign_without_authentication_fails(self, api_client, next_week_position, system_settings):
        """
        Assigning without authentication fails.
        
        Expected:
        - 401 or 403 response
        """
        response = api_client.post(
            f'/api/position-history/{next_week_position.id}/assign/',
            {},
            format='json'
        )
        
        assert response.status_code in (401, 403)