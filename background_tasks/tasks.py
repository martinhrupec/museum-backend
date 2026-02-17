from celery import shared_task
from django.utils import timezone
from datetime import timedelta, time
from api.api_models import Exhibition, Position, SystemSettings, NonWorkingDay, Report, Point, AdminNotification, PositionHistory
from django.core.mail import send_mail
from django.conf import settings
from decimal import Decimal
import structlog

logger = structlog.get_logger(__name__)


@shared_task
def shift_weekly_periods():
    """
    Shift weekly periods in SystemSettings at the start of each week.
    
    This task runs first and updates the period boundaries:
    - Old next_week becomes new this_week
    - New next_week is calculated (+7 days from old next_week)
    
    Runs every Monday at 00:00.
    """
    settings = SystemSettings.load()
    
    # Shift periods: next_week → this_week
    if settings.next_week_start and settings.next_week_end:
        settings.this_week_start = settings.next_week_start
        settings.this_week_end = settings.next_week_end
        logger.info(f"Shifted next_week to this_week: {settings.this_week_start} to {settings.this_week_end}")
    else:
        # First run - initialize this_week to current week
        today = timezone.now().date()
        days_since_monday = today.weekday()  # Monday=0
        settings.this_week_start = today - timedelta(days=days_since_monday)
        settings.this_week_end = settings.this_week_start + timedelta(days=6)
        logger.info(f"Initialized this_week (first run): {settings.this_week_start} to {settings.this_week_end}")
    
    # Calculate new next_week (7 days after new this_week)
    settings.next_week_start = settings.this_week_start + timedelta(days=7)
    settings.next_week_end = settings.next_week_start + timedelta(days=6)
    settings.save()
    
    logger.info(f"Set new next_week period: {settings.next_week_start} to {settings.next_week_end}")
    return f"Weekly periods shifted: this_week={settings.this_week_start} to {settings.this_week_end}, next_week={settings.next_week_start} to {settings.next_week_end}"


@shared_task
def generate_weekly_positions():
    """
    Generate positions for next week based on active exhibitions.
    Creates 2 shifts per day (morning + afternoon) for regular exhibitions.
    Creates positions with event times for special events.
    Skips non-working days for regular exhibitions.
    
    INCLUDES special events - they are part of weekly position generation.
    
    Runs every Monday at 00:01 (after shift_weekly_periods).
    """
    settings = SystemSettings.load()
    
    # Use settings values for position generation
    next_week_start = settings.next_week_start
    next_week_end = settings.next_week_end
    
    if not next_week_start or not next_week_end:
        logger.error("Cannot generate positions - next_week period not set. Run shift_weekly_periods first.")
        return "Error: next_week period not set"
    
    # Convert to timezone-aware datetime for filtering
    next_week_start_dt = timezone.make_aware(
        timezone.datetime.combine(next_week_start, time.min)
    )
    next_week_end_dt = timezone.make_aware(
        timezone.datetime.combine(next_week_end, time.max)
    )
    
    # Get non-working days for next week
    non_working_days = NonWorkingDay.objects.filter(
        date__gte=next_week_start,
        date__lte=next_week_end
    )
    non_working_full_days = set(
        nwd.date for nwd in non_working_days if nwd.is_full_day
    )
    non_working_morning = set(
        nwd.date for nwd in non_working_days 
        if not nwd.is_full_day and nwd.non_working_shift == NonWorkingDay.ShiftType.MORNING
    )
    non_working_afternoon = set(
        nwd.date for nwd in non_working_days 
        if not nwd.is_full_day and nwd.non_working_shift == NonWorkingDay.ShiftType.AFTERNOON
    )
    
    # Find exhibitions active during next week
    exhibitions = Exhibition.objects.filter(
        start_date__lte=next_week_end_dt,
        end_date__gte=next_week_start_dt
    )
    
    created_count = 0
    
    for exhibition in exhibitions:
        # Handle special events separately
        if exhibition.is_special_event:
            event_date = exhibition.start_date.date()
            # Check if event date is in next week
            if next_week_start <= event_date <= next_week_end:
                # Create positions for special event
                for _ in range(exhibition.number_of_positions):
                    Position.objects.create(
                        exhibition=exhibition,
                        date=event_date,
                        start_time=exhibition.event_start_time,
                        end_time=exhibition.event_end_time
                    )
                    created_count += 1
            # Skip to next exhibition
            continue
        
        # Regular exhibition logic
        # Iterate through each day of next week
        current_date = next_week_start
        
        while current_date <= next_week_end:
            # Skip if not a museum workday
            day_of_week = current_date.weekday()
            if day_of_week not in settings.workdays:
                current_date += timedelta(days=1)
                continue
            
            # Skip if exhibition is not open on this day
            if day_of_week not in exhibition.open_on:
                current_date += timedelta(days=1)
                continue
            
            # Skip full non-working days
            if current_date in non_working_full_days:
                current_date += timedelta(days=1)
                continue
            
            # Check if exhibition is active on this specific day
            if exhibition.is_active(timezone.make_aware(
                timezone.datetime.combine(current_date, time.min)
            )):
                # Determine if weekend (Saturday=5, Sunday=6)
                is_weekend = current_date.weekday() in [5, 6]
                
                # Get shift times based on day type
                if is_weekend:
                    morning_start = settings.weekend_morning_start
                    morning_end = settings.weekend_morning_end
                    afternoon_start = settings.weekend_afternoon_start
                    afternoon_end = settings.weekend_afternoon_end
                else:
                    morning_start = settings.weekday_morning_start
                    morning_end = settings.weekday_morning_end
                    afternoon_start = settings.weekday_afternoon_start
                    afternoon_end = settings.weekday_afternoon_end
                
                # Create positions: number_of_positions * 2 shifts per day
                for _ in range(exhibition.number_of_positions):
                    # Morning shift (skip if non-working)
                    if current_date not in non_working_morning:
                        Position.objects.create(
                            exhibition=exhibition,
                            date=current_date,
                            start_time=morning_start,
                            end_time=morning_end
                        )
                        created_count += 1
                    
                    # Afternoon shift (skip if non-working)
                    if current_date not in non_working_afternoon:
                        Position.objects.create(
                            exhibition=exhibition,
                            date=current_date,
                            start_time=afternoon_start,
                            end_time=afternoon_end
                        )
                        created_count += 1
            
            current_date += timedelta(days=1)
    
    logger.info(f"Created {created_count} positions for next week")
    return f"Created {created_count} positions for next week"


