"""
Fixtures for assignment algorithm tests.

Provides comprehensive test data for guards, positions, preferences, and system settings.
"""
import pytest
from datetime import date, time, timedelta
from decimal import Decimal
from django.utils import timezone
from django.contrib.auth.hashers import make_password

from api.api_models import (
    User, Guard, Exhibition, Position, SystemSettings,
    GuardWorkPeriod, GuardExhibitionPreference, GuardDayPreference
)


@pytest.fixture
def system_settings_for_assignment(db):
    """
    SystemSettings configured for next week assignment testing.
    
    Returns settings with:
    - next_week_start/end set to upcoming Monday-Sunday
    - Workdays: Monday-Friday (0-4)
    - Shift times configured
    """
    today = date.today()
    days_until_next_monday = (7 - today.weekday()) % 7 or 7
    next_monday = today + timedelta(days=days_until_next_monday)
    next_sunday = next_monday + timedelta(days=6)
    
    settings = SystemSettings.objects.create(
        this_week_start=next_monday - timedelta(days=7),
        this_week_end=next_sunday - timedelta(days=7),
        next_week_start=next_monday,
        next_week_end=next_sunday,
        workdays=[1, 2, 3, 4, 5, 6],  # Tuesday-Sunday (6 workdays)
        weekday_morning_start=time(8, 0),
        weekday_morning_end=time(12, 0),
        weekday_afternoon_start=time(13, 0),
        weekday_afternoon_end=time(17, 0),
        weekend_morning_start=time(9, 0),
        weekend_morning_end=time(13, 0),
        weekend_afternoon_start=time(14, 0),
        weekend_afternoon_end=time(18, 0),
        minimal_number_of_positions_in_week=2,
        points_life_weeks=4,
        day_for_assignments=1,  # Tuesday (within 40h limit)
        time_of_assignments=time(12, 0),  # Noon
    )
    return settings


@pytest.fixture
def sample_exhibitions(db, system_settings_for_assignment):
    """Create sample exhibitions for testing."""
    today = timezone.now()
    
    exhibition1 = Exhibition.objects.create(
        name="Ancient Egypt",
        number_of_positions=2,
        start_date=today - timedelta(days=30),
        end_date=today + timedelta(days=60),
        is_special_event=False,
        open_on=[1, 2, 3, 4, 5, 6]  # Tuesday-Sunday
    )
    
    exhibition2 = Exhibition.objects.create(
        name="Renaissance Art",
        number_of_positions=1,
        start_date=today - timedelta(days=20),
        end_date=today + timedelta(days=50),
        is_special_event=False,
        open_on=[1, 2, 3, 4, 5, 6]  # Tuesday-Sunday
    )
    
    exhibition3 = Exhibition.objects.create(
        name="Modern Sculpture",
        number_of_positions=1,
        start_date=today - timedelta(days=10),
        end_date=today + timedelta(days=40),
        is_special_event=False,
        open_on=[1, 2, 3, 4, 5, 6]  # Tuesday-Sunday
    )
    
    return [exhibition1, exhibition2, exhibition3]


@pytest.fixture
def sample_exhibitions_weekdays_only(db, system_settings_for_assignment):
    """Create sample exhibitions for testing - weekdays only (no weekends)."""
    today = timezone.now()
    
    exhibition1 = Exhibition.objects.create(
        name="Ancient Egypt",
        number_of_positions=2,
        start_date=today - timedelta(days=30),
        end_date=today + timedelta(days=60),
        is_special_event=False,
        open_on=[1, 2, 3, 4]  # Tuesday-Friday (no weekends)
    )
    
    exhibition2 = Exhibition.objects.create(
        name="Renaissance Art",
        number_of_positions=1,
        start_date=today - timedelta(days=20),
        end_date=today + timedelta(days=50),
        is_special_event=False,
        open_on=[1, 2, 3, 4]  # Tuesday-Friday (no weekends)
    )
    
    exhibition3 = Exhibition.objects.create(
        name="Modern Sculpture",
        number_of_positions=1,
        start_date=today - timedelta(days=10),
        end_date=today + timedelta(days=40),
        is_special_event=False,
        open_on=[1, 2, 3, 4]  # Tuesday-Friday (no weekends)
    )
    
    return [exhibition1, exhibition2, exhibition3]


