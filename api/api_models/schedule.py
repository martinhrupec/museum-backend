from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone
from django.contrib.postgres.fields import ArrayField
import structlog

logger = structlog.get_logger(__name__)


def default_open_days():
    """
    Default value for Exhibition.open_on field.
    Returns all workdays from active SystemSettings.
    This must be a function (callable) for Django migrations.
    """
    from .system_settings import SystemSettings
    try:
        settings = SystemSettings.get_active()
        return settings.workdays
    except:
        # Fallback if no settings exist yet (e.g., during initial migration)
        return [0, 1, 2, 3, 4, 5, 6]  # All days


class Exhibition(models.Model):
    """
    Museum exhibition with scheduled positions for guards.
    
    Tracks exhibition details, dates, and rules.
    Contains properties for checking exhibition status (active/upcoming/finished).
    """
    
    WEEKDAY_CHOICES = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]
    
    name = models.CharField(max_length=255)
    number_of_positions = models.IntegerField(
        help_text="Total number of guard positions needed"
    )
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    is_special_event = models.BooleanField(
        default=False,
        help_text="True if this is a one-time special event (opening, special occasion), False for regular exhibitions"
    )
    event_start_time = models.TimeField(
        null=True,
        blank=True,
        help_text="Start time for special event (required if is_special_event=True)"
    )
    event_end_time = models.TimeField(
        null=True,
        blank=True,
        help_text="End time for special event (required if is_special_event=True)"
    )
    open_on = ArrayField(
        models.IntegerField(choices=WEEKDAY_CHOICES),
        default=default_open_days,
        help_text="Days of the week when this exhibition is open (subset of museum workdays)"
    )
    rules = models.TextField(
        null=True, 
        blank=True,
        help_text="Special rules or instructions for this exhibition"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['-start_date']),
            models.Index(fields=['name']),
        ]
    
    def __str__(self):
        return self.name
    
    def is_active(self, someday=None):
        """Check if exhibition is active on a given day (defaults to now)"""
        if someday is None:
            someday = timezone.now()
        return self.start_date <= someday <= self.end_date
    
    @property
    def is_upcoming(self):
        """Check if exhibition hasn't started yet"""
        return self.start_date > timezone.now()
    
    @property
    def is_finished(self):
        """Check if exhibition has ended"""
        return self.end_date < timezone.now()
    
    def clean(self):
        """Validate fields based on whether this is a special event or regular exhibition"""
        if self.is_special_event:
            # Special event validation
            if self.start_date.date() != self.end_date.date():
                raise ValidationError("Special events must have start_date and end_date on the same day")
            
            if not self.event_start_time:
                raise ValidationError("Special events require event_start_time")
            
            if not self.event_end_time:
                raise ValidationError("Special events require event_end_time")
            
            if self.event_start_time >= self.event_end_time:
                raise ValidationError("Event start time must be before end time")
        else:
            # Regular exhibition validation
            if self.start_date >= self.end_date:
                raise ValidationError("Exhibition start date must be before end date")
            
            # Validate open_on is subset of SystemSettings.workdays (for regular exhibitions only)
            from .system_settings import SystemSettings
            try:
                settings = SystemSettings.get_active()
                if not set(self.open_on).issubset(set(settings.workdays)):
                    raise ValidationError(
                        f"Exhibition open_on days must be a subset of museum workdays. "
                        f"Museum workdays: {settings.workdays}, Exhibition days: {self.open_on}"
                    )
            except:
                # If no settings exist yet, skip validation
                pass