@shared_task
def update_all_guard_priorities():
    """
    Update priority_number for all active guards based on weighted points history.
    
    Called every Monday at 00:00 (right after generate_weekly_positions).
    Calculates priority based on points earned in last N weeks (from SystemSettings.points_life_weeks),
    with more recent weeks weighted higher.
    """
    from api.api_models.user_type import Guard
    from django.db.models import Sum
    
    sys_settings = SystemSettings.load()
    weeks_to_consider = sys_settings.points_life_weeks
    
    now = timezone.now()
    cycle_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    
    guards = Guard.active_guards.all()
    
    for guard in guards:
        priority = calculate_guard_priority(guard, cycle_start, weeks_to_consider)
        guard.priority_number = priority
        guard.save()
        logger.info(f"Updated priority for {guard.user.username}: {priority}")
    
    logger.info(f"Updated priorities for {guards.count()} guards")
    return f"Updated priorities for {guards.count()} guards"


@shared_task
def run_automated_assignment():
    """
    Run automated position assignment using Hungarian algorithm.
    
    Called after position generation (Wednesday at configured time).
    
    Steps:
    1. Get guards with availability
    2. Calculate availability caps (if demand > supply)
    3. Run Hungarian algorithm assignment
    4. Calculate minimum based on ACTUAL assignment results
    5. Save results
    
    Returns summary of assignment results.
    """
    from background_tasks.assignment_algorithm import assign_positions_automatically
    from background_tasks.minimum_calculator import calculate_and_update_minimum
    from background_tasks.tasks import calculate_availability_caps
    from api.api_models import Position
    
    settings = SystemSettings.get_active()
    
    logger.info("=" * 80)
    logger.info("AUTOMATED ASSIGNMENT TASK STARTED")
    logger.info("=" * 80)
    
    # Step 1: Calculate availability caps
    logger.info("Calculating availability caps...")
    guards_with_availability = list(get_guards_with_availability_updated())
    
    total_positions = Position.objects.filter(
        date__gte=settings.next_week_start,
        date__lte=settings.next_week_end
    ).count()
    
    availability_caps = calculate_availability_caps(guards_with_availability, total_positions)
    
    if availability_caps:
        capping_count = sum(
            1 for g in guards_with_availability 
            if availability_caps.get(g.id, g.availability) < g.availability
        )
        logger.info(f"Availability capped for {capping_count} guards (demand > supply)")
    else:
        logger.info("No capping needed (supply >= demand)")
    
    # Step 2: Run assignment algorithm
    logger.info("Running assignment algorithm...")
    result = assign_positions_automatically(settings, availability_caps)
    
    # Step 3: Calculate minimum based on ACTUAL situation (empty positions)
    logger.info("Calculating dynamic minimum based on actual situation...")
    minimum = calculate_and_update_minimum(settings, total_positions)
    logger.info(f"Minimum calculated and saved: {minimum}")
    
    # Add minimum to result
    result['minimum_calculated'] = minimum
    
    logger.info("=" * 80)
    logger.info(f"AUTOMATED ASSIGNMENT COMPLETED: {result['status']}")
    logger.info("=" * 80)
    
    return result


