from django.db import models


class Point(models.Model):
    """
    Points awarded to guards for various actions or achievements.
    
    Used in the scoring system to track guard performance.
    """
    
    guard = models.ForeignKey(
        'Guard',
        on_delete=models.CASCADE,
        related_name='points'
    )
    points = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        help_text="Point value (can be positive or negative)"
    )
    date_awarded = models.DateTimeField(auto_now_add=True)
    explanation = models.TextField(
        help_text="Reason for awarding/deducting points"
    )
    
    class Meta:
        verbose_name_plural = "Points"
        ordering = ['-date_awarded']
        indexes = [
            models.Index(fields=['date_awarded']),
            models.Index(fields=['guard', 'date_awarded']),
        ]
    
    def __str__(self):
        return f"{self.guard.user.username}: {self.points} pts - {self.explanation[:30]}"


class GuardWorkPeriod(models.Model):
    """
    Tracks time periods when a guard is available to work.
    
    Guards select days and shifts (morning/afternoon) they can work,
    and the system dynamically calculates which positions match these periods.
    """
    
    SHIFT_CHOICES = [
        ('morning', 'Morning'),
        ('afternoon', 'Afternoon'),
    ]
    
    WEEKDAY_CHOICES = [
        (0, 'Monday'),
        (1, 'Tuesday'),
        (2, 'Wednesday'),
        (3, 'Thursday'),
        (4, 'Friday'),
        (5, 'Saturday'),
        (6, 'Sunday'),
    ]
    
    guard = models.ForeignKey(
        'Guard',
        on_delete=models.CASCADE,
        related_name='work_periods'
    )
    day_of_week = models.IntegerField(
        choices=WEEKDAY_CHOICES,
        help_text="Day of the week (0=Monday, 6=Sunday)"
    )
    shift_type = models.CharField(
        max_length=10,
        choices=SHIFT_CHOICES,
        help_text="Type of shift (morning or afternoon)"
    )
    is_template = models.BooleanField(
        default=False,
        help_text="If true, this period is saved for future weeks"
    )
    next_week_start = models.DateField(
        null=True,
        blank=True,
        help_text="Start date of the week this period applies to (null if template)"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Guard Work Period"
        verbose_name_plural = "Guard Work Periods"
        ordering = ['guard', 'day_of_week', 'shift_type']
        indexes = [
            models.Index(fields=['guard', 'is_template']),
            models.Index(fields=['guard', 'next_week_start']),
            models.Index(fields=['guard', 'day_of_week', 'shift_type']),
        ]
    
    def __str__(self):
        week_info = f"Template" if self.is_template else f"Week {self.next_week_start}"
        return f"{self.guard.user.username}: {self.get_day_of_week_display()} {self.shift_type} ({week_info})"


class GuardAvailablePositions(models.Model):
    """
    DEPRECATED: This model is being replaced by GuardWorkPeriod.
    
    Previously tracked which positions a guard is available for.
    New system: guards select time periods, positions are calculated dynamically.
    """
    
    guard = models.ForeignKey(
        'Guard',
        on_delete=models.CASCADE,
        related_name='guard_available_positions'
    )
    position = models.ForeignKey(
        'Position',
        on_delete=models.CASCADE,
        related_name='guard_available_positions'
    )
    score = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Calculated suitability score for this guard-position match"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        verbose_name = "Guard Available Position"
        verbose_name_plural = "Guard Available Positions"
        ordering = ['-created_at']  # Najnoviji prvi
        indexes = [
            models.Index(fields=['guard', 'position', 'created_at']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"Čuvar: {self.guard.user.username}, " \
               f"pozicija: {self.position.exhibition.name} ({self.created_at.strftime('%Y-%m-%d %H:%M')})"
