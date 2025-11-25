from django.db import models


class AdminNotification(models.Model):
    """
    Notifications for admin users about exhibitions and system events.
    
    Used to alert admins about important events, deadlines, or issues.
    """
    
    user = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        related_name='admin_notifications'
    )
    exhibition = models.ForeignKey(
        'Exhibition',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='admin_notifications',
        help_text="Related exhibition (optional)"
    )
    message = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Admin Notification"
        verbose_name_plural = "Admin Notifications"
    
    def __str__(self):
        return f"{self.user.username}: {self.message[:50]}"


class Report(models.Model):
    """
    Guard reports about their assigned positions.
    
    Guards can submit reports about issues, incidents, or general feedback
    for positions they were assigned to.
    """
    
    guard = models.ForeignKey(
        'Guard',
        on_delete=models.CASCADE,
        related_name='reports'
    )
    position = models.ForeignKey(
        'Position',
        on_delete=models.CASCADE,
        related_name='reports'
    )
    position_explanation = models.TextField(
        null=True, 
        blank=True,
        help_text="Additional context about the position"
    )
    report_text = models.TextField(
        help_text="Main report content"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        indexes = [
            models.Index(fields=['created_at']),
            models.Index(fields=['guard', 'created_at']),
            models.Index(fields=['position', 'created_at']),
        ]
    
    def __str__(self):
        return f"Report by {self.guard.user.username} at {self.created_at}: " \
               f"{self.report_text[:30]}"