@shared_task
def validate_preference_templates():
    """
    Validate all template preferences after position generation.
    
    Called every Monday at 00:10 (after position generation and priority updates).
    
    For each template preference:
    1. Extract exhibition/day/work period set from created_at week (historical)
    2. Compare with next_week set (current)
    3. If sets differ, invalidate template and notify guard
    
    Ensures template preferences remain valid only when context hasn't changed.
    """
    from api.api_models.preferences import GuardExhibitionPreference, GuardDayPreference
    from api.api_models.calculation import GuardWorkPeriod
    
    settings = SystemSettings.get_active()
    
    if not settings.next_week_start or not settings.next_week_end:
        logger.warning("Cannot validate templates - next_week period not set")
        return "Skipped - next_week period not set"
    
    invalidated_exhibition_count = 0
    invalidated_day_count = 0
    invalidated_work_period_count = 0
    
    # Validate Exhibition Preference Templates
    exhibition_templates = GuardExhibitionPreference.objects.filter(is_template=True)
    
    for pref in exhibition_templates:
        # Get historical exhibition set from created_at week
        # NOTE: Preferences created_at refers to the NEXT week, so add 7 days
        week_start, week_end = _get_week_from_datetime(pref.created_at)
        week_start = week_start + timedelta(days=7)
        week_end = week_end + timedelta(days=7)
        historical_exhibitions = _get_exhibitions_for_week(week_start, week_end)
        
        # Get current next_week exhibition set
        current_exhibitions = _get_exhibitions_for_week(
            settings.next_week_start,
            settings.next_week_end
        )
        
        # Compare sets
        if historical_exhibitions != current_exhibitions:
            # Invalidate template - set next_week_start to current week to satisfy validation
            pref.is_template = False
            pref.next_week_start = settings.next_week_start
            pref.save()
            
            # Notify guard (system-generated, unicast notification)
            # Expires at end of configuration period - only relevant during configuration window
            expires_at = settings.config_end_datetime
            if expires_at is None:
                # Fallback: expires in 3 days if config_end_datetime not available
                expires_at = timezone.now() + timedelta(days=3)
            AdminNotification.objects.create(
                cast_type=AdminNotification.CAST_UNICAST,
                to_user=pref.guard.user,
                title="Preference za izložbe su zastarjele",
                message=(
                    f"Vaše spremljene preference za izložbe više nisu valjane jer se skup "
                    f"izložbi promijenio. Molimo postavite nove preference za sljedeći tjedan."
                ),
                expires_at=expires_at
            )
            
            invalidated_exhibition_count += 1
            logger.info(
                f"Invalidated exhibition template for {pref.guard.user.username}: "
                f"historical={sorted(historical_exhibitions)}, current={sorted(current_exhibitions)}"
            )
    
    # Validate Day Preference Templates
    day_templates = GuardDayPreference.objects.filter(is_template=True)
    
    for pref in day_templates:
        # Get historical workday set from created_at week
        # NOTE: Preferences created_at refers to the NEXT week, so add 7 days
        week_start, week_end = _get_week_from_datetime(pref.created_at)
        week_start = week_start + timedelta(days=7)
        week_end = week_end + timedelta(days=7)
        historical_days = _get_workdays_for_week(week_start, week_end)
        
        # Get current next_week workday set
        current_days = _get_workdays_for_week(
            settings.next_week_start,
            settings.next_week_end
        )
        
        # Compare sets
        if historical_days != current_days:
            # Invalidate template - set next_week_start to current week to satisfy validation
            pref.is_template = False
            pref.next_week_start = settings.next_week_start
            pref.save()
            
            # Notify guard (system-generated, unicast notification)
            # Expires at end of configuration period - only relevant during configuration window
            expires_at = settings.config_end_datetime
            if expires_at is None:
                expires_at = timezone.now() + timedelta(days=3)
            AdminNotification.objects.create(
                cast_type=AdminNotification.CAST_UNICAST,
                to_user=pref.guard.user,
                title="Preference za dane su zastarjele",
                message=(
                    f"Vaše spremljene preferencije za dane više nisu valjane jer se skup "
                    f"radnih dana promijenio. Molimo postavite nove preferencije za sljedeći tjedan."
                ),
                expires_at=expires_at
            )
            
            invalidated_day_count += 1
            logger.info(
                f"Invalidated day template for {pref.guard.user.username}: "
                f"historical={sorted(historical_days)}, current={sorted(current_days)}"
            )
    
    # Validate Work Period Templates
    # After the schema change, ALL work periods have next_week_start set.
    # Templates from last cycle have next_week_start=settings.this_week_start
    # (because when they were set, that was next_week).
    # Templates with older next_week_start are from even earlier and should be invalidated.
    
    from collections import defaultdict
    
    # Find templates that need validation (from previous configuration cycles)
    # These are templates with next_week_start < settings.next_week_start
    work_period_templates = GuardWorkPeriod.objects.filter(
        is_template=True,
        next_week_start__lt=settings.next_week_start  # From previous cycles
    )
    
    # Also handle any templates with NULL next_week_start (legacy data)
    legacy_templates = GuardWorkPeriod.objects.filter(
        is_template=True,
        next_week_start__isnull=True
    )
    
    # Group by guard
    templates_by_guard = defaultdict(list)
    for wp in work_period_templates:
        templates_by_guard[wp.guard].append(wp)
    
    carried_forward_count = 0
    
    for guard, work_periods in templates_by_guard.items():
        # Get the next_week_start from the template (what week it was created for)
        first_wp = work_periods[0]
        template_week_start = first_wp.next_week_start
        template_week_end = template_week_start + timedelta(days=6)
        
        # Get available periods for the template's week (historical)
        historical_periods = _get_available_work_periods_for_week(
            template_week_start,
            template_week_end
        )
        
        # Get available periods for next_week (current)
        current_periods = _get_available_work_periods_for_week(
            settings.next_week_start,
            settings.next_week_end
        )
        
        # Compare sets
        if historical_periods == current_periods:
            # Conditions match - carry forward the template
            # 1. Create new copies for next_week with is_template=True
            for wp in work_periods:
                GuardWorkPeriod.objects.create(
                    guard=guard,
                    day_of_week=wp.day_of_week,
                    shift_type=wp.shift_type,
                    is_template=True,
                    next_week_start=settings.next_week_start
                )
            
            # 2. Set old templates to is_template=False (they keep their original next_week_start)
            for wp in work_periods:
                wp.is_template = False
                wp.save()
            
            carried_forward_count += 1
            logger.info(
                f"Carried forward work period template for {guard.user.username}: "
                f"from week {template_week_start} to {settings.next_week_start}"
            )
        else:
            # Conditions don't match - invalidate template (no copy for next_week)
            for wp in work_periods:
                wp.is_template = False
                wp.save()
            
            # Notify guard
            expires_at = settings.config_end_datetime
            if expires_at is None:
                expires_at = timezone.now() + timedelta(days=3)
            AdminNotification.objects.create(
                cast_type=AdminNotification.CAST_UNICAST,
                to_user=guard.user,
                title="Radni periodi dostupnosti su zastarjeli",
                message=(
                    f"Vaši spremljeni radni periodi više nisu valjani jer se skup "
                    f"dostupnih smjena promijenio (promjena radnih dana, radnog vremena ili neradnih dana). "
                    f"Molimo postavite nove radne periode dostupnosti za sljedeći tjedan."
                ),
                expires_at=expires_at
            )
            
            invalidated_work_period_count += 1
            logger.info(
                f"Invalidated work period template for {guard.user.username}: "
                f"historical={sorted(historical_periods)}, current={sorted(current_periods)}"
            )
    
    # Handle legacy templates (NULL next_week_start) - just invalidate them
    legacy_templates_by_guard = defaultdict(list)
    for wp in legacy_templates:
        legacy_templates_by_guard[wp.guard].append(wp)
    
    for guard, work_periods in legacy_templates_by_guard.items():
        for wp in work_periods:
            wp.is_template = False
            wp.next_week_start = settings.this_week_start  # Assign to current week
            wp.save()
        
        invalidated_work_period_count += 1
        logger.info(
            f"Invalidated legacy work period template for {guard.user.username} "
            f"(had NULL next_week_start)"
        )
    
    # Cleanup: Delete work periods older than 3 weeks
    three_weeks_ago = settings.this_week_start - timedelta(weeks=3)
    deleted_old_periods = GuardWorkPeriod.objects.filter(
        next_week_start__lt=three_weeks_ago,
        is_template=False  # Only delete non-templates (templates should have been processed above)
    ).delete()[0]
    
    if deleted_old_periods > 0:
        logger.info(f"Cleaned up {deleted_old_periods} work periods older than {three_weeks_ago}")
    
    result = (
        f"Validated preference templates: "
        f"invalidated {invalidated_exhibition_count} exhibition templates, "
        f"{invalidated_day_count} day templates, "
        f"{invalidated_work_period_count} work period templates, "
        f"carried forward {carried_forward_count} work period templates, "
        f"cleaned up {deleted_old_periods} old periods"
    )
    logger.info(result)
    return result


