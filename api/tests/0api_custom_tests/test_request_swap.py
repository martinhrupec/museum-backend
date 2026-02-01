"""
Integration tests for request_swap endpoint.

Tests:
- Guard can request position swap
- Admin CANNOT request swaps (guard-only)
- Validation rules
"""
import pytest
from django.utils import timezone
from datetime import timedelta


@pytest.mark.django_db
class TestAdminRequestSwap:
    """Integration tests verifying admin CANNOT use POST /api/positions/{id}/request_swap/"""
    
    def test_admin_cannot_request_swap(
        self,
        authenticated_admin,
        guard_user,
        next_week_position
    ):
        """
        Admin attempting to request position swap should be rejected.
        
        This is a guard-only action.
        
        Expected:
        - 403 Forbidden
        """
        from api.api_models import PositionHistory
        
        # Assign position
        PositionHistory.objects.create(
            position=next_week_position,
            guard=guard_user.guard,
            action=PositionHistory.Action.ASSIGNED
        )
        
        response = authenticated_admin.post(
            f'/api/positions/{next_week_position.id}/request_swap/',
            {},
            format='json'
        )
        
        assert response.status_code == 403


@pytest.mark.django_db
class TestGuardRequestSwap:
    """Integration tests for guard using POST /api/positions/{id}/request_swap/"""
    
    def test_guard_can_request_swap_for_own_position(
        self,
        authenticated_guard,
        guard_user,
        next_week_position,
        mock_after_manual_window,
        system_settings
    ):
        """
        Guard can create swap request for their assigned position.
        
        Expected:
        - 200 or 201 response
        """
        from api.api_models import PositionHistory, GuardWorkPeriod
        
        # Assign position
        PositionHistory.objects.create(
            position=next_week_position,
            guard=guard_user.guard,
            action=PositionHistory.Action.ASSIGNED
        )
        
        # Set up work periods (required for swap)
        guard_user.guard.availability = 2
        guard_user.guard.save()
        GuardWorkPeriod.objects.create(
            guard=guard_user.guard,
            day_of_week=0,
            shift_type='morning',
            is_template=True
        )
        
        response = authenticated_guard.post(
            f'/api/positions/{next_week_position.id}/request_swap/',
            {},
            format='json'
        )
        
        assert response.status_code in (200, 201)
    
    def test_guard_cannot_request_swap_for_unassigned_position(
        self,
        authenticated_guard,
        guard_user,
        next_week_position,
        mock_after_manual_window
    ):
        """
        Guard cannot request swap for position they're not assigned to.
        
        Expected:
        - 403 Forbidden
        """
        from api.api_models import GuardWorkPeriod, PositionHistory
        
        # Set up work periods (required to pass work_period check)
        guard_user.guard.availability = 1
        guard_user.guard.save()
        GuardWorkPeriod.objects.create(
            guard=guard_user.guard,
            day_of_week=0,
            shift_type='morning',
            is_template=True
        )
        
        # Ensure position has NO assignment history (or assigned to someone else)
        PositionHistory.objects.filter(position=next_week_position).delete()
        
        response = authenticated_guard.post(
            f'/api/positions/{next_week_position.id}/request_swap/',
            {},
            format='json'
        )
        print('DEBUG swap response:', response.status_code, response.data)
        assert response.status_code == 403
    
    def test_guard_cannot_request_swap_for_other_guards_position(
        self,
        authenticated_guard,
        guard_user,
        second_guard_user,
        next_week_position,
        mock_after_manual_window
    ):
        """
        Guard cannot request swap for position assigned to another guard.
        
        Expected:
        - 403 Forbidden
        """
        from api.api_models import PositionHistory, GuardWorkPeriod
        
        # Set up work periods for authenticated guard
        guard_user.guard.availability = 1
        guard_user.guard.save()
        GuardWorkPeriod.objects.create(
            guard=guard_user.guard,
            day_of_week=0,
            shift_type='morning',
            is_template=True
        )
        
        # Assign to second guard
        PositionHistory.objects.create(
            position=next_week_position,
            guard=second_guard_user.guard,
            action=PositionHistory.Action.ASSIGNED
        )
        
        response = authenticated_guard.post(
            f'/api/positions/{next_week_position.id}/request_swap/',
            {},
            format='json'
        )
        
        assert response.status_code == 403
    
    def test_guard_cannot_have_multiple_active_swap_requests(
        self,
        authenticated_guard,
        guard_user,
        next_week_position,
        next_week_afternoon_position,
        mock_after_manual_window,
        system_settings
    ):
        """
        Guard cannot have more than one active swap request.
        
        Expected:
        - 400 Bad Request for second request
        """
        from api.api_models import PositionHistory, PositionSwapRequest, GuardWorkPeriod
        
        # Assign positions
        PositionHistory.objects.create(
            position=next_week_position,
            guard=guard_user.guard,
            action=PositionHistory.Action.ASSIGNED
        )
        PositionHistory.objects.create(
            position=next_week_afternoon_position,
            guard=guard_user.guard,
            action=PositionHistory.Action.ASSIGNED
        )
        
        # Set up work periods
        guard_user.guard.availability = 2
        guard_user.guard.save()
        GuardWorkPeriod.objects.create(
            guard=guard_user.guard,
            day_of_week=0,
            shift_type='morning',
            is_template=True
        )
        
        # Create first swap request
        PositionSwapRequest.objects.create(
            requesting_guard=guard_user.guard,
            position_to_swap=next_week_position,
            status='pending',
            expires_at=timezone.now() + timedelta(days=1)
        )
        
        # Try to create second swap request
        response = authenticated_guard.post(
            f'/api/positions/{next_week_afternoon_position.id}/request_swap/',
            {},
            format='json'
        )
        
        assert response.status_code == 400
        assert 'active swap request' in str(response.data).lower() or 'already' in str(response.data).lower()
    
    def test_guard_without_work_periods_cannot_request_swap(
        self,
        authenticated_guard,
        guard_user,
        next_week_position,
        mock_after_manual_window
    ):
        """
        Guard must have work_periods configured to request swap.
        
        Expected:
        - 400 Bad Request
        """
        from api.api_models import PositionHistory
        
        # Assign position
        PositionHistory.objects.create(
            position=next_week_position,
            guard=guard_user.guard,
            action=PositionHistory.Action.ASSIGNED
        )
        
        response = authenticated_guard.post(
            f'/api/positions/{next_week_position.id}/request_swap/',
            {},
            format='json'
        )
        
        assert response.status_code == 400
        assert 'work period' in str(response.data).lower()
    
    def test_request_swap_without_authentication_fails(
        self, api_client, next_week_position
    ):
        """
        Requesting swap without authentication fails.
        
        Expected:
        - 401 or 403 response
        """
        response = api_client.post(
            f'/api/positions/{next_week_position.id}/request_swap/',
            {},
            format='json'
        )
        
        assert response.status_code in (401, 403)
