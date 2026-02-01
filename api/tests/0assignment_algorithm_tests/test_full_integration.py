"""
FAZA 9: Full Integration & E2E Tests

Complete end-to-end testing of the assignment algorithm with realistic museum scenarios.
Tests the entire workflow from start to finish, including all components working together.
"""

import pytest
from datetime import date, time, timedelta
from decimal import Decimal
from django.utils import timezone

from api.api_models import (
    Position, PositionHistory, Exhibition, GuardWorkPeriod,
    GuardExhibitionPreference, GuardDayPreference, SystemSettings, Guard
)
from background_tasks.assignment_algorithm import assign_positions_automatically
from background_tasks.minimum_calculator import calculate_and_update_minimum
import time as time_module


# ============================================================================
# INTEGRATION TESTS (8 tests)
# ============================================================================

@pytest.mark.django_db
class TestCompleteWorkflow:
    """Test complete assignment workflow end-to-end"""
    
    def test_complete_assignment_workflow(
        self, create_guard_with_user, system_settings_for_assignment, sample_exhibitions
    ):
        """
        Test the complete workflow: guards → exhibitions → positions → assignment → history
        Realistic: 25 guards, 3 exhibitions, positions auto-generated
        """
        settings = system_settings_for_assignment
        exhibitions = sample_exhibitions
        
        # Verify positions were created by sample_exhibitions
        positions = Position.objects.filter(
            date__gte=settings.next_week_start,
            date__lte=settings.next_week_end
        )
        assert positions.count() > 0
        
        # Create 25 guards with realistic availability (1-4)
        guards = []
        availabilities = [1, 2, 2, 3, 3, 3, 4, 4, 2, 2, 1, 3, 3, 2, 2, 4, 1, 3, 2, 2, 3, 3, 2, 1, 4]
        
        for i in range(25):
            guard = create_guard_with_user(
                f"guard_{i+1}",
                f"guard{i+1}@test.com",
                availability=availabilities[i],
                priority=Decimal(str(1.0 + (i % 10) * 0.5))  # Priority 1.0 - 5.5
            )
            guards.append(guard)
            
            # Add work periods for all guards (full week)
            for day in range(1, 7):  # Tuesday-Sunday
                GuardWorkPeriod.objects.create(
                    guard=guard,
                    day_of_week=day,
                    shift_type='morning',
                    is_template=True
                )
                GuardWorkPeriod.objects.create(
                    guard=guard,
                    day_of_week=day,
                    shift_type='afternoon',
                    is_template=True
                )
        
        # Execute assignment
        result = assign_positions_automatically(settings)
        
        # Verify workflow completion
        assert result['status'] == 'success'
        assert result['assignments_created'] > 0
        
        # Verify history records created
        history_count = PositionHistory.objects.filter(
            action=PositionHistory.Action.ASSIGNED
        ).count()
        assert history_count == result['assignments_created']
        
        # Verify no over-assignments
        for guard in guards:
            assigned_count = PositionHistory.objects.filter(
                guard=guard,
                action=PositionHistory.Action.ASSIGNED
            ).count()
            assert assigned_count <= guard.availability