class Position(models.Model):
    """
    A specific guard position within an exhibition.
    
    Represents a time slot that needs to be filled by a guard.
    """
    
    exhibition = models.ForeignKey(
        Exhibition,
        on_delete=models.CASCADE,
        related_name='positions'
    )
    date = models.DateField()
    start_time = models.TimeField()
    end_time = models.TimeField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['date', 'start_time']
        indexes = [
            models.Index(fields=['date', 'start_time']),
            models.Index(fields=['exhibition', 'date']),
            models.Index(fields=['date']),
        ]
    
    def clean(self):
        """Validate time and date constraints"""
        if self.start_time >= self.end_time:
            raise ValidationError("Start time must be before end time")
        if self.exhibition_id:
            if self.date < self.exhibition.start_date.date():
                raise ValidationError("Position date cannot be before exhibition start")
            
            # Special event positions must be on the event date
            # Only check if exhibition is already saved (has pk)
            if self.exhibition.pk and self.exhibition.is_special_event:
                if self.date != self.exhibition.start_date.date():
                    raise ValidationError("Special event positions must be on the event date")
    
    @property
    def is_special_event(self):
        """Check if this position is for a special event"""
        return self.exhibition.is_special_event if self.exhibition_id else False
    
    def get_duration_hours(self):
        """
        Calculate duration of position in hours.
        
        Returns:
            Decimal: Duration in hours (e.g., 4.0, 3.5)
        """
        from datetime import datetime, timedelta
        from decimal import Decimal
        
        # Create datetime objects for calculation
        start_dt = datetime.combine(self.date, self.start_time)
        end_dt = datetime.combine(self.date, self.end_time)
        
        # Calculate duration
        duration = end_dt - start_dt
        hours = Decimal(duration.total_seconds()) / Decimal(3600)
        
        return hours
    
    def get_period(self, settings):
        """
        Returns 'this_week', 'next_week', or None for this position and given settings.
        """
        if hasattr(settings, 'this_week_start') and hasattr(settings, 'this_week_end'):
            if settings.this_week_start and settings.this_week_end:
                if settings.this_week_start <= self.date <= settings.this_week_end:
                    return 'this_week'
        if hasattr(settings, 'next_week_start') and hasattr(settings, 'next_week_end'):
            if settings.next_week_start and settings.next_week_end:
                if settings.next_week_start <= self.date <= settings.next_week_end:
                    return 'next_week'
        return None
    
    def get_assigned_guard(self):
        """
        Get currently assigned guard for this position based on latest PositionHistory.
        
        Logic:
        - Take most recent PositionHistory entry for this position
        - If action == CANCELLED → position is empty (return None)
        - Otherwise → guard in that entry is the assigned guard
        
        Returns:
            Guard object or None
        """
        latest_history = self.position_histories.order_by('-action_time').first()
        
        if not latest_history:
            return None
        
        if latest_history.action == PositionHistory.Action.CANCELLED:
            return None  # Position is empty
        
        return latest_history.guard
    
    def get_start_datetime(self):
        """
        Return timezone-aware datetime when this position starts.
        
        Returns:
            Timezone-aware datetime object
        """
        from datetime import datetime
        tz = timezone.get_current_timezone()
        naive = datetime.combine(self.date, self.start_time)
        if timezone.is_naive(naive):
            return timezone.make_aware(naive, tz)
        return naive.astimezone(tz)
    
    def __str__(self):
        return f"Pozicija: {self.exhibition.name}, datum: {self.date}" \
               f" od {self.start_time} do {self.end_time}"


class PositionHistory(models.Model):
    """
    Audit trail for position assignments and changes.
    
    Tracks all actions taken on positions (assigned, cancelled, replaced, etc).
    """
    
    class Action(models.TextChoices):
        ASSIGNED = "ASSIGNED", "Assigned"
        CANCELLED = "CANCELED", "Cancelled"
        REPLACED = "REPLACED", "Replaced"
        SWAPPED = "SWAPPED", "Swapped"
    
    position = models.ForeignKey(
        Position,
        on_delete=models.CASCADE,
        related_name='position_histories'
    )
    guard = models.ForeignKey(
        'Guard',
        on_delete=models.CASCADE,
        related_name='position_histories'
    )
    action = models.CharField(max_length=25, choices=Action.choices)
    action_time = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name_plural = "Position Histories"
        indexes = [
            models.Index(fields=['position', 'action_time']),
            models.Index(fields=['guard', 'action_time']),
            models.Index(fields=['action']),
        ]
    
    def __str__(self):
        return f"Pozicija: {self.position.exhibition.name}, " \
               f"čuvar: {self.guard.user.username} - akcija: {self.action} - {self.action_time}"


class NonWorkingDay(models.Model):
    """
    Non-working days or half-days when positions should not be generated.
    
    Used to mark holidays, special events, or maintenance days.
    """
    
    class ShiftType(models.TextChoices):
        MORNING = "MORNING", "Morning"
        AFTERNOON = "AFTERNOON", "Afternoon"
    
    date = models.DateField(unique=True)
    is_full_day = models.BooleanField(
        default=True,
        help_text="If True, entire day is non-working. If False, only one shift."
    )
    non_working_shift = models.CharField(
        max_length=10,
        choices=ShiftType.choices,
        null=True,
        blank=True,
        help_text="Which shift is non-working (only if is_full_day=False)"
    )
    reason = models.TextField(
        null=True,
        blank=True,
        help_text="Reason for non-working day (holiday, maintenance, etc.)"
    )
    created_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='non_working_days_created'
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['date']
        indexes = [
            models.Index(fields=['date']),
        ]
    
    def __str__(self):
        if self.is_full_day:
            return f"Non-working day: {self.date}"
        else:
            return f"Non-working {self.non_working_shift}: {self.date}"
    
    def delete_affected_positions(self):
        """
        Delete positions affected by this non-working day.
        This includes deleting associated PositionHistory records (CASCADE).
        
        Returns:
            int: Number of positions deleted
        """
        from .system_settings import SystemSettings
        
        settings = SystemSettings.load()
        
        # Determine shift times to delete
        if self.is_full_day:
            # Delete all positions on this date
            deleted_count, _ = Position.objects.filter(date=self.date).delete()
            logger.info(
                "deleted_positions_for_non_working_day",
                date=str(self.date),
                is_full_day=True,
                deleted_count=deleted_count
            )
            return deleted_count
        else:
            # Delete only specific shift
            is_weekend = self.date.weekday() in [5, 6]
            
            if self.non_working_shift == self.ShiftType.MORNING:
                if is_weekend:
                    start_time = settings.weekend_morning_start
                else:
                    start_time = settings.weekday_morning_start
            else:  # AFTERNOON
                if is_weekend:
                    start_time = settings.weekend_afternoon_start
                else:
                    start_time = settings.weekday_afternoon_start
            
            deleted_count, _ = Position.objects.filter(
                date=self.date,
                start_time=start_time
            ).delete()
            
            logger.info(
                "deleted_positions_for_non_working_day",
                date=str(self.date),
                is_full_day=False,
                shift=self.non_working_shift,
                deleted_count=deleted_count
            )
            
            return deleted_count


