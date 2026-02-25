"""
Tests for overlap handling in assignment algorithm.

Ensures guards cannot be assigned to overlapping positions
(same time slot on different exhibitions).
"""
import pytest
from datetime import date, time, timedelta
from decimal import Decimal

from api.api_models import (
    User, Guard, Exhibition, Position, PositionHistory, SystemSettings,
    GuardWorkPeriod
)
from background_tasks.assignment_algorithm import (
    positions_overlap,
    build_overlap_groups,
    assign_positions_automatically
)


class TestPositionsOverlap:
    """Unit tests for positions_overlap function."""
    
    def test_same_day_same_time_overlaps(self):
        """Positions at same date and time overlap."""
        class MockPosition:
            def __init__(self, d, start, end):
                self.date = d
                self.start_time = start
                self.end_time = end
        
        day = date(2024, 3, 10)  # Sunday
        pos1 = MockPosition(day, time(9, 0), time(13, 0))
        pos2 = MockPosition(day, time(9, 0), time(13, 0))
        
        assert positions_overlap(pos1, pos2) is True
    
    def test_same_day_partial_overlap(self):
        """Positions that partially overlap should be detected."""
        class MockPosition:
            def __init__(self, d, start, end):
                self.date = d
                self.start_time = start
                self.end_time = end
        
        day = date(2024, 3, 10)
        pos1 = MockPosition(day, time(9, 0), time(13, 0))
        pos2 = MockPosition(day, time(12, 0), time(16, 0))  # Starts before pos1 ends
        
        assert positions_overlap(pos1, pos2) is True
    
    def test_same_day_no_overlap(self):
        """Morning and afternoon positions don't overlap."""
        class MockPosition:
            def __init__(self, d, start, end):
                self.date = d
                self.start_time = start
                self.end_time = end
        
        day = date(2024, 3, 10)
        pos1 = MockPosition(day, time(9, 0), time(13, 0))  # Morning
        pos2 = MockPosition(day, time(14, 0), time(18, 0))  # Afternoon
        
        assert positions_overlap(pos1, pos2) is False
    
    def test_different_days_no_overlap(self):
        """Same time but different days don't overlap."""
        class MockPosition:
            def __init__(self, d, start, end):
                self.date = d
                self.start_time = start
                self.end_time = end
        
        pos1 = MockPosition(date(2024, 3, 10), time(9, 0), time(13, 0))
        pos2 = MockPosition(date(2024, 3, 11), time(9, 0), time(13, 0))
        
        assert positions_overlap(pos1, pos2) is False
    
    def test_adjacent_positions_no_overlap(self):
        """Positions that touch at boundary don't overlap."""
        class MockPosition:
            def __init__(self, d, start, end):
                self.date = d
                self.start_time = start
                self.end_time = end
        
        day = date(2024, 3, 10)
        pos1 = MockPosition(day, time(9, 0), time(13, 0))
        pos2 = MockPosition(day, time(13, 0), time(17, 0))  # Starts exactly when pos1 ends
        
        assert positions_overlap(pos1, pos2) is False