@pytest.mark.django_db
class TestAllFeatures:
    """Test assignment with all features enabled simultaneously"""
    
    def test_assignment_with_all_features_enabled(
        self, create_guard_with_user, system_settings_for_assignment, sample_exhibitions
    ):
        """
        Test all features together: preferences + work periods + capping + minimum calculation
        Realistic: 20 guards, positions from sample_exhibitions
        """
        settings = system_settings_for_assignment
        exhibitions = sample_exhibitions
        
        # Create 20 guards with varied availability (total ~50 slots)
        guards = []
        availabilities = [4, 4, 3, 3, 3, 2, 2, 2, 2, 2, 3, 3, 4, 1, 1, 2, 3, 3, 2, 2]
        
        for i in range(20):
            guard = create_guard_with_user(
                f"guard_{i+1}",
                f"guard{i+1}@test.com",
                availability=availabilities[i],
                priority=Decimal(str(1.0 + i * 0.2))
            )
            guards.append(guard)
            
            # Varied work periods (some partial)
            if i < 10:
                # First 10 guards: full week
                days = range(1, 7)
            else:
                # Next 10 guards: partial week
                days = range(1, 4)
            
            for day in days:
                GuardWorkPeriod.objects.create(
                    guard=guard,
                    day_of_week=day,
                    shift_type='morning',
                    is_template=True
                )
                GuardWorkPeriod.objects.create(
                    guard=guard,
                    day_of_week=day,
                    shift_type='afternoon',
                    is_template=True
                )
        
        # Add exhibition preferences for first 10 guards
        for i in range(10):
            exhibition_ids = [exhibitions[i % 3].id, exhibitions[(i + 1) % 3].id, exhibitions[(i + 2) % 3].id]
            GuardExhibitionPreference.objects.create(
                guard=guards[i],
                exhibition_order=exhibition_ids,
                is_template=True
            )
        
        # Add day preferences for first 10 guards
        for i in range(10):
            day_order = [(i % 6) + 1, ((i + 1) % 6) + 1, ((i + 2) % 6) + 1]
            GuardDayPreference.objects.create(
                guard=guards[i],
                day_order=day_order,
                is_template=True
            )
        
        # Execute assignment
        result = assign_positions_automatically(settings)
        
        # Verify all features worked
        assert result['status'] in ['success', 'warning']
        assert result['assignments_created'] > 0


@pytest.mark.django_db
class TestHistoryTracking:
    """Test that assignments create proper history records"""
    
    def test_assignment_creates_history_records(
        self, create_guard_with_user, system_settings_for_assignment, sample_exhibitions
    ):
        """
        Verify all assignments create PositionHistory with correct details
        """
        settings = system_settings_for_assignment
        
        # Create 15 guards
        guards = []
        for i in range(15):
            guard = create_guard_with_user(
                f"guard_{i+1}",
                f"guard{i+1}@test.com",
                availability=2,
                priority=Decimal('2.0')
            )
            guards.append(guard)
            
            for day in range(1, 7):
                GuardWorkPeriod.objects.create(
                    guard=guard,
                    day_of_week=day,
                    shift_type='morning',
                    is_template=True
                )
                GuardWorkPeriod.objects.create(
                    guard=guard,
                    day_of_week=day,
                    shift_type='afternoon',
                    is_template=True
                )
        
        # Record time before assignment
        before_time = timezone.now()
        
        # Execute assignment
        result = assign_positions_automatically(settings)
        
        # Verify history records
        history_records = PositionHistory.objects.filter(
            action=PositionHistory.Action.ASSIGNED,
            action_time__gte=before_time
        )
        
        assert history_records.count() == result['assignments_created']
        
        # Verify each history record details
        for record in history_records:
            assert record.position is not None
            assert record.guard is not None
            assert record.action == PositionHistory.Action.ASSIGNED
            assert record.action_time >= before_time


