from django.db import models


class AdminNotification(models.Model):
    """
    Notifications/announcements system with three cast types.
    
    Cast Types:
    1. BROADCAST - Shown to all users
       - No additional filters needed
       - Example: "Muzej zatvoren sljedeći tjedan"
    
    2. UNICAST - Shown to specific user (to_user)
       - Requires: to_user
       - Example: "Molimo doći 15 minuta ranije" (to specific guard)
    
    3. MULTICAST - Shown to dynamic group based on position assignments
       - Filters (in order of specificity):
         * notification_date only → all guards working that day
         * notification_date + shift_type → guards in that shift on that day
         * notification_date + exhibition → guards on that exhibition that day
         * notification_date + shift_type + exhibition → most specific
       - Example: "Vodstvo na Egipatskoj izložbi sutra u jutarnjoj smjeni"
       - Target determined by PositionHistory (assigned positions)
    
    System-generated notifications (created_by=None) typically use UNICAST.
    """
    
    CAST_BROADCAST = 'broadcast'
    CAST_UNICAST = 'unicast'
    CAST_MULTICAST = 'multicast'
    CAST_CHOICES = [
        (CAST_BROADCAST, 'Broadcast - Svi korisnici'),
        (CAST_UNICAST, 'Unicast - Specifičan korisnik'),
        (CAST_MULTICAST, 'Multicast - Grupa čuvara na pozicijama'),
    ]
    
    SHIFT_MORNING = 'morning'
    SHIFT_AFTERNOON = 'afternoon'
    SHIFT_CHOICES = [
        (SHIFT_MORNING, 'Jutarnja smjena'),
        (SHIFT_AFTERNOON, 'Popodnevna smjena'),
    ]
    
    # Who created this notification (admin or system)
    created_by = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='created_notifications',
        help_text="Admin who created this notification (null for system-generated)"
    )
    
    # Title of the notification
    title = models.CharField(
        max_length=200,
        help_text="Short notification title"
    )
    
    # Message body
    message = models.TextField(
        help_text="Notification message/content"
    )
    
    # Cast type determines who receives the notification
    cast_type = models.CharField(
        max_length=10,
        choices=CAST_CHOICES,
        default=CAST_BROADCAST,
        help_text="How notification is distributed: broadcast (all), unicast (one user), multicast (group)"
    )
    
    # Target user (for unicast)
    to_user = models.ForeignKey(
        'User',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='targeted_notifications',
        help_text="Target user for unicast notifications"
    )
    
    # Multicast filters: date/shift/exhibition determine target group
    notification_date = models.DateField(
        null=True,
        blank=True,
        help_text="Date for multicast filtering (required for multicast)"
    )
    
    shift_type = models.CharField(
        max_length=10,
        choices=SHIFT_CHOICES,
        null=True,
        blank=True,
        help_text="Shift for multicast filtering (optional, narrows down target group)"
    )
    
    exhibition = models.ForeignKey(
        'Exhibition',
        on_delete=models.CASCADE,
        null=True,
        blank=True,
        related_name='admin_notifications',
        help_text="Exhibition for multicast filtering (optional, narrows down target group)"
    )
    
    # Expiration - when notification stops being visible
    expires_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text=(
            "When notification expires. If not set, auto-calculated: "
            "notification_date end of day OR created_at + 30 days"
        )
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Admin Notification"
        verbose_name_plural = "Admin Notifications"
        indexes = [
            models.Index(fields=['cast_type']),
            models.Index(fields=['notification_date', 'shift_type']),
            models.Index(fields=['to_user']),
            models.Index(fields=['expires_at']),
        ]
    
    def __str__(self):
        parts = []
        
        if self.cast_type == self.CAST_BROADCAST:
            parts.append("[BROADCAST]")
        elif self.cast_type == self.CAST_UNICAST:
            parts.append(f"[UNICAST: {self.to_user.username if self.to_user else 'Unknown'}]")
        elif self.cast_type == self.CAST_MULTICAST:
            parts.append("[MULTICAST]")
            if self.notification_date:
                parts.append(f"[{self.notification_date}]")
            if self.shift_type:
                parts.append(f"[{self.get_shift_type_display()}]")
            if self.exhibition:
                parts.append(f"[{self.exhibition.name}]")
        
        parts.append(self.title)
        
        return " ".join(parts)
    
    def clean(self):
        """Validate notification targeting based on cast_type"""
        from django.core.exceptions import ValidationError
        
        if self.cast_type == self.CAST_UNICAST:
            if not self.to_user:
                raise ValidationError("Unicast notification must have to_user set.")
            
        elif self.cast_type == self.CAST_BROADCAST:
            # Broadcast doesn't need any additional fields
            pass


