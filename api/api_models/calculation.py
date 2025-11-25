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


class GuardAvailablePositions(models.Model):
    """
    Tracks which positions a guard is available for and their calculated score.
    
    Used by the assignment algorithm to match guards to positions.
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
        unique_together = ('guard', 'position')
        verbose_name = "Guard Available Position"
        verbose_name_plural = "Guard Available Positions"
    
    def __str__(self):
        return f"Čuvar: {self.guard.user.username}, " \
               f"pozicija: {self.position.exhibition.name}"