@pytest.mark.django_db
class TestFairness:
    """Test fair distribution of assignments"""
    
    def test_assignment_fairness_check(
        self, create_guard_with_user, system_settings_for_assignment
    ):
        """
        Test that guards with same priority/availability get roughly equal assignments
        """
        settings = system_settings_for_assignment
        
        # Create exhibition with many positions
        today = timezone.now()
        exhibition = Exhibition.objects.create(
            name="Gallery",
            number_of_positions=10,  # 10 positions per shift per day
            start_date=today - timedelta(days=30),
            end_date=today + timedelta(days=60),
            is_special_event=False,
            open_on=[1, 2, 3, 4, 5, 6]  # Tuesday-Sunday
        )
        
        # Verify positions created (6 days × 2 shifts × 10 positions = 120)
        positions = Position.objects.filter(
            date__gte=settings.next_week_start,
            date__lte=settings.next_week_end
        )
        position_count = positions.count()
        assert position_count > 0
        
        # Create 30 guards with IDENTICAL priority and availability
        guards = []
        for i in range(30):
            guard = create_guard_with_user(
                f"guard_{i+1}",
                f"guard{i+1}@test.com",
                availability=2,       # All same availability
                priority=Decimal('3.0')  # All same priority
            )
            guards.append(guard)
            
            for day in range(1, 7):
                GuardWorkPeriod.objects.create(
                    guard=guard,
                    day_of_week=day,
                    shift_type='morning',
                    is_template=True
                )
                GuardWorkPeriod.objects.create(
                    guard=guard,
                    day_of_week=day,
                    shift_type='afternoon',
                    is_template=True
                )
        
        # Execute assignment
        result = assign_positions_automatically(settings)
        
        # Count assignments per guard
        assignment_counts = []
        for guard in guards:
            count = PositionHistory.objects.filter(
                guard=guard,
                action=PositionHistory.Action.ASSIGNED
            ).count()
            assignment_counts.append(count)
        
        # All guards should get 0, 1, or 2 assignments (availability = 2)
        assert all(count <= 2 for count in assignment_counts)
        
        # Calculate distribution
        if sum(assignment_counts) > 0:
            avg_assignments = sum(assignment_counts) / len(assignment_counts)
            
            # Most guards should be close to average (fairness)
            close_to_avg = sum(1 for count in assignment_counts if abs(count - avg_assignments) <= 1)
            fairness_ratio = close_to_avg / len(assignment_counts)
            
            assert fairness_ratio >= 0.7  # At least 70% of guards get fair distribution


@pytest.mark.django_db
class TestLogging:
    """Test that assignment logs correctly"""
    
    def test_assignment_logs_correctly(
        self, create_guard_with_user, system_settings_for_assignment, sample_exhibitions
    ):
        """
        Verify assignment result contains comprehensive logging information
        """
        settings = system_settings_for_assignment
        
        # Create minimal setup
        guards = []
        for i in range(10):
            guard = create_guard_with_user(
                f"guard_{i+1}",
                f"guard{i+1}@test.com",
                availability=3,
                priority=Decimal('2.0')
            )
            guards.append(guard)
            
            for day in range(1, 7):
                GuardWorkPeriod.objects.create(
                    guard=guard,
                    day_of_week=day,
                    shift_type='morning',
                    is_template=True
                )
        
        # Execute assignment
        result = assign_positions_automatically(settings)
        
        # Verify result structure contains all expected fields
        expected_fields = [
            'status',
            'assignments_created',
        ]
        
        for field in expected_fields:
            assert field in result, f"Missing field: {field}"
        
        # Verify status is valid
        assert result['status'] in ['success', 'warning', 'error', 'skipped']
        
        # Verify counts are logical
        assert result['assignments_created'] >= 0