class TestBuildOverlapGroups:
    """Unit tests for build_overlap_groups function."""
    
    def test_no_overlaps_returns_empty(self):
        """Non-overlapping positions return empty overlap map."""
        class MockPosition:
            def __init__(self, d, start, end):
                self.date = d
                self.start_time = start
                self.end_time = end
        
        day = date(2024, 3, 10)
        positions = [
            MockPosition(day, time(9, 0), time(13, 0)),   # Morning
            MockPosition(day, time(14, 0), time(18, 0)),  # Afternoon
        ]
        
        overlap_map = build_overlap_groups(positions)
        
        # No overlaps - map should be empty
        assert len(overlap_map) == 0
    
    def test_two_overlapping_positions(self):
        """Two overlapping positions are mapped to each other."""
        class MockPosition:
            def __init__(self, d, start, end):
                self.date = d
                self.start_time = start
                self.end_time = end
        
        day = date(2024, 3, 10)
        positions = [
            MockPosition(day, time(9, 0), time(13, 0)),
            MockPosition(day, time(9, 0), time(13, 0)),  # Same time - overlaps
        ]
        
        overlap_map = build_overlap_groups(positions)
        
        assert 0 in overlap_map
        assert 1 in overlap_map[0]
        assert 1 in overlap_map
        assert 0 in overlap_map[1]
    
    def test_three_overlapping_positions(self):
        """Three positions at same time all overlap with each other."""
        class MockPosition:
            def __init__(self, d, start, end):
                self.date = d
                self.start_time = start
                self.end_time = end
        
        day = date(2024, 3, 10)
        positions = [
            MockPosition(day, time(9, 0), time(13, 0)),
            MockPosition(day, time(9, 0), time(13, 0)),
            MockPosition(day, time(9, 0), time(13, 0)),
        ]
        
        overlap_map = build_overlap_groups(positions)
        
        # All three overlap with each other
        assert overlap_map[0] == {1, 2}
        assert overlap_map[1] == {0, 2}
        assert overlap_map[2] == {0, 1}
    
    def test_mixed_overlapping_and_non_overlapping(self):
        """Mix of overlapping and non-overlapping positions."""
        class MockPosition:
            def __init__(self, d, start, end):
                self.date = d
                self.start_time = start
                self.end_time = end
        
        day = date(2024, 3, 10)
        positions = [
            MockPosition(day, time(9, 0), time(13, 0)),   # 0: Morning - overlaps with 1
            MockPosition(day, time(9, 0), time(13, 0)),   # 1: Morning - overlaps with 0
            MockPosition(day, time(14, 0), time(18, 0)),  # 2: Afternoon - no overlap
        ]
        
        overlap_map = build_overlap_groups(positions)
        
        assert overlap_map[0] == {1}
        assert overlap_map[1] == {0}
        assert 2 not in overlap_map  # No overlaps for afternoon position