def _get_week_from_datetime(dt):
    """
    Calculate Monday-Sunday week range from any datetime.
    
    Args:
        dt: Datetime object
    
    Returns:
        tuple: (week_start_date, week_end_date) - Monday and Sunday
    """
    week_start = dt.date() - timedelta(days=dt.weekday())  # Monday
    week_end = week_start + timedelta(days=6)  # Sunday
    return week_start, week_end


def _get_exhibitions_for_week(week_start, week_end):
    """
    Get set of exhibition IDs that have positions in given week.
    
    Args:
        week_start: Date of Monday
        week_end: Date of Sunday
    
    Returns:
        set: Set of exhibition IDs
    """
    exhibitions = Exhibition.objects.filter(
        positions__date__gte=week_start,
        positions__date__lte=week_end
    ).distinct().values_list('id', flat=True)
    
    return set(exhibitions)


def _get_workdays_for_week(week_start, week_end):
    """
    Get set of day_of_week integers that have positions in given week.
    
    Args:
        week_start: Date of Monday
        week_end: Date of Sunday
    
    Returns:
        set: Set of day_of_week integers (0=Monday, 6=Sunday)
    """
    positions = Position.objects.filter(
        date__gte=week_start,
        date__lte=week_end
    ).values_list('date', flat=True).distinct()
    
    # Convert dates to day_of_week
    workdays = set(date.weekday() for date in positions)
    return workdays


def _get_available_work_periods_for_week(week_start, week_end):
    """
    Get set of (day_of_week, shift_type) tuples that are available in given week.
    
    Takes into account:
    - Which days have positions
    - Morning/afternoon shifts per day (based on position start_times)
    
    Args:
        week_start: Date of Monday
        week_end: Date of Sunday
    
    Returns:
        set: Set of (day_of_week, shift_type) tuples
        Example: {(0, 'morning'), (0, 'afternoon'), (1, 'morning'), ...}
    """
    settings = SystemSettings.get_active()
    
    # Get all positions in this week
    positions = Position.objects.filter(
        date__gte=week_start,
        date__lte=week_end
    ).values('date', 'start_time').distinct()
    
    available_periods = set()
    
    for pos in positions:
        day_of_week = pos['date'].weekday()
        start_time = pos['start_time']
        
        # Determine if morning or afternoon based on start_time
        is_weekend = day_of_week in [5, 6]  # Saturday=5, Sunday=6
        
        if is_weekend:
            morning_start = settings.weekend_morning_start
            afternoon_start = settings.weekend_afternoon_start
        else:
            morning_start = settings.weekday_morning_start
            afternoon_start = settings.weekday_afternoon_start
        
        if start_time == morning_start:
            shift_type = 'morning'
        elif start_time == afternoon_start:
            shift_type = 'afternoon'
        else:
            # Unknown shift - skip
            continue
        
        available_periods.add((day_of_week, shift_type))
    
    return available_periods


