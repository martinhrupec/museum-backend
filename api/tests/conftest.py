"""
Pytest configuration and shared fixtures for all tests.

This file provides reusable fixtures for:
- User creation (admin, guard)
- Authentication (APIClient)
- Database setup (SystemSettings, Exhibition, Position)
- Common test data
"""
import pytest
from django.contrib.auth import get_user_model
from django.utils import timezone
from rest_framework.test import APIClient
from datetime import datetime, date, time, timedelta
from decimal import Decimal

from api.api_models import (
    Guard, 
    Exhibition, 
    Position, 
    SystemSettings,
    PositionHistory,
    Point,
    AdminNotification,
    GuardExhibitionPreference,
    GuardDayPreference,
    GuardWorkPeriod,
    NonWorkingDay
)


# ============= EMAIL CONFIGURATION =============
@pytest.fixture(autouse=True)
def use_real_smtp_backend(settings):
    """
    Force real SMTP email backend for all tests.
    pytest-django defaults to locmem backend which doesn't send real emails.
    """
    settings.EMAIL_BACKEND = 'django.core.mail.backends.smtp.EmailBackend'

User = get_user_model()


# ============= API CLIENT =============

@pytest.fixture
def api_client():
    """
    DRF APIClient for making HTTP requests in integration tests.
    
    Usage:
        def test_endpoint(api_client):
            response = api_client.get('/api/endpoint/')
            assert response.status_code == 200
    """
    return APIClient()


# ============= USER FIXTURES =============

@pytest.fixture
def admin_user(db):
    """
    Create admin user with ROLE_ADMIN and is_staff=True.
    
    Returns:
        User instance with admin role
    """
    return User.objects.create_user(
        username='admin',
        email='admin@museum.com',
        password='testpass123',
        role=User.ROLE_ADMIN,
        first_name='Admin',
        last_name='User'
    )


@pytest.fixture
def guard_user(db):
    """
    Create guard user with ROLE_GUARD.
    Guard profile is auto-created via signal.
    
    Returns:
        User instance with guard role (has guard profile)
    """
    return User.objects.create_user(
        username='guard1',
        email='guard1@museum.com',
        password='testpass123',
        role=User.ROLE_GUARD,
        first_name='Guard',
        last_name='One'
    )


@pytest.fixture
def second_guard_user(db):
    """
    Create second guard user for swap/multi-guard tests.
    
    Returns:
        User instance with guard role
    """
    return User.objects.create_user(
        username='guard2',
        email='guard2@museum.com',
        password='testpass123',
        role=User.ROLE_GUARD,
        first_name='Guard',
        last_name='Two'
    )


@pytest.fixture
def inactive_user(db):
    """
    Create inactive user (is_active=False) for testing access restrictions.
    
    Returns:
        User instance with is_active=False
    """
    user = User.objects.create_user(
        username='inactive',
        email='inactive@museum.com',
        password='testpass123',
        role=User.ROLE_GUARD
    )
    user.is_active = False
    user.save()
    return user


# ============= AUTHENTICATED CLIENTS =============

@pytest.fixture
def authenticated_admin(api_client, admin_user):
    """
    APIClient authenticated as admin user.
    
    Usage:
        def test_admin_action(authenticated_admin):
            response = authenticated_admin.post('/api/admin-endpoint/')
    """
    api_client.force_authenticate(user=admin_user)
    return api_client


@pytest.fixture
def authenticated_guard(api_client, guard_user):
    """
    APIClient authenticated as guard user.
    
    Usage:
        def test_guard_action(authenticated_guard):
            response = authenticated_guard.get('/api/guard-endpoint/')
    """
    api_client.force_authenticate(user=guard_user)
    return api_client


@pytest.fixture
def authenticated_second_guard(api_client, second_guard_user):
    """
    APIClient authenticated as second guard (for swap tests).
    """
    api_client.force_authenticate(user=second_guard_user)
    return api_client


# ============= JWT AUTHENTICATED CLIENTS =============

