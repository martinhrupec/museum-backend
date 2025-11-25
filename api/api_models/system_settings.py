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
    
    # Assignment settings
    day_for_assignments = models.IntegerField(
        choices=WEEKDAY_CHOICES,
        default=0,  # Monday
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
        default=2,
        help_text="Minimum positions a guard must take per week"
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
