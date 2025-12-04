from django.db import models


class GuardExhibitionPreference(models.Model):
    """
    Guard's ranking preferences for exhibitions.
    
    Tracks the order in which a guard prefers exhibitions.
    Lower ordinal_number = higher preference (1 = most preferred).
    
    If guard doesn't set preferences, no records exist for that guard.
    Normalization and priority calculation happens in the assignment algorithm.
    """
    
    guard = models.ForeignKey(
        'Guard',
        on_delete=models.CASCADE,
        related_name='exhibition_preferences'
    )
    exhibition = models.ForeignKey(
        'Exhibition',
        on_delete=models.CASCADE,
        related_name='guard_preferences'
    )
    ordinal_number = models.PositiveIntegerField(
        help_text="Order of preference: 1 = most preferred, 2 = second, etc."
    )
    created_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('guard', 'exhibition')
        verbose_name = "Guard Exhibition Preference"
        verbose_name_plural = "Guard Exhibition Preferences"
        ordering = ['guard', 'ordinal_number']
        indexes = [
            models.Index(fields=['guard', 'ordinal_number']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.guard.user.username} - {self.exhibition.name}: #{self.ordinal_number}"


class GuardPositionPreference(models.Model):
    """
    Guard's ranking preferences for specific positions.
    
    More granular than exhibition preferences - allows guards to rank
    specific time slots within exhibitions.
    
    Lower ordinal_number = higher preference (1 = most preferred).
    """
    
    guard = models.ForeignKey(
        'Guard',
        on_delete=models.CASCADE,
        related_name='position_preferences'
    )
    position = models.ForeignKey(
        'Position',
        on_delete=models.CASCADE,
        related_name='guard_preferences'
    )
    ordinal_number = models.PositiveIntegerField(
        help_text="Order of preference: 1 = most preferred, 2 = second, etc."
    )
    created_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        unique_together = ('guard', 'position')
        verbose_name = "Guard Position Preference"
        verbose_name_plural = "Guard Position Preferences"
        ordering = ['guard', 'ordinal_number']
        indexes = [
            models.Index(fields=['guard', 'ordinal_number']),
            models.Index(fields=['created_at']),
        ]
    
    def __str__(self):
        return f"{self.guard.user.username} - {self.position.exhibition.name} " \
               f"{self.position.date} {self.position.start_time}: #{self.ordinal_number}"
