import time
from django.db import models
from django.core.cache import cache


class SystemSettings(models.Model):
    """
    Singleton model for system-wide settings.
    Only one instance should exist.
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
    
    day_for_start_of_configuration = models.IntegerField(
        choices=WEEKDAY_CHOICES,
        default=6,  # Sunday
        help_text="Day of the week when configuration starts"
    )
    
    time_of_start_of_configuration = models.TimeField(
        default='18:00',
        help_text="Time when configuration starts"
    )
    
    # Assignment settings
    day_for_assignments = models.IntegerField(
        choices=WEEKDAY_CHOICES,
        default=2,  # Wednesday
        help_text="Day of the week when assignments are published"
    )
    time_of_assignments = models.TimeField(
        default='09:00',
        help_text="Time when assignments are published"
    )
    
    # Point system settings
    points_life_weeks = models.IntegerField(
        default=4,
        help_text="Number of weeks before points expire"
    )
    
    # Position requirements
    minimal_number_of_positions_in_week = models.IntegerField(
        default=1,
        help_text="Minimum positions a guard must take per week"
    )
    
    award_for_position_completion = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=2.00,
        help_text="Points awarded for completing a position"
    )
    
    award_for_sunday_position_done = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=0.50,
        help_text="Points for completing a Sunday position"
    )
    
    award_for_cancelled_position_jumping_in_on_position_day = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=3.00,
        help_text="Points awarded for jumping in on a cancelled position on the position day"
    )
    
    award_for_cancelled_position_jumping_in_before_position_day = models.DecimalField(
        max_digits=5,
        decimal_places=2,
        default=2.00,
        help_text="Points awarded for jumping in on a cancelled position before the position day"
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
        default=-5.00,
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
    
    # Singleton enforcement
    class Meta:
        verbose_name = "System Settings"
        verbose_name_plural = "System Settings"
    
    def save(self, *args, **kwargs):
        """Ensure only one instance exists (singleton pattern)"""
        self.pk = 1
        super().save(*args, **kwargs)
        # Clear cache when settings change
        cache.delete('system_settings')
    
    def delete(self, *args, **kwargs):
        """Prevent deletion of settings"""
        pass
    
    @classmethod
    def load(cls):
        """Load settings from cache or database"""
        settings = cache.get('system_settings')
        if settings is None:
            settings, created = cls.objects.get_or_create(pk=1)
            cache.set('system_settings', settings, 3600)  # Cache for 1 hour
        return settings
    
    def __str__(self):
        return "System Settings"
