from django.db import models
from django.contrib.postgres.fields import ArrayField
from django.core.exceptions import ValidationError
from .system_settings import SystemSettings


class GuardExhibitionPreference(models.Model):
    """
    Guard's ranked exhibition preferences stored as a single bulk record.
    
    Stores ordered array of exhibition IDs (first = highest priority).
    Can be saved as template for future weeks if exhibition set remains the same.
    
    Template validation: Weekly task compares historical exhibition set
    (from created_at week) with next_week set. If different, template invalidated.
    """
    
    guard = models.ForeignKey(
        'Guard',
        on_delete=models.CASCADE,
        related_name='exhibition_preferences'
    )
    exhibition_order = ArrayField(
        models.IntegerField(),
        help_text="Ordered array of exhibition IDs (first = most preferred)"
    )
    is_template = models.BooleanField(
        default=False,
        help_text="If true, preferences saved for future weeks (validated weekly)"
    )
    next_week_start = models.DateField(
        null=True,
        blank=True,
        help_text="Start date of week these preferences apply to (null if template)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    def clean(self):
        """Validate next_week_start based on is_template."""
        if self.is_template and self.next_week_start is not None:
            raise ValidationError({
                'next_week_start': 'next_week_start must be null when is_template is True'
            })
        if not self.is_template and self.next_week_start is None:
            raise ValidationError({
                'next_week_start': 'next_week_start must be set when is_template is False'
            })
    
    def save(self, *args, **kwargs):
        """Run validation before saving."""
        self.full_clean()
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = "Guard Exhibition Preference"
        verbose_name_plural = "Guard Exhibition Preferences"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['guard', 'is_template']),
            models.Index(fields=['guard', 'next_week_start']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        context = "Template" if self.is_template else f"Week {self.next_week_start}"
        return f"{self.guard.user.username} - {len(self.exhibition_order)} exhibitions ({context})"


class GuardDayPreference(models.Model):
    """
    Guard's ranked day preferences stored as a single bulk record.
    
    Stores ordered array of day_of_week integers (first = highest priority).
    Can be saved as template for future weeks if workday set remains the same.
    
    Template validation: Weekly task compares historical workday set
    (from created_at week) with next_week set. If different, template invalidated.
    """
    
    guard = models.ForeignKey(
        'Guard',
        on_delete=models.CASCADE,
        related_name='day_preferences'
    )
    day_order = ArrayField(
        models.IntegerField(choices=SystemSettings.WEEKDAY_CHOICES),
        help_text="Ordered array of days (0=Mon, 6=Sun, first = most preferred)"
    )
    is_template = models.BooleanField(
        default=False,
        help_text="If true, preferences saved for future weeks (validated weekly)"
    )
    next_week_start = models.DateField(
        null=True,
        blank=True,
        help_text="Start date of week these preferences apply to (null if template)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    def clean(self):
        """Validate next_week_start based on is_template."""
        if self.is_template and self.next_week_start is not None:
            raise ValidationError({
                'next_week_start': 'next_week_start must be null when is_template is True'
            })
        if not self.is_template and self.next_week_start is None:
            raise ValidationError({
                'next_week_start': 'next_week_start must be set when is_template is False'
            })
    
    def save(self, *args, **kwargs):
        """Run validation before saving."""
        self.full_clean()
        super().save(*args, **kwargs)
    
    class Meta:
        verbose_name = "Guard Day Preference"
        verbose_name_plural = "Guard Day Preferences"
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['guard', 'is_template']),
            models.Index(fields=['guard', 'next_week_start']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        context = "Template" if self.is_template else f"Week {self.next_week_start}"
        return f"{self.guard.user.username} - {len(self.day_order)} days ({context})"