def calculate_guard_priority(guard, cycle_start, weeks_to_consider):
    """
    Calculate weighted priority for a single guard based on points history.
    
    Args:
        guard: Guard instance
        cycle_start: Datetime of current cycle start (Monday 00:00)
        weeks_to_consider: Number of weeks to look back (from SystemSettings)
    
    Returns:
        Decimal: Calculated priority number
    """
    from api.api_models.user_type import Guard
    from django.db.models import Sum
    
    weighted_sum = Decimal('0.0')
    
    for i in range(weeks_to_consider):
        # Calculate week boundaries
        # i=0: last week (most recent)
        # i=1: 2 weeks ago, etc.
        week_end = cycle_start - timedelta(days=i * 7)
        week_start = week_end - timedelta(days=7)
        
        # Get points for this guard in this week
        points_this_week = Point.objects.filter(
            guard=guard,
            date_awarded__gte=week_start,
            date_awarded__lt=week_end
        ).aggregate(total=Sum('points'))['total']
        
        # Check if guard existed during this week
        guard_created = guard.user.date_joined
        guard_existed_in_week = guard_created < week_start
        
        if points_this_week is None:
            if guard_existed_in_week:
                # Guard existed but earned no points - use 0, not average
                points_this_week = Decimal('0.0')
                logger.debug(f"Guard {guard.user.username} existed in week but earned 0 points")
            else:
                # Guard didn't exist yet - use average of other guards
                points_this_week = get_average_points_for_week(guard, week_start, week_end)
                logger.debug(f"Guard {guard.user.username} didn't exist yet, using average: {points_this_week}")
        
        # Apply weight factor with gradual decay: i=0 → 1.0, i=1 → 1.2, i=2 → 1.4, etc.
        factor = Decimal('1.0') if i == 0 else Decimal('1.0') + (Decimal('0.2') * i)
        weighted_points = Decimal(str(points_this_week)) / factor
        
        weighted_sum += weighted_points
        
        logger.debug(
            f"Guard {guard.user.username}, week {i} ({week_start.date()} to {week_end.date()}): "
            f"{points_this_week} pts, factor={factor}, weighted={weighted_points}"
        )
    
    return round(weighted_sum, 2)


def get_average_points_for_week(excluded_guard, week_start, week_end):
    """
    Calculate average points earned by all guards (except excluded_guard) in given week.
    Used for new guards who don't have points history.
    
    Args:
        excluded_guard: Guard to exclude from average calculation
        week_start: Start of week period
        week_end: End of week period
    
    Returns:
        Decimal: Average points for this week, or 0 if no data
    """
    from api.api_models.user_type import Guard
    from django.db.models import Sum, Count
    
    # Get all guards who have points in this week (excluding current guard)
    guards_with_points = Point.objects.filter(
        date_awarded__gte=week_start,
        date_awarded__lt=week_end
    ).exclude(
        guard=excluded_guard
    ).values('guard').annotate(
        total=Sum('points')
    )
    
    if not guards_with_points:
        return Decimal('0.0')
    
    total_points = sum(g['total'] for g in guards_with_points)
    avg_points = Decimal(str(total_points)) / len(guards_with_points)
    
    logger.debug(
        f"Average points for week {week_start.date()} to {week_end.date()}: "
        f"{avg_points} (from {len(guards_with_points)} guards)"
    )
    
    return avg_points


@shared_task
def send_report_email(report_id):
    """
    Asynchronously send email notification about new guard report.
    
    Args:
        report_id: ID of the Report object to send email about
    """
    import traceback
    
    logger.info(f"[send_report_email] Task started for report_id={report_id}")
    
    try:
        # Check email configuration
        logger.info(f"[send_report_email] Email config check:")
        logger.info(f"  - EMAIL_BACKEND: {settings.EMAIL_BACKEND}")
        logger.info(f"  - EMAIL_HOST: {settings.EMAIL_HOST}")
        logger.info(f"  - EMAIL_PORT: {settings.EMAIL_PORT}")
        logger.info(f"  - EMAIL_USE_TLS: {settings.EMAIL_USE_TLS}")
        logger.info(f"  - EMAIL_HOST_USER: {settings.EMAIL_HOST_USER or 'NOT SET'}")
        logger.info(f"  - EMAIL_HOST_PASSWORD: {'SET' if settings.EMAIL_HOST_PASSWORD else 'NOT SET'}")
        logger.info(f"  - DEFAULT_FROM_EMAIL: {settings.DEFAULT_FROM_EMAIL}")
        logger.info(f"  - RECEPTION_EMAIL: {settings.RECEPTION_EMAIL or 'NOT SET'}")
        
        # Validate configuration
        if not settings.EMAIL_HOST_USER:
            raise ValueError("EMAIL_HOST_USER is not configured in settings")
        if not settings.EMAIL_HOST_PASSWORD:
            raise ValueError("EMAIL_HOST_PASSWORD is not configured in settings")
        if not settings.RECEPTION_EMAIL:
            raise ValueError("RECEPTION_EMAIL is not configured in settings")
        
        # Fetch report
        logger.info(f"[send_report_email] Fetching report from database...")
        report = Report.objects.select_related('guard__user', 'position__exhibition').get(id=report_id)
        logger.info(f"[send_report_email] Report found: guard={report.guard.user.username}, position={report.position}")
        
        subject = f"Prijava problema - {report.guard.user.get_full_name() or report.guard.user.username}"
        message = f"""
Prijava problema:

Čuvar/ica: {report.guard.user.get_full_name() or report.guard.user.username}
Pozicija: {report.position.exhibition.name} - {report.position.date.strftime('%d.%m.%Y')} {report.position.start_time}

Poštovani,
{report.report_text}

Lijep pozdrav,
{report.guard.user.get_full_name() or report.guard.user.username}, {report.created_at.strftime('%d.%m.%Y %H:%M')}
        """
        
        logger.info(f"[send_report_email] Attempting to send email...")
        logger.info(f"  - Subject: {subject}")
        logger.info(f"  - From: {settings.DEFAULT_FROM_EMAIL}")
        logger.info(f"  - To: {settings.RECEPTION_EMAIL}")
        
        result = send_mail(
            subject,
            message,
            settings.DEFAULT_FROM_EMAIL,
            [settings.RECEPTION_EMAIL],
            fail_silently=False,
        )
        
        logger.info(f"[send_report_email] SUCCESS! Email sent for report #{report_id}, send_mail returned: {result}")
        return result
        
    except Report.DoesNotExist:
        error_msg = f"Report #{report_id} not found in database"
        logger.error(f"[send_report_email] ERROR: {error_msg}")
        logger.error(f"[send_report_email] Traceback:\n{traceback.format_exc()}")
        raise
    except Exception as e:
        error_msg = f"Failed to send report email for report #{report_id}: {type(e).__name__}: {str(e)}"
        logger.error(f"[send_report_email] ERROR: {error_msg}")
        logger.error(f"[send_report_email] Full traceback:\n{traceback.format_exc()}")
        raise  # Re-raise to mark task as FAILURE


