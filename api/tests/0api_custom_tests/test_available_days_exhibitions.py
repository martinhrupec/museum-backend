"""
Integration tests for available_days and available_exhibitions endpoints.

These endpoints return what days/exhibitions a guard can include in their preferences
based on their work periods.
"""
import pytest
from datetime import time, timedelta
from api.api_models import GuardWorkPeriod, Position


@pytest.mark.django_db
class TestAvailableDays:
    """Tests for GET /api/guards/{id}/available_days/"""
    
    def test_guard_can_get_own_available_days(
        self, authenticated_guard, guard_user, system_settings, mock_config_window_open
    ):
        """
        Guard can see their own available days based on work periods.
        """
        # Create work periods for Monday, Wednesday, Friday (0, 2, 4)
        for day in [0, 2, 4]:
            GuardWorkPeriod.objects.create(
                guard=guard_user.guard,
                day_of_week=day,
                shift_type='morning',
                is_template=True
            )
        
        response = authenticated_guard.get(
            f'/api/guards/{guard_user.guard.id}/available_days/'
        )
        
        assert response.status_code == 200
        assert response.data['days'] == [0, 2, 4]
        assert response.data['count'] == 3
        assert len(response.data['days_detailed']) == 3
    
    def test_guard_without_work_periods_gets_empty_list(
        self, authenticated_guard, guard_user, system_settings, mock_config_window_open
    ):
        """
        Guard without work periods gets empty list.
        """
        response = authenticated_guard.get(
            f'/api/guards/{guard_user.guard.id}/available_days/'
        )
        
        assert response.status_code == 200
        assert response.data['days'] == []
        assert 'nema postavljene periode' in response.data.get('message', '').lower()
    
    def test_guard_cannot_see_other_guards_available_days(
        self, authenticated_guard, second_guard_user, system_settings
    ):
        """
        Guard cannot see another guard's available days.
        """
        response = authenticated_guard.get(
            f'/api/guards/{second_guard_user.guard.id}/available_days/'
        )
        
        assert response.status_code in (403, 404)
    
    def test_admin_can_see_guard_available_days(
        self, authenticated_admin, guard_user, system_settings, mock_config_window_open
    ):
        """
        Admin can see any guard's available days.
        """
        GuardWorkPeriod.objects.create(
            guard=guard_user.guard,
            day_of_week=1,
            shift_type='morning',
            is_template=True
        )
        
        response = authenticated_admin.get(
            f'/api/guards/{guard_user.guard.id}/available_days/'
        )
        
        assert response.status_code == 200
        assert 1 in response.data['days']


@pytest.mark.django_db
class TestAvailableExhibitions:
    """Tests for GET /api/guards/{id}/available_exhibitions/"""
    
    def test_guard_can_get_own_available_exhibitions(
        self, authenticated_guard, guard_user, sample_exhibition, system_settings, mock_config_window_open
    ):
        """
        Guard can see exhibitions available on their work period days.
        """
        # Create position on Monday
        Position.objects.create(
            exhibition=sample_exhibition,
            date=system_settings.next_week_start,  # This is Monday
            start_time=time(9, 0),
            end_time=time(14, 0)
        )
        
        # Create work period for Monday
        GuardWorkPeriod.objects.create(
            guard=guard_user.guard,
            day_of_week=system_settings.next_week_start.weekday(),
            shift_type='morning',
            is_template=True
        )
        
        response = authenticated_guard.get(
            f'/api/guards/{guard_user.guard.id}/available_exhibitions/'
        )
        
        assert response.status_code == 200
        assert sample_exhibition.id in response.data['exhibition_ids']
        assert response.data['count'] == 1
    
    def test_guard_without_work_periods_gets_empty_exhibitions(
        self, authenticated_guard, guard_user, sample_exhibition, system_settings, mock_config_window_open
    ):
        """
        Guard without work periods gets empty exhibition list.
        """
        # Create position but no work periods
        Position.objects.create(
            exhibition=sample_exhibition,
            date=system_settings.next_week_start,
            start_time=time(9, 0),
            end_time=time(14, 0)
        )
        
        response = authenticated_guard.get(
            f'/api/guards/{guard_user.guard.id}/available_exhibitions/'
        )
        
        assert response.status_code == 200
        assert response.data['exhibitions'] == []
        assert 'nema postavljene periode' in response.data.get('message', '').lower()
    
    def test_exhibition_not_on_work_period_day_excluded(
        self, authenticated_guard, guard_user, system_settings, mock_config_window_open
    ):
        """
        Exhibition on day not in work periods is excluded.
        """
        from api.api_models import Exhibition
        from django.utils import timezone
        
        # Create a new exhibition without auto-generated positions
        test_exhibition = Exhibition.objects.create(
            name="Test Exhibition",
            number_of_positions=1,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=30),
            is_special_event=False,
            open_on=[0]  # Only open Monday
        )
        # Delete auto-generated positions
        Position.objects.filter(exhibition=test_exhibition).delete()
        
        # Create position ONLY on Monday (weekday 0)
        Position.objects.create(
            exhibition=test_exhibition,
            date=system_settings.next_week_start,  # Monday
            start_time=time(9, 0),
            end_time=time(14, 0)
        )
        
        # Create work period for Tuesday (weekday 1) - different day!
        GuardWorkPeriod.objects.create(
            guard=guard_user.guard,
            day_of_week=1,  # Tuesday
            shift_type='morning',
            is_template=True
        )
        
        response = authenticated_guard.get(
            f'/api/guards/{guard_user.guard.id}/available_exhibitions/'
        )
        
        assert response.status_code == 200
        # Exhibition should not be in list because it's not open on guard's work days
        assert test_exhibition.id not in response.data['exhibition_ids']
    
    def test_guard_cannot_see_other_guards_available_exhibitions(
        self, authenticated_guard, second_guard_user, system_settings
    ):
        """
        Guard cannot see another guard's available exhibitions.
        """
        response = authenticated_guard.get(
            f'/api/guards/{second_guard_user.guard.id}/available_exhibitions/'
        )
        
        assert response.status_code in (403, 404)
    
    def test_admin_can_see_guard_available_exhibitions(
        self, authenticated_admin, guard_user, sample_exhibition, system_settings, mock_config_window_open
    ):
        """
        Admin can see any guard's available exhibitions.
        """
        Position.objects.create(
            exhibition=sample_exhibition,
            date=system_settings.next_week_start,
            start_time=time(9, 0),
            end_time=time(14, 0)
        )
        
        GuardWorkPeriod.objects.create(
            guard=guard_user.guard,
            day_of_week=system_settings.next_week_start.weekday(),
            shift_type='morning',
            is_template=True
        )
        
        response = authenticated_admin.get(
            f'/api/guards/{guard_user.guard.id}/available_exhibitions/'
        )
        
        assert response.status_code == 200
        assert sample_exhibition.id in response.data['exhibition_ids']