@pytest.fixture
def jwt_authenticated_admin(api_client, admin_user):
    """
    APIClient authenticated via JWT as admin user.
    
    Usage:
        def test_admin_jwt_action(jwt_authenticated_admin):
            response = jwt_authenticated_admin.post('/api/endpoint/')
    """
    # Login to get JWT tokens
    response = api_client.post(
        '/api/auth/jwt/create/',
        {'username': 'admin', 'password': 'testpass123'},
        format='json'
    )
    access_token = response.data['access']
    refresh_token = response.data['refresh']
    
    # Set JWT token in headers
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
    
    # Store tokens for logout tests
    api_client._jwt_access_token = access_token
    api_client._jwt_refresh_token = refresh_token
    
    return api_client


@pytest.fixture
def jwt_authenticated_guard(api_client, guard_user):
    """
    APIClient authenticated via JWT as guard user.
    
    Usage:
        def test_guard_jwt_action(jwt_authenticated_guard):
            response = jwt_authenticated_guard.get('/api/endpoint/')
    """
    # Login to get JWT tokens
    response = api_client.post(
        '/api/auth/jwt/create/',
        {'username': 'guard1', 'password': 'testpass123'},
        format='json'
    )
    access_token = response.data['access']
    refresh_token = response.data['refresh']
    
    # Set JWT token in headers
    api_client.credentials(HTTP_AUTHORIZATION=f'Bearer {access_token}')
    
    # Store tokens for logout tests
    api_client._jwt_access_token = access_token
    api_client._jwt_refresh_token = refresh_token
    
    return api_client


# ============= SYSTEM SETTINGS =============

@pytest.fixture
def system_settings(db):
    """
    Create SystemSettings with realistic defaults.
    
    Sets up:
    - Work week periods (this_week, next_week)
    - Shift times (weekday/weekend morning/afternoon)
    - Position limits (minimal number per week)
    - Point values and penalties
    - Assignment timing (day and time for automated assignments)
    
    Returns:
        SystemSettings instance
    """
    today = date.today()
    
    # Calculate week boundaries
    # This week: current Monday to Sunday
    this_week_start = today - timedelta(days=today.weekday())
    this_week_end = this_week_start + timedelta(days=6)
    
    # Next week: next Monday to Sunday
    next_week_start = this_week_start + timedelta(days=7)
    next_week_end = next_week_start + timedelta(days=6)
    
    return SystemSettings.objects.create(
        # Week periods
        this_week_start=this_week_start,
        this_week_end=this_week_end,
        next_week_start=next_week_start,
        next_week_end=next_week_end,
        
        # Assignment timing - Wednesday 19:00 (default)
        # Config window: Monday 08:00 to Wednesday 18:00
        day_for_assignments=2,  # Wednesday
        time_of_assignments=time(19, 0),
        
        # Shift times - Weekday
        weekday_morning_start=time(11, 0),
        weekday_morning_end=time(15, 0),
        weekday_afternoon_start=time(15, 0),
        weekday_afternoon_end=time(19, 0),
        
        # Shift times - Weekend
        weekend_morning_start=time(10, 0),
        weekend_morning_end=time(15, 0),
        weekend_afternoon_start=time(15, 0),
        weekend_afternoon_end=time(20, 0),
        
        # Position limits
        minimal_number_of_positions_in_week=3,
        
        # Points and penalties
        hourly_rate=Decimal('10.00'),
        award_for_sunday_position_completion=Decimal('5.00'),
        award_for_jumping_in_on_cancelled_position=Decimal('3.00'),
        penalty_for_position_cancellation_before_the_position_day=Decimal('-2.00'),
        penalty_for_position_cancellation_on_the_position_day=Decimal('-5.00'),
        penalty_for_being_late_with_notification=Decimal('-3.00'),
        penalty_for_being_late_without_notification=Decimal('-10.00'),
        
        # Workdays (Monday-Friday)
        workdays=[0, 1, 2, 3, 4]
    )


@pytest.fixture
def mock_config_window_open(system_settings, mocker):
    """
    Mock timezone.now() to return a time within the configuration window.
    
    Config window is from Monday 08:00 to 1 hour before automated assignment.
    With assignment on Wednesday 19:00, config window ends Wednesday 18:00.
    This fixture mocks time to be Tuesday 10:00 of the current week,
    which is safely within the config window.
    
    Usage:
        def test_guard_can_configure(authenticated_guard, guard_user, mock_config_window_open):
            # Time is now within config window
            ...
    """
    # Tuesday 10:00 of this week - safely within config window (Mon 08:00 - Wed 18:00)
    config_time = datetime.combine(
        system_settings.this_week_start + timedelta(days=1),  # Tuesday
        time(10, 0)
    )
    config_time = timezone.make_aware(config_time)
    
    mocker.patch('django.utils.timezone.now', return_value=config_time)
    return config_time