# ========================================
# ASSIGNMENT HELPER FUNCTIONS
# ========================================

def get_guards_with_availability_updated():
    """
    Get all guards who updated their availability during current configuration period.
    
    Configuration period: from Monday 08:00 (config start) to config_end_time.
    Only guards who set availability in this period are eligible for automated assignment.
    
    Returns:
        QuerySet: Guards with availability set in current configuration period, ordered by priority
    """
    from api.api_models.user_type import Guard
    from django.utils import timezone
    
    settings = SystemSettings.load()
    
    # Use SystemSettings properties for configuration period boundaries
    config_start = settings.config_start_datetime
    config_end = settings.config_end_datetime
    
    if config_start is None or config_end is None:
        logger.warning("Configuration period not properly set in SystemSettings")
        return Guard.objects.none()
    
    # Get guards who updated availability in this configuration period
    eligible_guards = Guard.active_guards.filter(
        availability__isnull=False,
        availability__gt=0,
        availability_updated_at__gte=config_start,
        availability_updated_at__lte=config_end
    ).select_related('user').order_by('-priority_number')
    
    logger.info(
        f"Found {eligible_guards.count()} guards with availability set between "
        f"{config_start.strftime('%Y-%m-%d %H:%M')} and {config_end.strftime('%Y-%m-%d %H:%M')}"
    )
    
    return eligible_guards


def assign_initial_priority_to_new_guard(guard):
    """
    Assign priority_number to a new guard based on average of existing guards.
    
    If no other guards exist, assigns default priority of 50.0.
    If other guards exist, assigns the average of their priority_numbers.
    
    Args:
        guard: Guard instance (newly created, without priority_number)
    
    Returns:
        Decimal: The assigned priority number
    """
    from api.api_models.user_type import Guard
    from django.db.models import Avg
    from decimal import Decimal
    
    # Get average priority of all existing guards (excluding current one)
    avg_priority = Guard.objects.filter(
        priority_number__isnull=False
    ).exclude(
        id=guard.id
    ).aggregate(
        avg=Avg('priority_number')
    )['avg']
    
    if avg_priority is None:
        # No existing guards with priority - assign default
        assigned_priority = Decimal('1.0')
        logger.info(f"Assigned default priority {assigned_priority} to new guard {guard.user.username} (first guard)")
    else:
        # Assign average of existing priorities
        assigned_priority = Decimal(str(round(float(avg_priority), 2)))
        logger.info(f"Assigned average priority {assigned_priority} to new guard {guard.user.username}")
    
    guard.priority_number = assigned_priority
    guard.save()
    
    return assigned_priority


