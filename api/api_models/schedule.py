from django.db import models
from django.core.exceptions import ValidationError
from django.utils import timezone


class Exhibition(models.Model):
    """
    Museum exhibition with scheduled positions for guards.
    
    Tracks exhibition details, dates, and rules.
    Contains properties for checking exhibition status (active/upcoming/finished).
    """
    
    name = models.CharField(max_length=255)
    number_of_positions = models.IntegerField(
        help_text="Total number of guard positions needed"
    )
    start_date = models.DateTimeField()
    end_date = models.DateTimeField()
    rules = models.TextField(
        null=True, 
        blank=True,
        help_text="Special rules or instructions for this exhibition"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    # Many-to-many relationship through AdminNotification
    users_from_notifications = models.ManyToManyField(
        'User',
        through='AdminNotification',
        related_name='exhibitions_from_notifications'
    )
    
    class Meta:
        ordering = ['-start_date']
        indexes = [
            models.Index(fields=['-start_date']),
            models.Index(fields=['name']),
        ]
    
    def __str__(self):
        return self.name
    
    @property
    def is_active(self):
        """Check if exhibition is currently running"""
        now = timezone.now()
        return self.start_date <= now <= self.end_date
    
    @property
    def is_upcoming(self):
        """Check if exhibition hasn't started yet"""
        return self.start_date > timezone.now()
    
    @property
    def is_finished(self):
        """Check if exhibition has ended"""
        return self.end_date < timezone.now()
    
    def clean(self):
        """Validate that start_date is before end_date"""
        if self.start_date >= self.end_date:
            raise ValidationError("Exhibition start date must be before end date")


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
        if self.exhibition_id and self.date < self.exhibition.start_date.date():
            raise ValidationError("Position date cannot be before exhibition start")
    
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
        TAKEN_AFTER_LOCKING = "TAKEN_AFTER_LOCKING", "Taken After Locking"
    
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