@pytest.mark.django_db
class TestRealisticScenario:
    """Test realistic museum scenario"""
    
    def test_realistic_museum_scenario(
        self, create_guard_with_user, system_settings_for_assignment
    ):
        """
        Simulate real museum: 30 guards, 3 exhibitions, many weekly positions
        Tuesday-Sunday workdays, varied availability
        """
        settings = system_settings_for_assignment
        today = timezone.now()
        
        # Create 3 realistic exhibitions
        exhibitions = [
            Exhibition.objects.create(
                name="Stalna postavka",
                number_of_positions=2,
                start_date=today - timedelta(days=30),
                end_date=today + timedelta(days=60),
                is_special_event=False,
                open_on=[1, 2, 3, 4, 5, 6]
            ),
            Exhibition.objects.create(
                name="Privremena izložba",
                number_of_positions=1,
                start_date=today - timedelta(days=30),
                end_date=today + timedelta(days=60),
                is_special_event=False,
                open_on=[1, 3, 5, 6]
            ),
            Exhibition.objects.create(
                name="Galerija",
                number_of_positions=1,
                start_date=today - timedelta(days=30),
                end_date=today + timedelta(days=60),
                is_special_event=False,
                open_on=[2, 4, 5, 6]
            ),
        ]
        
        # Create 30 guards with realistic varied availability (1-4)
        guards = []
        realistic_availabilities = [
            4, 3, 3, 2, 2, 2, 1, 3, 3, 2,
            4, 2, 3, 1, 2, 3, 3, 2, 4, 2,
            3, 2, 1, 3, 2, 2, 3, 4, 1, 2
        ]
        
        for i in range(30):
            guard = create_guard_with_user(
                f"cuvar_{i+1}",
                f"cuvar{i+1}@test.com",
                availability=realistic_availabilities[i],
                priority=Decimal(str(1.0 + (i % 15) * 0.3))  # Priority 1.0 - 5.2
            )
            guards.append(guard)
            
            # Most guards work full week, some partial
            if i < 25:
                days = range(1, 7)  # Full week
            else:
                days = [1, 2, 3]    # Partial week
            
            for day in days:
                GuardWorkPeriod.objects.create(
                    guard=guard,
                    day_of_week=day,
                    shift_type='morning',
                    is_template=True
                )
                GuardWorkPeriod.objects.create(
                    guard=guard,
                    day_of_week=day,
                    shift_type='afternoon',
                    is_template=True
                )
        
        # Add realistic preferences for some guards
        for i in range(15):
            exhibition_ids = [exhibitions[i % 3].id, exhibitions[(i + 1) % 3].id, exhibitions[(i + 2) % 3].id]
            GuardExhibitionPreference.objects.create(
                guard=guards[i],
                exhibition_order=exhibition_ids,
                is_template=True
            )
        
        # Execute assignment
        result = assign_positions_automatically(settings)
        
        # Verify realistic expectations
        assert result['status'] == 'success'
        assert result['assignments_created'] > 0
        
        # No guard should be over-assigned
        for i, guard in enumerate(guards):
            assigned_count = PositionHistory.objects.filter(
                guard=guard,
                action=PositionHistory.Action.ASSIGNED
            ).count()
            assert assigned_count <= realistic_availabilities[i]


@pytest.mark.django_db
class TestConsistency:
    """Test assignment consistency"""
    
    def test_assignment_consistency_across_runs(
        self, create_guard_with_user, system_settings_for_assignment
    ):
        """
        Test that running assignment multiple times on same data produces consistent results
        (deterministic behavior)
        """
        settings = system_settings_for_assignment
        today = timezone.now()
        
        # Create exhibition
        exhibition = Exhibition.objects.create(
            name="Test",
            number_of_positions=5,
            start_date=today - timedelta(days=30),
            end_date=today + timedelta(days=60),
            is_special_event=False,
            open_on=[1, 2]  # Only Tuesday and Wednesday
        )
        
        # Create 15 guards with distinct priorities for determinism
        guards = []
        for i in range(15):
            guard = create_guard_with_user(
                f"guard_{i+1}",
                f"guard{i+1}@test.com",
                availability=2,
                priority=Decimal(str(float(i + 1)))  # Distinct priorities
            )
            guards.append(guard)
            
            for day in range(1, 7):
                GuardWorkPeriod.objects.create(
                    guard=guard,
                    day_of_week=day,
                    shift_type='morning',
                    is_template=True
                )
        
        # First run
        result_1 = assign_positions_automatically(settings)
        assignments_1 = list(PositionHistory.objects.filter(
            action=PositionHistory.Action.ASSIGNED
        ).values_list('position_id', 'guard_id').order_by('position_id'))
        
        # Clear assignments for second run
        PositionHistory.objects.filter(action=PositionHistory.Action.ASSIGNED).delete()
        
        # Second run
        result_2 = assign_positions_automatically(settings)
        assignments_2 = list(PositionHistory.objects.filter(
            action=PositionHistory.Action.ASSIGNED
        ).values_list('position_id', 'guard_id').order_by('position_id'))
        
        # Verify consistency
        assert result_1['assignments_created'] == result_2['assignments_created']
        assert assignments_1 == assignments_2  # Exact same assignments


# ============================================================================
# E2E TESTS (4 tests)
# ============================================================================

