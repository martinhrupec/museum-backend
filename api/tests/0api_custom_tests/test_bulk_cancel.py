"""
Integration tests for bulk_cancel endpoint.

Tests:
- POST /api/position-history/bulk-cancel/
- Guard can bulk cancel their positions
- Only first position incurs penalty
- Admin CANNOT use bulk cancel
- Validation rules
"""
import pytest
from django.utils import timezone
from datetime import timedelta


@pytest.mark.django_db
class TestAdminBulkCancel:
    """Integration tests verifying admin CANNOT use POST /api/position-history/bulk-cancel/"""
    
    def test_admin_cannot_bulk_cancel(
        self,
        authenticated_admin,
        guard_user,
        next_week_position,
        next_week_afternoon_position
    ):
        """
        Admin attempting to use bulk cancel should be rejected.
        
        This is a guard-only action.
        
        Expected:
        - 403 Forbidden
        """
        from api.api_models import PositionHistory
        
        # Assign positions to guard
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
        
        response = authenticated_admin.post(
            '/api/position-history/bulk-cancel/',
            {
                'start_date': str(next_week_position.date),
                'end_date': str(next_week_afternoon_position.date)
            },
            format='json'
        )
        
        assert response.status_code == 403
        assert 'administrator' in str(response.data).lower() or 'guard' in str(response.data).lower()