@pytest.fixture
def mock_manual_window_open(system_settings, mocker):
    """
    Mock timezone.now() to return a time within the manual assignment window.
    
    Manual assignment window starts 1h after automated assignment (Wed 20:00)
    and ends 36h later (Friday 07:00).
    This fixture mocks time to be Thursday 10:00 of the current week,
    which is safely within the manual assignment window.
    
    Usage:
        def test_admin_can_assign(authenticated_admin, mock_manual_window_open):
            # Time is now within manual assignment window
            ...
    """
    # Thursday 10:00 of this week - within manual window (Wed 20:00 - Fri 07:00)
    manual_time = datetime.combine(
        system_settings.this_week_start + timedelta(days=3),  # Thursday
        time(10, 0)
    )
    manual_time = timezone.make_aware(manual_time)
    
    mocker.patch('django.utils.timezone.now', return_value=manual_time)
    return manual_time


@pytest.fixture
def mock_after_manual_window(system_settings, mocker):
    """
    Mock timezone.now() to return a time AFTER the manual assignment window.
    
    Manual assignment window ends 36h after automated assignment.
    With assignment on Wednesday 19:00, manual window ends Friday 08:00.
    This fixture mocks time to be Friday 10:00 of the current week,
    which is after the manual assignment window has ended.
    
    Useful for:
    - Testing swap requests (which require manual window to be closed)
    - Testing bulk operations that need finalized assignments
    
    Usage:
        def test_guard_can_swap(authenticated_guard, mock_after_manual_window):
            # Time is now after manual window ended
            ...
    """
    # Friday 10:00 of this week - after manual window (which ends Fri 08:00)
    after_manual_time = datetime.combine(
        system_settings.this_week_start + timedelta(days=4),  # Friday
        time(10, 0)
    )
    after_manual_time = timezone.make_aware(after_manual_time)
    
    mocker.patch('django.utils.timezone.now', return_value=after_manual_time)
    return after_manual_time


# ============= EXHIBITION & POSITION =============

@pytest.fixture
def sample_exhibition(db, system_settings):
    """
    Create exhibition open all weekdays (Monday-Friday).
    
    Depends on system_settings to ensure SystemSettings exists before Exhibition creation
    (Exhibition.save triggers position generation which needs SystemSettings).
    
    Returns:
        Exhibition instance
    """
    from datetime import timedelta
    from django.utils import timezone
    
    return Exhibition.objects.create(
        name='Main Gallery',
        number_of_positions=2,
        start_date=timezone.now(),
        end_date=timezone.now() + timedelta(days=90),
        open_on=[0, 1, 2, 3, 4],  # Monday-Friday
        is_special_event=False
    )


@pytest.fixture
def special_event_exhibition(db, system_settings):
    """
    Create special event exhibition with custom hours.
    
    Depends on system_settings to ensure SystemSettings exists before Exhibition creation.
    
    Returns:
        Exhibition instance with is_special_event=True
    """
    from datetime import timedelta, time
    from django.utils import timezone
    
    return Exhibition.objects.create(
        name='Special Event',
        number_of_positions=3,
        start_date=timezone.now(),
        end_date=timezone.now() + timedelta(days=7),
        open_on=[4, 5],  # Friday-Saturday
        is_special_event=True,
        event_start_time=time(18, 0),
        event_end_time=time(22, 0)
    )


@pytest.fixture
def multiple_exhibitions(db, system_settings):
    """
    Create multiple exhibitions for realistic preference testing.
    
    Returns:
        List of 3 Exhibition instances
    """
    from datetime import timedelta
    from django.utils import timezone
    
    exhibitions = [
        Exhibition.objects.create(
            name='Ancient Art',
            number_of_positions=2,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=90),
            open_on=[0, 1, 2, 3, 4],  # Monday-Friday
            is_special_event=False
        ),
        Exhibition.objects.create(
            name='Modern Gallery',
            number_of_positions=1,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=90),
            open_on=[0, 1, 2, 3, 4],  # Monday-Friday
            is_special_event=False
        ),
        Exhibition.objects.create(
            name='Sculpture Garden',
            number_of_positions=2,
            start_date=timezone.now(),
            end_date=timezone.now() + timedelta(days=90),
            open_on=[0, 1, 2, 3, 4, 5],  # Monday-Saturday
            is_special_event=False
        ),
    ]
    return exhibitions


