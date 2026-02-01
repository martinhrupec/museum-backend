from datetime import date, datetime, time as time_module, timedelta

from django.db import models
from django.core.cache import cache
from django.contrib.postgres.fields import ArrayField
from django.utils import timezone


def default_workdays():
    """Default museum workdays: Tuesday to Sunday"""
    return [1, 2, 3, 4, 5, 6]


class SystemSettings(models.Model):
    """
    System-wide settings with version history.
    Each update creates a new version instead of modifying existing one.
    """

    _CYCLE_ANCHOR_DATE = date(2024, 1, 1)  # Monday baseline for derived weekday math
    
    WEEKDAY_CHOICES = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]
    
    # Museum working days
    workdays = ArrayField(
        models.IntegerField(choices=WEEKDAY_CHOICES),
        default=default_workdays,  # Callable function
        help_text="Days of the week when museum is open for visitors"
    )
    
    # Current week period - active week (guards are working these positions)
    this_week_start = models.DateField(
        null=True,
        blank=True,
        help_text="Start date of current active week (set by weekly task)"
    )
    this_week_end = models.DateField(
        null=True,
        blank=True,
        help_text="End date of current active week (set by weekly task)"
    )
    
    # Next week period - in configuration (guards are setting preferences for this week)
    next_week_start = models.DateField(
        null=True,
        blank=True,
        help_text="Start date of next week period (set by weekly task)"
    )
    next_week_end = models.DateField(
        null=True,
        blank=True,
        help_text="End date of next week period (set by weekly task)"
    )
    
    # ========================================
    # TIMING CONFIGURATION
    # ========================================
    # Position generation is FIXED: Monday 00:00 (hardcoded in Celery Beat)
    # Configuration start is FIXED: Monday 08:00 (+8h from generation)
    # Configuration end is AUTOMATIC: 1 hour before automated assignment
    # Manual assignment start is AUTOMATIC: 1 hour after automated assignment
    #
    # Admin controls only ONE thing: when automated assignments are published
    
    # Automated assignment (the only admin-controlled timing)
    day_for_assignments = models.IntegerField(
        choices=WEEKDAY_CHOICES,
        default=2,  # Wednesday
        help_text="Day when automated assignments are published (after this, manual assignment period starts)"
    )
    time_of_assignments = models.TimeField(
        default=time_module(19, 0),
        help_text="Time when automated assignments are published"
    )
    
    # Position shift times
    weekday_morning_start = models.TimeField(
        default='11:00',
        help_text="Morning shift start time for weekdays"
    )
    weekday_morning_end = models.TimeField(
        default='15:00',
        help_text="Morning shift end time for weekdays"
    )
    weekday_afternoon_start = models.TimeField(
        default='15:00',
        help_text="Afternoon shift start time for weekdays"
    )
    weekday_afternoon_end = models.TimeField(
        default='19:00',
        help_text="Afternoon shift end time for weekdays"
    )
    weekend_morning_start = models.TimeField(
        default='11:00',
        help_text="Morning shift start time for weekends"
    )
    weekend_morning_end = models.TimeField(
        default='14:30',
        help_text="Morning shift end time for weekends"
    )
    weekend_afternoon_start = models.TimeField(
        default='14:30',
        help_text="Afternoon shift start time for weekends"
    )
    weekend_afternoon_end = models.TimeField(
        default='18:00',
        help_text="Afternoon shift end time for weekends"
    )
    
    # Position requirements
    minimal_number_of_positions_in_week = models.IntegerField(
        default=1,
        help_text="Minimum positions a guard must take per week"
    )
    
    # Point system settings
    points_life_weeks = models.IntegerField(
        default=4,
        help_text="Number of weeks before points expire"
    )
    
    # Awards and penalties
    award_for_position_completion = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=2.00,
        help_text="Points awarded for completing a position"
    )
    
    award_for_sunday_position_completion = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.50,
        help_text="Points for completing a Sunday position"
    )
    
    award_for_jumping_in_on_cancelled_position = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=2.00,
        help_text="Points awarded for jumping in on a cancelled position"
    )
    
    penalty_for_being_late_with_notification = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=-2.00,
        help_text="Points deducted for being late with notification"
    )
    
    penalty_for_being_late_without_notification = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=-6.00,
        help_text="Points deducted for being late without notification"
    )
    
    penalty_for_position_cancellation_on_the_position_day = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=-5.00,
        help_text="Points deducted for canceling a position on the position day"
    )
    
    penalty_for_position_cancellation_before_the_position_day = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=-2.50,
        help_text="Points deducted for canceling a position before the position day"
    )
    
    penalty_for_assigning_less_then_minimal_positions = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=-2.00,
        help_text="Points deducted for assigning fewer than minimal positions"
    )
    
    # Payroll settings
    hourly_rate = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        default=6.56,
        help_text="Hourly pay rate for guards (€/hour)"
    )
    
    # Version tracking
    created_at = models.DateTimeField(auto_now_add=True, null=True)
    updated_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='system_settings_updates',
        help_text="Admin who made this update"
    )
    is_active = models.BooleanField(
        default=True,
        help_text="Whether this is the current active version"
    )
    
    # Singleton enforcement
    class Meta:
        verbose_name = "System Settings"
        verbose_name_plural = "System Settings"
        ordering = ['-created_at']  # Newest first
    
    @property
    def config_start_day(self):
        """Configuration always starts on Monday (fixed)"""
        return 0  # Monday
    
    @property
    def config_start_time(self):
        """Configuration starts 8 hours after position generation (Monday 08:00)"""
        return time_module(8, 0)
    
    def _combine_cycle_datetime(self, day_offset, time_value):
        """Return naive datetime using a fixed Monday anchor for derived values."""
        if time_value is None:
            return None
        day_offset = day_offset or 0
        target_date = self._CYCLE_ANCHOR_DATE + timedelta(days=day_offset)
        return datetime.combine(target_date, time_value)

    def _reference_assignment_datetime(self):
        """Naive datetime for automated assignment within anchor week."""
        return self._combine_cycle_datetime(self.day_for_assignments, self.time_of_assignments)

    def _make_aware_datetime(self, date_value, time_value):
        if date_value is None or time_value is None:
            return None
        naive_dt = datetime.combine(date_value, time_value)
        tz = timezone.get_current_timezone()
        if timezone.is_naive(naive_dt):
            return timezone.make_aware(naive_dt, tz)
        return naive_dt.astimezone(tz)

    def _current_cycle_assignment_datetime(self):
        """Aware datetime for automated assignment in the active weekly cycle."""
        if not self.this_week_start:
            return None
        assignment_date = self.this_week_start + timedelta(days=self.day_for_assignments or 0)
        return self._make_aware_datetime(assignment_date, self.time_of_assignments)

    @property
    def config_end_day(self):
        """Configuration ends 1 hour before automated assignment"""
        reference = self._reference_assignment_datetime()
        if reference is None:
            return 0
        config_end_dt = reference - timedelta(hours=1)
        return config_end_dt.weekday()
    
    @property
    def config_end_time(self):
        """Configuration ends 1 hour before automated assignment"""
        reference = self._reference_assignment_datetime()
        if reference is None:
            return time_module(0, 0)
        config_end_dt = reference - timedelta(hours=1)
        return config_end_dt.time()
    
    @property
    def manual_assignment_day(self):
        """Manual assignment starts 1 hour after automated assignment"""
        reference = self._reference_assignment_datetime()
        if reference is None:
            return 0
        manual_dt = reference + timedelta(hours=1)
        return manual_dt.weekday()
    
    @property
    def manual_assignment_time(self):
        """Manual assignment starts 1 hour after automated assignment"""
        reference = self._reference_assignment_datetime()
        if reference is None:
            return time_module(0, 0)
        manual_dt = reference + timedelta(hours=1)
        return manual_dt.time()

    @property
    def manual_assignment_end_day(self):
        """Manual assignment ends 36 hours after automated assignment."""
        reference = self._reference_assignment_datetime()
        if reference is None:
            return 0
        manual_end_dt = reference + timedelta(hours=36)
        return manual_end_dt.weekday()

    @property
    def manual_assignment_end_time(self):
        """Manual assignment ends 36 hours after automated assignment."""
        reference = self._reference_assignment_datetime()
        if reference is None:
            return time_module(0, 0)
        manual_end_dt = reference + timedelta(hours=36)
        return manual_end_dt.time()

    @property
    def automated_assignment_datetime(self):
        return self._current_cycle_assignment_datetime()

    @property
    def config_start_datetime(self):
        if not self.this_week_start:
            return None
        return self._make_aware_datetime(self.this_week_start, self.config_start_time)

    @property
    def config_end_datetime(self):
        assignment_dt = self.automated_assignment_datetime
        if assignment_dt is None:
            return None
        return assignment_dt - timedelta(hours=1)

    @property
    def manual_assignment_start_datetime(self):
        assignment_dt = self.automated_assignment_datetime
        if assignment_dt is None:
            return None
        return assignment_dt + timedelta(hours=1)

    @property
    def manual_assignment_end_datetime(self):
        """Manual window closes 36 hours after automated assignment."""
        assignment_dt = self.automated_assignment_datetime
        if assignment_dt is None:
            return None
        return assignment_dt + timedelta(hours=36)
    
    @property
    def grace_period_start_datetime(self):
        """Grace period starts 1 hour after automated assignment (same as manual_assignment_start)."""
        return self.manual_assignment_start_datetime
    
    @property
    def grace_period_end_datetime(self):
        """Grace period ends 2 hours after automated assignment (1h grace + normal manual)."""
        assignment_dt = self.automated_assignment_datetime
        if assignment_dt is None:
            return None
        return assignment_dt + timedelta(hours=2)

    @property
    def timing_windows(self):
        """Expose derived timing windows as cycle-relative day/time payloads."""

        def build_payload(day_value, time_value):
            if day_value is None or time_value is None:
                return None
            weekday_map = dict(self.WEEKDAY_CHOICES)
            return {
                'day': day_value,
                'day_label': weekday_map.get(day_value, f'Day {day_value}'),
                'time': time_value.strftime('%H:%M'),
            }

        return {
            'config': {
                'start': build_payload(self.config_start_day, self.config_start_time),
                'end': build_payload(self.config_end_day, self.config_end_time),
            },
            'automated_assignment': {
                'publish': build_payload(self.day_for_assignments, self.time_of_assignments),
            },
            'manual_assignment': {
                'start': build_payload(self.manual_assignment_day, self.manual_assignment_time),
                'end': build_payload(self.manual_assignment_end_day, self.manual_assignment_end_time),
            },
        }
    
    def save(self, *args, **kwargs):
        """
        Save new version, validate timing, and invalidate cache.
        
        Validation: Assignment must be between 12h and 40h after cycle start (Monday 00:00)
        This ensures: 8h for config start + minimum 4h configuration period
        while keeping manual assignment window inside the same working week.
        """
        from django.core.exceptions import ValidationError
        
        def hours_from_cycle_start(day, time_obj):
            """Calculate hours elapsed from cycle start (Monday 00:00)"""
            # Monday=0, so days_offset is just the day itself
            hours = day * 24
            hours += time_obj.hour + time_obj.minute / 60
            return hours
        
        def describe_offset(hours_value):
            weekday_map = dict(self.WEEKDAY_CHOICES)
            day_index = int(hours_value // 24)
            remainder = hours_value - day_index * 24
            hour_value = int(remainder)
            minute_value = int(round((remainder - hour_value) * 60))
            day_label = weekday_map.get(day_index % 7, f"Day {day_index}")
            return f"{day_label} {hour_value:02d}:{minute_value:02d}"

        assignment_hours = hours_from_cycle_start(
            self.day_for_assignments,
            self.time_of_assignments
        )
        
        MIN_HOURS_FROM_CYCLE_START = 12  # 8h config start + 4h minimum config period
        MAX_HOURS_FROM_CYCLE_START = 67  # Wednesday 19:00 - latest allowed assignment time
        
        if assignment_hours < MIN_HOURS_FROM_CYCLE_START:
            raise ValidationError(
                f"Automated assignment must be at least {MIN_HOURS_FROM_CYCLE_START} hours after cycle start (Monday 00:00). "
                f"This ensures configuration period (Monday 08:00 to 1h before assignment) is sufficient. "
                f"Current assignment: {self.get_day_for_assignments_display()} at {self.time_of_assignments.strftime('%H:%M')} "
                f"({assignment_hours:.1f}h from cycle start). "
                f"Earliest allowed: {describe_offset(MIN_HOURS_FROM_CYCLE_START)}."
            )

        if assignment_hours > MAX_HOURS_FROM_CYCLE_START:
            raise ValidationError(
                f"Automated assignment must be no later than {MAX_HOURS_FROM_CYCLE_START} hours after cycle start (Monday 00:00). "
                f"Current assignment: {self.get_day_for_assignments_display()} at {self.time_of_assignments.strftime('%H:%M')} "
                f"({assignment_hours:.1f}h from cycle start). "
                f"Latest allowed: {describe_offset(MAX_HOURS_FROM_CYCLE_START)}."
            )
        
        # If this is being set as active, deactivate all others
        if self.is_active:
            SystemSettings.objects.filter(is_active=True).update(is_active=False)
        
        super().save(*args, **kwargs)
        
        # Update cache with latest active version
        if self.is_active:
            cache.set('system_settings', self, 3600)  # Cache for 1 hour
    
    def delete(self, *args, **kwargs):
        """Prevent deletion of settings"""
        raise Exception("System settings cannot be deleted")
    
    @classmethod
    def load(cls):
        """Load current active settings from cache or database"""
        settings = cache.get('system_settings')
        if settings is None:
            settings = cls.objects.filter(is_active=True).first()
            if settings is None:
                # Create default settings if none exist
                settings = cls.objects.create(is_active=True)
            cache.set('system_settings', settings, 3600)  # Cache for 1 hour
        return settings
    
    @classmethod
    def get_active(cls):
        """Alias for load() - get current active settings"""
        return cls.load()


class HourlyRateHistory(models.Model):
    """
    Tracks historical changes to hourly pay rate.
    
    Used to calculate accurate earnings for positions worked in the past,
    ensuring guards are paid with the rate that was active at that time.
    """
    
    hourly_rate = models.DecimalField(
        max_digits=6,
        decimal_places=2,
        help_text="Hourly pay rate (€/hour)"
    )
    effective_from = models.DateTimeField(
        help_text="When this rate became effective"
    )
    changed_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='hourly_rate_changes',
        help_text="Admin who changed the rate"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-effective_from']
        verbose_name_plural = "Hourly Rate History"
        indexes = [
            models.Index(fields=['-effective_from']),
        ]
    
    def __str__(self):
        return f"€{self.hourly_rate}/h from {self.effective_from.date()}"
    
    @classmethod
    def get_rate_for_date(cls, target_datetime):
        """
        Get the hourly rate that was active on a specific date.
        
        Args:
            target_datetime: datetime when position was worked
            
        Returns:
            Decimal: hourly rate that was active at that time
        """
        rate_entry = cls.objects.filter(
            effective_from__lte=target_datetime
        ).order_by('-effective_from').first()
        
        if rate_entry:
            return rate_entry.hourly_rate
        
        # Fallback to current SystemSettings if no history exists
        from .system_settings import SystemSettings
        settings = SystemSettings.get_active()
        return settings.hourly_rate
    
    def __str__(self):
        return f"€{self.hourly_rate}/h from {self.effective_from.date()}"


# Signal to track hourly rate changes
from django.db.models.signals import post_save
from django.dispatch import receiver
import structlog

logger = structlog.get_logger(__name__)


@receiver(post_save, sender=SystemSettings)
def track_hourly_rate_change(sender, instance, created, **kwargs):
    """
    Automatically create HourlyRateHistory entry when hourly_rate changes.
    
    This ensures we have historical record of all pay rate changes
    for accurate earnings calculations.
    """
    if not instance.is_active:
        # Only track changes to active settings
        return
    
    # Check if hourly_rate changed (or if this is first active settings)
    latest_rate = HourlyRateHistory.objects.order_by('-effective_from').first()
    
    should_create_entry = False
    old_rate = None
    
    if not latest_rate:
        # No history exists yet - create first entry
        should_create_entry = True
    elif latest_rate.hourly_rate != instance.hourly_rate:
        # Rate changed - create new entry
        should_create_entry = True
        old_rate = latest_rate.hourly_rate
    
    if should_create_entry:
        HourlyRateHistory.objects.create(
            hourly_rate=instance.hourly_rate,
            effective_from=instance.created_at or timezone.now(),
            changed_by=instance.updated_by
        )
        
        logger.info(
            "hourly_rate_changed",
            old_rate=float(old_rate) if old_rate else None,
            new_rate=float(instance.hourly_rate),
            effective_from=str(instance.created_at or timezone.now()),
            changed_by_id=instance.updated_by.id if instance.updated_by else None
        )