@pytest.mark.django_db
class TestGuardBulkCancel:
    """Integration tests for guard using POST /api/position-history/bulk-cancel/"""
    
    def test_guard_can_bulk_cancel_next_week_positions(
        self,
        authenticated_guard,
        guard_user,
        next_week_position,
        next_week_afternoon_position,
        mock_after_manual_window
    ):
        """
        Guard can bulk cancel their next_week positions after manual window ends.
        
        Only first position should incur penalty.
        
        Expected:
        - 200 response
        - All positions cancelled
        - Penalty applied only to first position
        """
        from api.api_models import PositionHistory, Point
        
        # Assign positions to guard
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
        
        # Record initial point count
        initial_point_count = Point.objects.filter(guard=guard_user.guard).count()
        
        response = authenticated_guard.post(
            '/api/position-history/bulk-cancel/',
            {
                'start_date': str(next_week_position.date),
                'end_date': str(next_week_afternoon_position.date)
            },
            format='json'
        )
        
        assert response.status_code == 200
        assert response.data['cancelled_count'] == 2
        assert 'penalty_applied' in response.data
        
        # Verify penalty was applied only once
        final_point_count = Point.objects.filter(guard=guard_user.guard).count()
        assert final_point_count == initial_point_count + 1
        
        # Verify positions are cancelled
        for position in [next_week_position, next_week_afternoon_position]:
            position.refresh_from_db()
            latest = position.position_histories.order_by('-action_time', '-id').first()
            assert latest.action == PositionHistory.Action.CANCELLED
    
    def test_guard_bulk_cancel_before_manual_window_ends_fails(
        self,
        authenticated_guard,
        guard_user,
        next_week_position,
        next_week_afternoon_position,
        mock_manual_window_open
    ):
        """
        Guard cannot bulk cancel next_week positions before manual window ends.
        
        Expected:
        - 400 or 200 but no penalty applied (depends on implementation)
        """
        from api.api_models import PositionHistory
        
        # Assign positions to guard
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
        
        response = authenticated_guard.post(
            '/api/position-history/bulk-cancel/',
            {
                'start_date': str(next_week_position.date),
                'end_date': str(next_week_afternoon_position.date)
            },
            format='json'
        )
        
        # Bulk cancel can succeed but penalty not applied if manual window not ended
        if response.status_code == 200:
            # No penalty should be applied
            assert response.data['penalty_applied'] is None
        else:
            # Or endpoint might reject the action
            assert response.status_code in (400, 403)
    
    def test_guard_cannot_bulk_cancel_other_guards_positions(
        self,
        authenticated_guard,
        guard_user,
        second_guard_user,
        next_week_position,
        next_week_afternoon_position,
        mock_after_manual_window
    ):
        """
        Guard cannot bulk cancel positions assigned to another guard.
        
        Expected:
        - 400 (no assigned positions found)
        """
        from api.api_models import PositionHistory
        
        # Assign positions to SECOND guard (not authenticated guard)
        PositionHistory.objects.create(
            position=next_week_position,
            guard=second_guard_user.guard,
            action=PositionHistory.Action.ASSIGNED
        )
        PositionHistory.objects.create(
            position=next_week_afternoon_position,
            guard=second_guard_user.guard,
            action=PositionHistory.Action.ASSIGNED
        )
        
        response = authenticated_guard.post(
            '/api/position-history/bulk-cancel/',
            {
                'start_date': str(next_week_position.date),
                'end_date': str(next_week_afternoon_position.date)
            },
            format='json'
        )
        
        assert response.status_code == 400
        assert 'no assigned position' in str(response.data).lower()
    
    def test_bulk_cancel_with_invalid_date_range_fails(
        self,
        authenticated_guard,
        guard_user,
        mock_after_manual_window
    ):
        """
        Bulk cancel with start_date > end_date should fail.
        
        Expected:
        - 400 Bad Request
        """
        response = authenticated_guard.post(
            '/api/position-history/bulk-cancel/',
            {
                'start_date': '2026-01-20',
                'end_date': '2026-01-15'
            },
            format='json'
        )
        
        assert response.status_code == 400
        assert 'start_date' in str(response.data).lower() or 'before' in str(response.data).lower()
    
    def test_bulk_cancel_with_missing_dates_fails(
        self,
        authenticated_guard,
        guard_user,
        mock_after_manual_window
    ):
        """
        Bulk cancel without start_date or end_date should fail.
        
        Expected:
        - 400 Bad Request
        """
        # Missing end_date
        response1 = authenticated_guard.post(
            '/api/position-history/bulk-cancel/',
            {'start_date': '2026-01-15'},
            format='json'
        )
        assert response1.status_code == 400
        
        # Missing start_date
        response2 = authenticated_guard.post(
            '/api/position-history/bulk-cancel/',
            {'end_date': '2026-01-20'},
            format='json'
        )
        assert response2.status_code == 400
    
    def test_bulk_cancel_with_invalid_date_format_fails(
        self,
        authenticated_guard,
        guard_user,
        mock_after_manual_window
    ):
        """
        Bulk cancel with invalid date format should fail.
        
        Expected:
        - 400 Bad Request
        """
        response = authenticated_guard.post(
            '/api/position-history/bulk-cancel/',
            {
                'start_date': '15-01-2026',  # Wrong format
                'end_date': '20/01/2026'     # Wrong format
            },
            format='json'
        )
        
        assert response.status_code == 400
        assert 'invalid' in str(response.data).lower() or 'format' in str(response.data).lower()
    
    def test_bulk_cancel_with_no_assigned_positions_fails(
        self,
        authenticated_guard,
        guard_user,
        next_week_position,
        mock_after_manual_window
    ):
        """
        Bulk cancel when guard has no assigned positions in range should fail.
        
        Expected:
        - 400 Bad Request
        """
        # Don't assign any positions
        
        response = authenticated_guard.post(
            '/api/position-history/bulk-cancel/',
            {
                'start_date': str(next_week_position.date),
                'end_date': str(next_week_position.date)
            },
            format='json'
        )
        
        assert response.status_code == 400
        assert 'no assigned position' in str(response.data).lower()
    
    def test_bulk_cancel_without_authentication_fails(
        self,
        api_client
    ):
        """
        Bulk cancel without authentication fails.
        
        Expected:
        - 401 or 403 response
        """
        response = api_client.post(
            '/api/position-history/bulk-cancel/',
            {
                'start_date': '2026-01-15',
                'end_date': '2026-01-20'
            },
            format='json'
        )
        
        assert response.status_code in (401, 403)
    
    def test_bulk_cancel_only_next_week_during_manual_window_no_penalty(
        self,
        authenticated_guard,
        guard_user,
        next_week_position,
        next_week_afternoon_position,
        mock_manual_window_open,
        system_settings
    ):
        """
        Guard bulk cancels ONLY next_week positions DURING manual window = NO penalty.
        
        Expected:
        - 200 response
        - All positions cancelled
        - NO penalty applied
        """
        from api.api_models import PositionHistory, Point
        
        # Assign next_week positions to guard
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
        
        # Record initial point count
        initial_point_count = Point.objects.filter(guard=guard_user.guard).count()
        
        response = authenticated_guard.post(
            '/api/position-history/bulk-cancel/',
            {
                'start_date': str(next_week_position.date),
                'end_date': str(next_week_afternoon_position.date)
            },
            format='json'
        )
        
        assert response.status_code == 200
        assert response.data['cancelled_count'] == 2
        assert response.data['penalty_applied'] is None  # NO penalty
        
        # Verify NO penalty was applied
        final_point_count = Point.objects.filter(guard=guard_user.guard).count()
        assert final_point_count == initial_point_count  # Same count
    
    def test_bulk_cancel_mix_this_week_and_next_week_always_penalty(
        self,
        authenticated_guard,
        guard_user,
        sample_exhibition,
        next_week_position,
        mock_manual_window_open,
        system_settings
    ):
        """
        Guard bulk cancels MIX of this_week + next_week = ALWAYS penalty (even in manual window).
        
        Expected:
        - 200 response
        - All positions cancelled
        - Penalty applied to first position
        """
        from api.api_models import PositionHistory, Point, Position
        from datetime import timedelta
        
        # Create this_week position that is AFTER mocked time
        # Mock time is Thursday 10:00, so create position for next day (Friday)
        this_week_date = mock_manual_window_open.date() + timedelta(days=1)
        this_week_position = Position.objects.create(
            exhibition=sample_exhibition,
            date=this_week_date,
            start_time=system_settings.weekday_morning_start,
            end_time=system_settings.weekday_morning_end
        )
        
        # Assign both this_week and next_week positions
        PositionHistory.objects.create(
            position=this_week_position,
            guard=guard_user.guard,
            action=PositionHistory.Action.ASSIGNED
        )
        PositionHistory.objects.create(
            position=next_week_position,
            guard=guard_user.guard,
            action=PositionHistory.Action.ASSIGNED
        )
        
        # Record initial point count
        initial_point_count = Point.objects.filter(guard=guard_user.guard).count()
        
        response = authenticated_guard.post(
            '/api/position-history/bulk-cancel/',
            {
                'start_date': str(this_week_position.date),
                'end_date': str(next_week_position.date)
            },
            format='json'
        )
        
        assert response.status_code == 200
        assert response.data['cancelled_count'] == 2
        assert response.data['penalty_applied'] is not None  # Penalty applied
        
        # Verify penalty was applied
        final_point_count = Point.objects.filter(guard=guard_user.guard).count()
        assert final_point_count == initial_point_count + 1
    
    def test_bulk_cancel_only_next_week_after_manual_window_penalty(
        self,
        authenticated_guard,
        guard_user,
        next_week_position,
        next_week_afternoon_position,
        mock_after_manual_window,
        system_settings
    ):
        """
        Guard bulk cancels ONLY next_week positions AFTER manual window = PENALTY.
        
        Expected:
        - 200 response
        - All positions cancelled
        - Penalty applied
        """
        from api.api_models import PositionHistory, Point
        
        # Assign next_week positions
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
        
        # Record initial point count
        initial_point_count = Point.objects.filter(guard=guard_user.guard).count()
        
        response = authenticated_guard.post(
            '/api/position-history/bulk-cancel/',
            {
                'start_date': str(next_week_position.date),
                'end_date': str(next_week_afternoon_position.date)
            },
            format='json'
        )
        
        assert response.status_code == 200
        assert response.data['cancelled_count'] == 2
        assert response.data['penalty_applied'] is not None  # Penalty applied
        
        # Verify penalty was applied
        final_point_count = Point.objects.filter(guard=guard_user.guard).count()
        assert final_point_count == initial_point_count + 1