def calculate_availability_caps(eligible_guards, total_positions):
    """
    Calculate capped availability for each guard using iterative load balancing.
    
    If total demand (sum of availabilities) exceeds supply (positions), iteratively
    reduce the highest availability values until demand matches supply. When multiple
    guards have the same max availability, reduce the one with lowest priority_number first.
    
    This is a "water filling" / "iterative capping" algorithm that ensures fair distribution.
    
    Args:
        eligible_guards: QuerySet of Guard objects with availability set
        total_positions: Total number of available positions in next_week
    
    Returns:
        dict: {guard_id: capped_availability} - mapping guard ID to their maximum allowed positions
              Guards keep their original availability if no capping needed.
              Can be 0 if guard is completely excluded (not enough positions for everyone).
    
    Example:
        Positions: 10
        Guards: A(availability=5, priority=80), B(4, priority=70), C(3, priority=60)
        Total demand: 12 > 10 supply
        
        Iteration 1: Max=5 (only A), cap A to 4 → 4+4+3=11 (still too much)
        Iteration 2: Max=4 (A and B), B has lower priority, cap B to 3 → 4+3+3=10 (fits!)
        
        Returns: {A_id: 4, B_id: 3, C_id: 3}
    """
    from api.api_models.user_type import Guard
    
    # Initialize caps with original availability
    caps = {guard.id: guard.availability for guard in eligible_guards}
    
    # Calculate total demand
    total_demand = sum(caps.values())
    
    if total_demand <= total_positions:
        # Everyone can work their desired amount - no capping needed
        logger.info(
            f"No capping needed: demand={total_demand}, supply={total_positions}. "
            f"All guards can work their requested availability."
        )
        return caps
    
    # Need to cap - iteratively reduce highest values
    logger.info(
        f"Capping needed: demand={total_demand}, number of positions={total_positions}. "
        f"Starting iterative reduction..."
    )
    
    # Create priority lookup (lower number = worse priority, gets capped first)
    guard_priorities = {guard.id: guard.priority_number for guard in eligible_guards}
    
    iteration = 0
    while sum(caps.values()) > total_positions:
        iteration += 1
        current_demand = sum(caps.values())
        
        # Find maximum cap value
        max_cap = max(caps.values())
        
        # Find all guards at this maximum
        guards_at_max = [gid for gid, cap in caps.items() if cap == max_cap]
        
        if len(guards_at_max) > 1:
            # Multiple guards at max - find lowest priority among them
            min_priority = min(guard_priorities[gid] for gid in guards_at_max)
            
            # Get ALL guards with this lowest priority (might be multiple with same priority)
            guards_to_cap = [gid for gid in guards_at_max 
                           if guard_priorities[gid] == min_priority]
            
            logger.debug(
                f"Iteration {iteration}: {len(guards_at_max)} guards at max={max_cap}. "
                f"Reducing {len(guards_to_cap)} guard(s) with lowest priority={min_priority:.2f}"
            )
        else:
            # Only one guard at max
            guards_to_cap = guards_at_max
            logger.debug(
                f"Iteration {iteration}: Single guard at max={max_cap}. "
                f"Reducing guard {guards_to_cap[0]}"
            )
        
        # Reduce all selected guards by 1
        for gid in guards_to_cap:
            caps[gid] -= 1
        
        logger.debug(
            f"After iteration {iteration}: demand reduced from {current_demand} to {sum(caps.values())}"
        )
    
    final_demand = sum(caps.values())
    capped_count = sum(1 for gid, cap in caps.items() 
                       if cap < {guard.id: guard.availability for guard in eligible_guards}[gid])
    
    logger.info(
        f"Capping complete after {iteration} iterations. "
        f"Final demand: {final_demand}, supply: {total_positions}. "
        f"{capped_count} guards capped from original availability."
    )
    
    return caps


@shared_task
def award_daily_completions():
    """
    Award points for completed positions from earlier today.
    Runs every day at 23:00.
    
    Awards:
    - 2.00 points for each completed position (award_for_position_completion)
    - 0.50 points instead if Sunday (award_for_sunday_position_completion)
    """
    from api.api_models.user_type import Guard
    
    settings = SystemSettings.get_active()
    now = timezone.now()
    today = now.date()
    
    logger.info(f"Starting daily completion awards for {today}")
    
    # Find all positions from today (by 23:00, all shifts have ended)
    positions_today = Position.objects.filter(date=today)
    
    if not positions_today.exists():
        logger.info(f"No positions found for {today}")
        return f"No positions found for {today}"
    
    awards_given = 0
    total_points_awarded = Decimal('0.00')
    
    # Check each position to find guards who completed them
    for position in positions_today:
        # Get latest history for this position
        latest_history = PositionHistory.objects.filter(
            position=position
        ).order_by('-action_time', '-id').first()
        
        # Award only if position was assigned (ASSIGNED or REPLACED or SWAPPED action)
        if latest_history and latest_history.action in [
            PositionHistory.Action.ASSIGNED,
            PositionHistory.Action.REPLACED,
            PositionHistory.Action.SWAPPED
        ]:
            guard = latest_history.guard
            
            # Determine award amount (0.5 for Sunday, 2.0 for other days)
            is_sunday = position.date.weekday() == 6
            if is_sunday:
                points = Decimal(str(settings.award_for_sunday_position_completion))
                explanation = f"Completed Sunday position ({position.exhibition.name}, {position.date})"
            else:
                points = Decimal(str(settings.award_for_position_completion))
                explanation = f"Completed position ({position.exhibition.name}, {position.date})"
            
            Point.objects.create(
                guard=guard,
                points=points,
                explanation=explanation
            )
            
            awards_given += 1
            total_points_awarded += points
            logger.debug(f"Awarded {points} points to {guard.user.username} for {position.exhibition.name} on {position.date}")
    
    logger.info(
        f"Daily completion awards complete: {awards_given} awards given, "
        f"{total_points_awarded} total points awarded for {today}"
    )
    
    return f"Awarded points for {awards_given} completed positions from {today}"


@shared_task
def check_and_penalize_insufficient_positions():
    """
    Check if it's time to penalize guards for insufficient positions, then execute if needed.
    Runs every Sunday at 22:00 via Celery Beat - checks if manual assignment period just ended.
    
    Executes penalize_insufficient_positions() exactly once when:
    - Current time >= manual_assignment_end_datetime
    - AND penalty hasn't been applied yet for this next_week period (checked in DB)
    """
    settings = SystemSettings.get_active()
    now = timezone.now()
    
    # Check if manual assignment period has ended
    manual_end = settings.manual_assignment_end_datetime
    
    if not manual_end:
        logger.debug("Manual assignment end time not yet calculated - skipping penalty check")
        return "Manual assignment end time not set yet"
    
    if now < manual_end:
        logger.debug(f"Manual assignment period not ended yet. Ends at: {manual_end}")
        return "Manual assignment period still active"
    
    # Check if we've already penalized for this next_week period by looking in DB
    # Look for Point records with "Insufficient positions for week" explanation created after manual_end
    existing_penalties = Point.objects.filter(
        explanation__icontains=f'Insufficient positions for week starting {settings.next_week_start}',
        created_at__gte=manual_end
    )
    
    if existing_penalties.exists():
        logger.debug(f"Penalty already applied for week {settings.next_week_start} - found {existing_penalties.count()} existing records")
        return f"Penalty already applied for this week ({existing_penalties.count()} guards penalized)"
    
    # Run the penalty task
    result = penalize_insufficient_positions()
    
    return result