# ========================================
# SIGNALS
# ========================================

from django.db.models.signals import post_save
from django.dispatch import receiver
from datetime import time, timedelta


@receiver(post_save, sender=Exhibition)
def generate_positions_on_exhibition_create(sender, instance, created, **kwargs):
    """
    Automatically generate positions when a new exhibition is created,
    if it overlaps with the this_week/next_week period defined in SystemSettings.
    
    This ensures positions are created regardless of how the exhibition is added
    (API, Django admin, shell, management command, etc.)
    """
    # Only run on creation, not updates
    if not created:
        return
    
    # Skip if signal is disabled (useful for bulk imports)
    if kwargs.get('skip_position_generation', False):
        return
    
    exhibition = instance
    from .system_settings import SystemSettings
    settings = SystemSettings.get_active()
    
    # Check if this_week and next_week periods are defined
    if not (settings.this_week_start and settings.this_week_end and 
            settings.next_week_start and settings.next_week_end):
        logger.info(
            "position_generation_skipped",
            exhibition_id=exhibition.id,
            exhibition_name=exhibition.name,
            reason="weekly_periods_not_configured"
        )
        return
    
    # Calculate the full period from this_week_start to next_week_end
    period_start = settings.this_week_start
    period_end = settings.next_week_end
    
    # Check if exhibition overlaps with this period
    # Convert exhibition dates to dates for comparison
    exhibition_start_date = exhibition.start_date.date()
    exhibition_end_date = exhibition.end_date.date()
    
    # Check if there's any overlap
    if exhibition_start_date <= period_end and exhibition_end_date >= period_start:
        logger.info(
            "position_generation_started",
            exhibition_id=exhibition.id,
            exhibition_name=exhibition.name,
            is_special_event=exhibition.is_special_event,
            period_start=str(period_start),
            period_end=str(period_end)
        )
        
        # Generate positions for the exhibition
        positions_created = _generate_positions_for_exhibition(
            exhibition, 
            period_start, 
            period_end, 
            settings
        )
        
        logger.info(
            "position_generation_completed",
            exhibition_id=exhibition.id,
            exhibition_name=exhibition.name,
            positions_created=positions_created
        )
    else:
        logger.info(
            "position_generation_skipped",
            exhibition_id=exhibition.id,
            exhibition_name=exhibition.name,
            reason="no_period_overlap",
            exhibition_start=str(exhibition_start_date),
            exhibition_end=str(exhibition_end_date),
            period_start=str(period_start),
            period_end=str(period_end)
        )


def _generate_special_event_positions(exhibition, period_start, period_end):
    """
    Generate positions for a special event.
    
    Special events:
    - Occur on a single day (start_date == end_date)
    - Use event_start_time and event_end_time instead of shifts
    - Create number_of_positions for the event time slot
    
    Args:
        exhibition: Exhibition instance (with is_special_event=True)
        period_start: Start date of the period
        period_end: End date of the period
        
    Returns:
        int: Number of positions created
    """
    event_date = exhibition.start_date.date()
    
    # Check if event date falls within the period
    if not (period_start <= event_date <= period_end):
        return 0
    
    created_count = 0
    
    # Create positions for the special event
    for _ in range(exhibition.number_of_positions):
        Position.objects.create(
            exhibition=exhibition,
            date=event_date,
            start_time=exhibition.event_start_time,
            end_time=exhibition.event_end_time
        )
        created_count += 1
    
    return created_count


def _generate_positions_for_exhibition(exhibition, period_start, period_end, settings):
    """
    Generate positions for a specific exhibition within a given period.
    Based on the generate_weekly_positions task logic.
    
    Args:
        exhibition: Exhibition instance
        period_start: Start date of the period
        period_end: End date of the period
        settings: SystemSettings instance
        
    Returns:
        int: Number of positions created
    """
    # Special handling for special events
    if exhibition.is_special_event:
        return _generate_special_event_positions(exhibition, period_start, period_end)
    
    # Convert to timezone-aware datetime for filtering
    period_start_dt = timezone.make_aware(
        timezone.datetime.combine(period_start, time.min)
    )
    period_end_dt = timezone.make_aware(
        timezone.datetime.combine(period_end, time.max)
    )
    
    # Get non-working days for the period
    non_working_days = NonWorkingDay.objects.filter(
        date__gte=period_start,
        date__lte=period_end
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
    
    created_count = 0
    current_date = period_start
    
    while current_date <= period_end:
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
        current_datetime = timezone.make_aware(
            timezone.datetime.combine(current_date, time.min)
        )
        if exhibition.is_active(current_datetime):
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
    
    return created_count