@pytest.mark.django_db
class TestOverlapFilteringIntegration:
    """Integration tests for overlap filtering in full assignment process."""
    
    @pytest.fixture
    def settings_with_sunday(self, db):
        """Create settings configured for a week including Sunday."""
        today = date.today()
        # Find next Sunday
        days_until_sunday = (6 - today.weekday()) % 7 or 7
        next_sunday = today + timedelta(days=days_until_sunday)
        next_monday = next_sunday - timedelta(days=6)
        
        return SystemSettings.objects.create(
            this_week_start=next_monday - timedelta(days=7),
            this_week_end=next_sunday - timedelta(days=7),
            next_week_start=next_monday,
            next_week_end=next_sunday,
            workdays=[0, 1, 2, 3, 4, 5, 6],  # All days including Sunday
            weekend_morning_start=time(9, 0),
            weekend_morning_end=time(13, 0),
            weekend_afternoon_start=time(14, 0),
            weekend_afternoon_end=time(18, 0),
            weekday_morning_start=time(8, 0),
            weekday_morning_end=time(12, 0),
            weekday_afternoon_start=time(13, 0),
            weekday_afternoon_end=time(17, 0),
            minimal_number_of_positions_in_week=1,
            points_life_weeks=4,
        )
    
    @pytest.fixture
    def guard_with_high_availability(self, db, settings_with_sunday):
        """Create a guard with availability for multiple positions."""
        user = User.objects.create(
            username='overlap_test_guard',
            email='overlap@test.com',
            password='testpass123'
        )
        guard = Guard.objects.create(
            user=user,
            availability=3,  # Can work 3 positions
            priority_number=Decimal('10.0')
        )
        
        # Add work period for Sunday morning
        next_sunday = settings_with_sunday.next_week_end
        GuardWorkPeriod.objects.create(
            guard=guard,
            day_of_week=6,  # Sunday
            shift_type='morning',
            next_week_start=settings_with_sunday.next_week_start
        )
        
        return guard
    
    @pytest.fixture
    def two_exhibitions_same_time(self, db, settings_with_sunday):
        """Create two exhibitions with positions at the same time on Sunday."""
        next_sunday = settings_with_sunday.next_week_end
        
        exhibition_a = Exhibition.objects.create(
            name='Exhibition A',
            number_of_positions=1,
            start_date=settings_with_sunday.next_week_start,
            end_date=settings_with_sunday.next_week_end + timedelta(days=30),
            open_on=[6],  # Sunday
        )
        
        exhibition_b = Exhibition.objects.create(
            name='Exhibition B',
            number_of_positions=1,
            start_date=settings_with_sunday.next_week_start,
            end_date=settings_with_sunday.next_week_end + timedelta(days=30),
            open_on=[6],  # Sunday
        )
        
        # Create positions at same time on Sunday morning
        pos_a = Position.objects.create(
            exhibition=exhibition_a,
            date=next_sunday,
            start_time=time(9, 0),
            end_time=time(13, 0)
        )
        
        pos_b = Position.objects.create(
            exhibition=exhibition_b,
            date=next_sunday,
            start_time=time(9, 0),
            end_time=time(13, 0)
        )
        
        return exhibition_a, exhibition_b, pos_a, pos_b
    
    def test_algorithm_prevents_overlapping_assignment(
        self, settings_with_sunday, guard_with_high_availability, two_exhibitions_same_time
    ):
        """
        Test that the assignment algorithm does not assign same guard
        to two overlapping positions.
        
        This is the bug scenario: guard available Sunday morning,
        two exhibitions with positions Sunday morning.
        Guard should only be assigned to ONE of them.
        
        With the new implementation, overlap constraints are built into the matrix,
        so Hungarski algorithm naturally assigns each overlapping position to a 
        different guard's slot, and if only one guard exists, one position remains
        unassigned (filtered as -9999).
        """
        exhibition_a, exhibition_b, pos_a, pos_b = two_exhibitions_same_time
        
        # Run automated assignment
        result = assign_positions_automatically(settings_with_sunday)
        
        assert result['status'] == 'success'
        
        # Check that guard was assigned to only ONE position
        guard_assignments = PositionHistory.objects.filter(
            guard=guard_with_high_availability,
            action=PositionHistory.Action.ASSIGNED
        )
        
        # Guard should have exactly 1 assignment (not 2!)
        assert guard_assignments.count() == 1, (
            f"Guard should have 1 assignment but has {guard_assignments.count()}. "
            f"This indicates the overlap constraint is not working!"
        )
        
        # With the new approach, one position should remain unassigned
        # because the matrix constraint prevents same guard from getting both
        assert result['positions_remaining'] >= 1, (
            "Expected at least one position to remain (overlap prevented assignment)"
        )

    @pytest.fixture
    def second_guard(self, db, settings_with_sunday):
        """Create a second guard that can also work Sunday morning."""
        user = User.objects.create(
            username='overlap_test_guard_2',
            email='overlap2@test.com',
            password='testpass123'
        )
        guard = Guard.objects.create(
            user=user,
            availability=2,
            priority_number=Decimal('8.0')  # Lower priority than first guard
        )
        
        # Add work period for Sunday morning
        GuardWorkPeriod.objects.create(
            guard=guard,
            day_of_week=6,  # Sunday
            shift_type='morning',
            next_week_start=settings_with_sunday.next_week_start
        )
        
        return guard

    def test_two_guards_both_positions_filled(
        self, settings_with_sunday, guard_with_high_availability, 
        second_guard, two_exhibitions_same_time
    ):
        """
        Test that with two guards available, both overlapping positions get filled.
        
        This is the key improvement: instead of leaving one position empty,
        the algorithm assigns each overlapping position to a different guard.
        """
        exhibition_a, exhibition_b, pos_a, pos_b = two_exhibitions_same_time
        
        # Run automated assignment
        result = assign_positions_automatically(settings_with_sunday)
        
        assert result['status'] == 'success'
        
        # Both positions should be assigned
        assert result['assignments_created'] == 2, (
            f"Expected 2 assignments but got {result['assignments_created']}. "
            f"Both guards should be assigned to different positions."
        )
        
        # No positions should remain
        assert result['positions_remaining'] == 0, (
            "Both overlapping positions should be filled by different guards"
        )
        
        # Verify each guard got exactly one position
        guard1_assignments = PositionHistory.objects.filter(
            guard=guard_with_high_availability,
            action=PositionHistory.Action.ASSIGNED
        )
        guard2_assignments = PositionHistory.objects.filter(
            guard=second_guard,
            action=PositionHistory.Action.ASSIGNED
        )
        
        assert guard1_assignments.count() == 1
        assert guard2_assignments.count() == 1
        
        # Make sure they're on different positions
        pos1 = guard1_assignments.first().position
        pos2 = guard2_assignments.first().position
        assert pos1 != pos2, "Guards should be assigned to different positions"