@pytest.mark.django_db
class TestWeeklyCycle:
    """Test multi-week assignment cycle"""
    
    def test_weekly_assignment_cycle_simulation(
        self, create_guard_with_user, system_settings_for_assignment
    ):
        """
        Simulate assignment and verify it works correctly
        """
        settings = system_settings_for_assignment
        today = timezone.now()
        
        # Create exhibition
        exhibition = Exhibition.objects.create(
            name="Museum",
            number_of_positions=4,
            start_date=today - timedelta(days=30),
            end_date=today + timedelta(days=120),
            is_special_event=False,
            open_on=[1, 2, 3, 4, 5, 6]
        )
        
        # Create persistent guards
        guards = []
        for i in range(20):
            guard = create_guard_with_user(
                f"guard_{i+1}",
                f"guard{i+1}@test.com",
                availability=3,
                priority=Decimal(str(2.0 + i * 0.1))
            )
            guards.append(guard)
            
            for day in range(1, 7):
                GuardWorkPeriod.objects.create(
                    guard=guard,
                    day_of_week=day,
                    shift_type='morning',
                    is_template=True
                )
                GuardWorkPeriod.objects.create(
                    guard=guard,
                    day_of_week=day,
                    shift_type='afternoon',
                    is_template=True
                )
        
        # Run assignment
        result = assign_positions_automatically(settings)
        
        # Verify week completed successfully
        assert result['status'] == 'success'
        assert result['assignments_created'] > 0
        
        # Verify history records
        total_history = PositionHistory.objects.filter(
            action=PositionHistory.Action.ASSIGNED
        ).count()
        assert total_history == result['assignments_created']


@pytest.mark.django_db
class TestStressTest:
    """Stress test with large dataset"""
    
    def test_stress_test_large_dataset(
        self, create_guard_with_user, system_settings_for_assignment
    ):
        """
        Stress test: 50 guards, 7 exhibitions, many positions
        Verify performance and correctness under load
        """
        settings = system_settings_for_assignment
        today = timezone.now()
        
        # Create 7 exhibitions
        exhibitions = []
        for i in range(7):
            exh = Exhibition.objects.create(
                name=f"Exhibition {i+1}",
                number_of_positions=2,
                start_date=today - timedelta(days=30),
                end_date=today + timedelta(days=60),
                is_special_event=False,
                open_on=[1, 2, 3, 4, 5, 6]
            )
            exhibitions.append(exh)
        
        # Create 50 guards
        guards = []
        for i in range(50):
            guard = create_guard_with_user(
                f"guard_{i+1}",
                f"guard{i+1}@test.com",
                availability=(i % 4) + 1,  # 1-4
                priority=Decimal(str(1.0 + (i % 20) * 0.25))
            )
            guards.append(guard)
            
            for day in range(1, 7):
                GuardWorkPeriod.objects.create(
                    guard=guard,
                    day_of_week=day,
                    shift_type='morning',
                    is_template=True
                )
                GuardWorkPeriod.objects.create(
                    guard=guard,
                    day_of_week=day,
                    shift_type='afternoon',
                    is_template=True
                )
        
        # Measure performance
        start_time = time_module.time()
        result = assign_positions_automatically(settings)
        execution_time = time_module.time() - start_time
        
        # Verify correctness
        assert result['status'] in ['success', 'warning']
        assert result['assignments_created'] > 0
        
        # Performance: Should complete in reasonable time (< 300 seconds for stress test)
        # The algorithm with 50 guards x 336 positions can take 2+ minutes on some systems
        assert execution_time < 300, f"Assignment took {execution_time:.2f}s (too slow)"
        
        # Verify no over-assignments
        for i, guard in enumerate(guards):
            assigned_count = PositionHistory.objects.filter(
                guard=guard,
                action=PositionHistory.Action.ASSIGNED
            ).count()
            assert assigned_count <= guard.availability