@pytest.fixture
def special_event_exhibition(db):
    """Create a special event exhibition (should be excluded from automated assignment)."""
    today = timezone.now()
    next_week = today + timedelta(days=7)
    
    return Exhibition.objects.create(
        name="Grand Opening Special",
        number_of_positions=5,
        start_date=next_week,
        end_date=next_week,
        is_special_event=True,
        event_start_time=time(18, 0),
        event_end_time=time(22, 0),
        open_on=[2]  # Wednesday
    )


@pytest.fixture
def create_guard_with_user(db):
    """
    Fixture factory for creating guards with associated users.
    
    Guard profile is auto-created via post_save signal when User with ROLE_GUARD is created.
    
    Usage:
        guard = create_guard_with_user('username', 'email@test.com', availability=3, priority=Decimal('2.0'))
    """
    def _create_guard(username, email, availability=None, priority=Decimal('1.0')):
        user = User.objects.create(
            username=username,
            email=email,
            password=make_password('testpass123'),
            role=User.ROLE_GUARD,
            is_active=True
        )
        
        # Guard is auto-created by signal - retrieve it
        guard = Guard.objects.get(user=user)
        
        # Update availability and priority
        if availability is not None:
            guard.availability = availability
            # Set availability_updated_at to Monday 09:00 (within configuration period)
            # Configuration period is Monday 08:00 - 1h before automated assignment
            now = timezone.now()
            days_since_monday = now.weekday()  # Monday=0
            monday_9am = now.replace(hour=9, minute=0, second=0, microsecond=0) - timedelta(days=days_since_monday)
            guard.availability_updated_at = monday_9am
        
        guard.priority_number = priority
        guard.save()
        
        return guard
    
    return _create_guard


@pytest.fixture
def guards_with_low_availability(db, create_guard_with_user):
    """Create guards with low availability (1-2 positions)."""
    return [
        create_guard_with_user('guard_low1', 'low1@test.com', availability=1, priority=Decimal('1.0')),
        create_guard_with_user('guard_low2', 'low2@test.com', availability=2, priority=Decimal('1.5')),
    ]


@pytest.fixture
def guards_with_medium_availability(db, create_guard_with_user):
    """Create guards with medium availability (3-4 positions)."""
    return [
        create_guard_with_user('guard_med1', 'med1@test.com', availability=3, priority=Decimal('2.0')),
        create_guard_with_user('guard_med2', 'med2@test.com', availability=4, priority=Decimal('2.5')),
    ]


@pytest.fixture
def guards_with_high_availability(db, create_guard_with_user):
    """Create realistic number of guards (~15) with varying availability (2-5 positions)."""
    guards = []
    for i in range(15):
        availability = 2 + (i % 4)  # Varies 2-5
        priority = Decimal(str(1.0 + (i % 5) * 0.5))  # Varies 1.0-3.0
        guard = create_guard_with_user(f'guard{i}', f'g{i}@test.com', availability=availability, priority=priority)
        guards.append(guard)
    return guards


@pytest.fixture
def guards_mixed_availability(db, create_guard_with_user):
    """Create realistic mixed set of guards (~20) with varying availability and priorities."""
    guards = []
    for i in range(20):
        availability = 1 + (i % 5)  # Varies 1-5
        priority = Decimal(str(0.5 + (i % 6) * 0.5))  # Varies 0.5-3.0
        guard = create_guard_with_user(f'guard{i}', f'g{i}@test.com', availability=availability, priority=priority)
        guards.append(guard)
    return guards