@pytest.fixture
def next_week_position(db, sample_exhibition, system_settings):
    """
    Create position in next_week with morning shift.
    
    Returns:
        Position instance (next Monday 9:00-14:00)
    """
    return Position.objects.create(
        exhibition=sample_exhibition,
        date=system_settings.next_week_start,
        start_time=system_settings.weekday_morning_start,
        end_time=system_settings.weekday_morning_end
    )


@pytest.fixture
def next_week_afternoon_position(db, sample_exhibition, system_settings):
    """
    Create afternoon position in next_week.
    
    Returns:
        Position instance (next Monday 14:00-19:00)
    """
    return Position.objects.create(
        exhibition=sample_exhibition,
        date=system_settings.next_week_start,
        start_time=system_settings.weekday_afternoon_start,
        end_time=system_settings.weekday_afternoon_end
    )


@pytest.fixture
def this_week_position(db, sample_exhibition, system_settings):
    """
    Create position in this_week (for cancellation tests).
    
    Returns:
        Position instance (this Monday 9:00-14:00)
    """
    return Position.objects.create(
        exhibition=sample_exhibition,
        date=system_settings.this_week_start,
        start_time=system_settings.weekday_morning_start,
        end_time=system_settings.weekday_morning_end
    )


@pytest.fixture
def this_week_afternoon_position(db, sample_exhibition, system_settings):
    """
    Create afternoon position in this_week (for swap tests).
    
    Returns:
        Position instance (this Monday 14:00-19:00)
    """
    return Position.objects.create(
        exhibition=sample_exhibition,
        date=system_settings.this_week_start,
        start_time=system_settings.weekday_afternoon_start,
        end_time=system_settings.weekday_afternoon_end
    )


# ============= HELPER FIXTURES =============

@pytest.fixture
def assigned_position(db, next_week_position, guard_user):
    """
    Create position already assigned to guard1.
    
    Returns:
        tuple: (Position, PositionHistory)
    """
    history = PositionHistory.objects.create(
        position=next_week_position,
        guard=guard_user.guard,
        action=PositionHistory.Action.ASSIGNED
    )
    return next_week_position, history


@pytest.fixture
def cancelled_position(db, next_week_position, guard_user):
    """
    Create position that was assigned then cancelled.
    
    Returns:
        tuple: (Position, latest_PositionHistory)
    """
    # First assign
    PositionHistory.objects.create(
        position=next_week_position,
        guard=guard_user.guard,
        action=PositionHistory.Action.ASSIGNED
    )
    # Then cancel
    cancelled_history = PositionHistory.objects.create(
        position=next_week_position,
        guard=guard_user.guard,
        action=PositionHistory.Action.CANCELLED
    )
    return next_week_position, cancelled_history


@pytest.fixture
def multiple_guards(db):
    """
    Create 5 guards for algorithm tests.
    
    Returns:
        list[User]: List of 5 guard users
    """
    guards = []
    for i in range(1, 6):
        user = User.objects.create_user(
            username=f'guard{i}',
            email=f'guard{i}@museum.com',
            password='testpass123',
            role=User.ROLE_GUARD,
            first_name=f'Guard',
            last_name=f'Number {i}'
        )
        # Set priority for algorithm
        user.guard.priority_number = Decimal(f'{i}.00')
        user.guard.save()
        guards.append(user)
    return guards


# ============= TIME HELPERS =============

@pytest.fixture
def freeze_time_to_manual_window(system_settings):
    """
    Freeze time to manual assignment window (Saturday 10:00).
    For use with time-dependent tests.
    
    Note: Requires pytest-freezegun or manual timezone mocking
    """
    return system_settings.manual_assignment_start_datetime


@pytest.fixture
def freeze_time_after_grace_period(system_settings):
    """
    Freeze time to after grace period (Saturday 11:00+).
    """
    return system_settings.grace_period_end_datetime + timedelta(minutes=1)