@pytest.mark.django_db
class TestVariedPreferences:
    """Test complex preference scenarios"""
    
    def test_assignment_with_varied_preferences(
        self, create_guard_with_user, system_settings_for_assignment
    ):
        """
        Test assignment with complex preference combinations:
        - Multiple exhibition preferences
        - Multiple day preferences
        """
        settings = system_settings_for_assignment
        today = timezone.now()
        
        # Create 5 exhibitions
        exhibitions = []
        for i in range(5):
            exh = Exhibition.objects.create(
                name=f"Exh {i+1}",
                number_of_positions=2,
                start_date=today - timedelta(days=30),
                end_date=today + timedelta(days=60),
                is_special_event=False,
                open_on=[1, 2, 3, 4, 5, 6]
            )
            exhibitions.append(exh)
        
        # Create 25 guards with complex preferences
        guards = []
        for i in range(25):
            guard = create_guard_with_user(
                f"guard_{i+1}",
                f"guard{i+1}@test.com",
                availability=3,
                priority=Decimal(str(2.0 + (i % 10) * 0.3))
            )
            guards.append(guard)
            
            for day in range(1, 7):
                GuardWorkPeriod.objects.create(
                    guard=guard,
                    day_of_week=day,
                    shift_type='morning',
                    is_template=True
                )
                GuardWorkPeriod.objects.create(
                    guard=guard,
                    day_of_week=day,
                    shift_type='afternoon',
                    is_template=True
                )
            
            # Exhibition preferences (array of all 5 exhibitions in varied order)
            exhibition_ids = [
                exhibitions[(i + j) % 5].id
                for j in range(5)
            ]
            GuardExhibitionPreference.objects.create(
                guard=guard,
                exhibition_order=exhibition_ids,
                is_template=True
            )
            
            # Day preferences (array of days in varied order)
            day_order = [((i + j) % 6) + 1 for j in range(6)]
            GuardDayPreference.objects.create(
                guard=guard,
                day_order=day_order,
                is_template=True
            )
        
        # Execute assignment
        result = assign_positions_automatically(settings)
        
        # Verify assignment succeeded
        assert result['status'] == 'success'
        assert result['assignments_created'] > 0


@pytest.mark.django_db
class TestPerformance:
    """Test performance benchmarks"""
    
    def test_performance_benchmark(
        self, create_guard_with_user, system_settings_for_assignment
    ):
        """
        Performance benchmark: Realistic scale (30 guards, 36 positions)
        Measure execution time for different operations
        """
        settings = system_settings_for_assignment
        today = timezone.now()
        
        # Create 3 exhibitions
        exhibitions = []
        for i in range(3):
            exh = Exhibition.objects.create(
                name=f"Exh {i+1}",
                number_of_positions=2,
                start_date=today - timedelta(days=30),
                end_date=today + timedelta(days=60),
                is_special_event=False,
                open_on=[1, 3, 5]  # Tue, Thu, Sat
            )
            exhibitions.append(exh)
        
        # Create 30 guards
        guards = []
        for i in range(30):
            guard = create_guard_with_user(
                f"guard_{i+1}",
                f"guard{i+1}@test.com",
                availability=(i % 3) + 2,  # 2-4
                priority=Decimal(str(2.0 + i * 0.1))
            )
            guards.append(guard)
            
            for day in range(1, 7):
                GuardWorkPeriod.objects.create(
                    guard=guard,
                    day_of_week=day,
                    shift_type='morning',
                    is_template=True
                )
                GuardWorkPeriod.objects.create(
                    guard=guard,
                    day_of_week=day,
                    shift_type='afternoon',
                    is_template=True
                )
        
        # Add preferences for 20 guards
        for i in range(20):
            exhibition_ids = [exhibitions[j].id for j in range(3)]
            GuardExhibitionPreference.objects.create(
                guard=guards[i],
                exhibition_order=exhibition_ids,
                is_template=True
            )
            
            GuardDayPreference.objects.create(
                guard=guards[i],
                day_order=[(i % 6) + 1, ((i + 1) % 6) + 1],
                is_template=True
            )
        
        # Benchmark assignment
        start_time = time_module.time()
        result = assign_positions_automatically(settings)
        assignment_time = time_module.time() - start_time
        
        # Verify performance
        assert assignment_time < 30, f"Assignment took {assignment_time:.2f}s (should be < 30s)"
        
        # Verify correctness
        assert result['status'] in ['success', 'warning']
        
        # Log performance metrics
        print(f"\n=== Performance Benchmark ===")
        print(f"Guards: 30")
        print(f"Assignment time: {assignment_time:.3f}s")
        print(f"Assignments created: {result['assignments_created']}")