@pytest.fixture
def guards_same_priority(db, create_guard_with_user):
    """Create guards with identical priority (tests priority normalization edge case)."""
    priority = Decimal('2.0')
    return [
        create_guard_with_user('equal1', 'eq1@test.com', availability=3, priority=priority),
        create_guard_with_user('equal2', 'eq2@test.com', availability=3, priority=priority),
        create_guard_with_user('equal3', 'eq3@test.com', availability=3, priority=priority),
    ]


@pytest.fixture
def next_week_positions(db, system_settings_for_assignment, sample_exhibitions):
    """
    Create positions for next week (Tuesday-Sunday, 2 shifts per day).
    
    Total: 6 days × 2 shifts × 2 avg positions (2+1+1 from exhibitions) = ~24 positions
    """
    settings = system_settings_for_assignment
    positions = []
    
    current_date = settings.next_week_start
    
    # Generate for each workday (Tuesday-Sunday)
    for day_offset in range(7):  # Full week
        work_date = current_date + timedelta(days=day_offset)
        
        # Skip Monday (workday 0)
        if work_date.weekday() not in settings.workdays:
            continue
        
        # Morning shift positions
        for exhibition in sample_exhibitions:
            if work_date.weekday() in exhibition.open_on:
                for _ in range(exhibition.number_of_positions):
                    pos = Position.objects.create(
                        exhibition=exhibition,
                        date=work_date,
                        start_time=settings.weekday_morning_start,
                        end_time=settings.weekday_morning_end
                    )
                    positions.append(pos)
        
        # Afternoon shift positions
        for exhibition in sample_exhibitions:
            if work_date.weekday() in exhibition.open_on:
                for _ in range(exhibition.number_of_positions):
                    pos = Position.objects.create(
                        exhibition=exhibition,
                        date=work_date,
                        start_time=settings.weekday_afternoon_start,
                        end_time=settings.weekday_afternoon_end
                    )
                    positions.append(pos)
    
    return positions


@pytest.fixture
def minimal_positions(db, system_settings_for_assignment, sample_exhibitions):
    """Create minimal set of positions (1 day, morning shift only)."""
    settings = system_settings_for_assignment
    exhibition = sample_exhibitions[0]
    
    positions = []
    for _ in range(2):  # 2 positions for this exhibition
        pos = Position.objects.create(
            exhibition=exhibition,
            date=settings.next_week_start,
            start_time=settings.weekday_morning_start,
            end_time=settings.weekday_morning_end
        )
        positions.append(pos)
    
    return positions


@pytest.fixture
def special_event_positions(db, system_settings_for_assignment, special_event_exhibition):
    """Create positions for special event (should be excluded from automated assignment)."""
    settings = system_settings_for_assignment
    event_date = settings.next_week_start + timedelta(days=2)  # Wednesday
    
    positions = []
    for _ in range(5):
        pos = Position.objects.create(
            exhibition=special_event_exhibition,
            date=event_date,
            start_time=special_event_exhibition.event_start_time,
            end_time=special_event_exhibition.event_end_time
        )
        positions.append(pos)
    
    return positions