@shared_task
def penalize_insufficient_positions():
    """
    Penalize guards who took fewer positions than minimum required.
    Runs at the end of manual assignment period (~36h after automated assignment).
    
    Penalty: penalty_for_assigning_less_then_minimal_positions per guard
    Applies to all active guards who took too few positions.
    """
    from api.api_models.user_type import Guard
    
    settings = SystemSettings.get_active()
    
    if not settings.next_week_start or not settings.next_week_end:
        logger.warning("Cannot penalize - next_week period not set")
        return "Cannot penalize - next_week period not set"
    
    logger.info(f"Starting insufficient positions penalty check for next_week: {settings.next_week_start} - {settings.next_week_end}")
    
    # Get all positions for next_week
    next_week_positions = Position.objects.filter(
        date__gte=settings.next_week_start,
        date__lte=settings.next_week_end
    )
    
    # Get all guards who are active
    active_guards = Guard.active_guards.all()
    
    penalties_given = 0
    total_penalty_points = Decimal('0.00')
    
    for guard in active_guards:
        # Count how many next_week positions this guard is currently assigned to
        assigned_positions = []
        
        for position in next_week_positions:
            latest_history = PositionHistory.objects.filter(
                position=position
            ).order_by('-action_time', '-id').first()
            
            if latest_history and latest_history.action in [
                PositionHistory.Action.ASSIGNED,
                PositionHistory.Action.REPLACED,
                PositionHistory.Action.SWAPPED
            ] and latest_history.guard == guard:
                assigned_positions.append(position)
        
        assigned_count = len(assigned_positions)
        minimal_required = settings.minimal_number_of_positions_in_week
        
        if assigned_count < minimal_required:
            penalty = Decimal(str(settings.penalty_for_assigning_less_then_minimal_positions))
            explanation = (
                f"Kazna za nedovoljno upisanih smjena"
                f"({assigned_count}/{minimal_required} pozicija u tjednu {settings.next_week_start})"
            )
            
            Point.objects.create(
                guard=guard,
                points=penalty,
                explanation=explanation
            )
            
            penalties_given += 1
            total_penalty_points += penalty
            logger.debug(
                f"Penalized {guard.user.username}: {assigned_count}/{minimal_required} positions, "
                f"{penalty} points"
            )
    
    logger.info(
        f"Insufficient positions penalty complete: {penalties_given} penalties given, "
        f"{total_penalty_points} total penalty points for week {settings.next_week_start}"
    )
    
    return f"Penalized {penalties_given} guards for insufficient positions"


@shared_task
def expire_swap_requests():
    """
    Expire pending swap requests that have passed position start time.
    
    For each expired swap request:
    - Set status to 'expired'
    - Create PositionHistory with action='cancelled'
    - Assign penalty points (no-show = cancellation on position day)
    
    Runs periodically (weekday: 11:05, 15:05; weekend: 11:05, 14:35)
    """
    from api.api_models.textual_model import PositionSwapRequest
    from django.db import transaction
    
    now = timezone.now()
    
    # Find all pending swap requests that should have expired
    expired_swaps = PositionSwapRequest.objects.filter(
        status='pending',
        expires_at__lte=now
    )
    
    expired_count = 0
    total_penalties = Decimal('0.00')
    
    for swap_request in expired_swaps:
        try:
            with transaction.atomic():
                position = swap_request.position_to_swap
                guard = swap_request.requesting_guard
                settings = SystemSettings.get_active()
                
                # 1. Update swap request status
                swap_request.status = 'expired'
                swap_request.save()
                
                # 2. Create PositionHistory (cancelled)
                PositionHistory.objects.create(
                    position=position,
                    guard=guard,
                    action=PositionHistory.Action.CANCELLED
                )
                
                # 3. Assign penalty (cancellation on position day = strongest penalty)
                penalty = Decimal(str(settings.penalty_for_position_cancellation_on_the_position_day))
                
                Point.objects.create(
                    guard=guard,
                    points=penalty,
                    explanation=(
                        f"Penalty for no-show: Swap request expired for "
                        f"{position.exhibition.name} on {position.date.strftime('%d.%m.%Y')} "
                        f"{position.start_time.strftime('%H:%M')}-{position.end_time.strftime('%H:%M')}"
                    )
                )
                
                expired_count += 1
                total_penalties += abs(penalty)
                
                logger.info(
                    f"Expired swap request {swap_request.id}: "
                    f"Guard {guard.user.username} penalized {penalty} points for "
                    f"position {position.id}"
                )
                
        except Exception as e:
            logger.error(f"Error expiring swap request {swap_request.id}: {e}")
            continue
    
    logger.info(
        f"Swap request expiration complete: {expired_count} requests expired, "
        f"{total_penalties} total penalty points"
    )
    
    return f"Expired {expired_count} swap requests"