# Signal to auto-set expires_at if not explicitly provided
from django.db.models.signals import post_save
from django.dispatch import receiver
from datetime import datetime, time, timedelta
import structlog

logger = structlog.get_logger(__name__)


@receiver(post_save, sender=AdminNotification)
def set_notification_expiry(sender, instance, created, **kwargs):
    """
    Auto-calculate expires_at if not explicitly set by admin.
    
    Logic:
    - If expires_at already set by admin → do nothing
    - If notification_date exists → expires_at = end of that day (23:59:59)
    - Otherwise → expires_at = created_at + 30 days
    
    Only runs on creation, not updates (to avoid recursion).
    """
    if created and not instance.expires_at:
        from django.utils import timezone
        
        if instance.notification_date:
            # Set to end of notification_date
            expires_at = timezone.make_aware(
                datetime.combine(instance.notification_date, time(23, 59, 59))
            )
            expiry_type = "notification_date_end"
        else:
            # Set to 30 days from now
            expires_at = timezone.now() + timedelta(days=30)
            expiry_type = "default_30_days"
        
        # Update without triggering signal again
        AdminNotification.objects.filter(pk=instance.pk).update(expires_at=expires_at)
        
        logger.info(
            "notification_expiry_set",
            notification_id=instance.id,
            title=instance.title,
            cast_type=instance.cast_type,
            expires_at=str(expires_at),
            expiry_type=expiry_type
        )


class PositionSwapRequest(models.Model):
    """
    Guard's request to swap their assigned position with another guard.
    
    Eligibility and matching calculated dynamically:
    - Expires at position start time
    - Only one active request per guard
    - Auto-cancels if guard cancels the position
    - No penalties when swap is completed
    """
    
    STATUS_PENDING = 'pending'
    STATUS_ACCEPTED = 'accepted'
    STATUS_EXPIRED = 'expired'
    STATUS_CANCELLED = 'cancelled'
    
    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending'),
        (STATUS_ACCEPTED, 'Accepted'),
        (STATUS_EXPIRED, 'Expired'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]
    
    requesting_guard = models.ForeignKey(
        'Guard',
        on_delete=models.CASCADE,
        related_name='swap_requests_made',
        help_text="Guard requesting to swap their position"
    )
    
    position_to_swap = models.ForeignKey(
        'Position',
        on_delete=models.CASCADE,
        related_name='swap_requests',
        help_text="Position that requesting guard wants to swap away"
    )
    
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING
    )
    
    # Filled when accepted
    accepted_by_guard = models.ForeignKey(
        'Guard',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='swap_requests_accepted',
        help_text="Guard who accepted the swap"
    )
    
    # Filled when accepted
    position_offered_in_return = models.ForeignKey(
        'Position',
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='swap_offers',
        help_text="Position that accepting guard gave in return"
    )
    
    expires_at = models.DateTimeField(
        help_text="Request expires at position start time"
    )
    
    created_at = models.DateTimeField(auto_now_add=True)
    accepted_at = models.DateTimeField(null=True, blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Position Swap Request"
        verbose_name_plural = "Position Swap Requests"
        indexes = [
            models.Index(fields=['status', 'expires_at']),
            models.Index(fields=['requesting_guard', 'status']),
            models.Index(fields=['position_to_swap']),
        ]
        # Only one active swap request per guard
        constraints = [
            models.UniqueConstraint(
                fields=['requesting_guard'],
                condition=models.Q(status='pending'),
                name='one_active_swap_per_guard'
            )
        ]
    
    def __str__(self):
        return f"[{self.status.upper()}] {self.requesting_guard.user.username} " \
               f"wants to swap {self.position_to_swap.exhibition.name} on {self.position_to_swap.date}"


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