@pytest.fixture
def guard_work_periods_template(db, guards_mixed_availability, system_settings_for_assignment):
    """
    Create template work periods for guards.
    
    guard1: Monday morning, Wednesday afternoon
    guard2: Tuesday full day, Thursday morning
    guard3: Monday-Friday mornings
    guard4: All shifts all days (maximum availability)
    guard5: Only Friday afternoon
    """
    settings = system_settings_for_assignment
    guards = guards_mixed_availability
    
    # Guard 1: Selective periods (Tuesday, Thursday afternoon)
    GuardWorkPeriod.objects.create(guard=guards[0], day_of_week=1, shift_type='morning', is_template=True)  # Tuesday
    GuardWorkPeriod.objects.create(guard=guards[0], day_of_week=3, shift_type='afternoon', is_template=True)  # Thursday
    
    # Guard 2: Two days (Wednesday)
    GuardWorkPeriod.objects.create(guard=guards[1], day_of_week=2, shift_type='morning', is_template=True)
    GuardWorkPeriod.objects.create(guard=guards[1], day_of_week=2, shift_type='afternoon', is_template=True)
    GuardWorkPeriod.objects.create(guard=guards[1], day_of_week=4, shift_type='morning', is_template=True)  # Friday
    
    # Guard 3: All mornings (Tuesday-Sunday)
    for day in range(1, 7):  # Tuesday-Sunday
        GuardWorkPeriod.objects.create(guard=guards[2], day_of_week=day, shift_type='morning', is_template=True)
    
    # Guard 4: All shifts (Tuesday-Sunday)
    for day in range(1, 7):  # Tuesday-Sunday (6 workdays)
        GuardWorkPeriod.objects.create(guard=guards[3], day_of_week=day, shift_type='morning', is_template=True)
        GuardWorkPeriod.objects.create(guard=guards[3], day_of_week=day, shift_type='afternoon', is_template=True)
    
    # Guard 5: Very restrictive (Friday afternoon only)
    GuardWorkPeriod.objects.create(guard=guards[4], day_of_week=5, shift_type='afternoon', is_template=True)  # Friday
    
    return guards


@pytest.fixture
def guard_work_periods_specific(db, guards_mixed_availability, system_settings_for_assignment):
    """
    Create specific week work periods (override templates).
    
    Only for guard1 - specific periods for next_week.
    """
    settings = system_settings_for_assignment
    guard = guards_mixed_availability[0]
    
    # Override template with specific week
    GuardWorkPeriod.objects.create(
        guard=guard,
        day_of_week=0,
        shift_type='afternoon',  # Changed from morning
        is_template=False,
        next_week_start=settings.next_week_start
    )
    GuardWorkPeriod.objects.create(
        guard=guard,
        day_of_week=4,
        shift_type='morning',  # New period
        is_template=False,
        next_week_start=settings.next_week_start
    )
    
    return guard


@pytest.fixture
def exhibition_preferences(db, guards_mixed_availability, sample_exhibitions, system_settings_for_assignment):
    """
    Create exhibition preferences for guards.
    
    guard1: Prefers Ancient Egypt > Renaissance > Modern
    guard2: Prefers Renaissance > Modern > Ancient Egypt
    guard3: No preference (neutral)
    """
    settings = system_settings_for_assignment
    guards = guards_mixed_availability
    exhibitions = sample_exhibitions
    
    # Guard 1 preferences
    GuardExhibitionPreference.objects.create(
        guard=guards[0],
        exhibition_order=[exhibitions[0].id, exhibitions[1].id, exhibitions[2].id],
        is_template=True
    )
    
    # Guard 2 preferences (reversed)
    GuardExhibitionPreference.objects.create(
        guard=guards[1],
        exhibition_order=[exhibitions[1].id, exhibitions[2].id, exhibitions[0].id],
        is_template=True
    )
    
    # Guard 3: No preference (returns neutral score of 1.0)
    
    return guards


@pytest.fixture
def day_preferences(db, guards_mixed_availability, system_settings_for_assignment):
    """
    Create day preferences for guards.
    
    guard1: Monday > Friday > Wednesday > Tuesday > Thursday
    guard2: Friday > Thursday > Wednesday > Tuesday > Monday
    """
    guards = guards_mixed_availability
    
    # Guard 1: Prefers start and end of week
    GuardDayPreference.objects.create(
        guard=guards[0],
        day_order=[0, 4, 2, 1, 3],  # Mon, Fri, Wed, Tue, Thu
        is_template=True
    )
    
    # Guard 2: Prefers end of week
    GuardDayPreference.objects.create(
        guard=guards[1],
        day_order=[4, 3, 2, 1, 0],  # Fri, Thu, Wed, Tue, Mon
        is_template=True
    )
    
    return guards
