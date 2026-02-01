"""
Audit Log model for tracking admin actions.

Logs all critical administrative changes for compliance and accountability.
"""

from django.db import models
from django.contrib.postgres.fields import JSONField
from django.utils import timezone


class AuditLog(models.Model):
    """
    Audit trail for administrative actions.
    
    Tracks who changed what, when, and what the changes were.
    Used for compliance, debugging, and accountability.
    """
    
    class Action(models.TextChoices):
        CREATE = 'CREATE', 'Created'
        UPDATE = 'UPDATE', 'Updated'
        DELETE = 'DELETE', 'Deleted'
        BULK_UPDATE = 'BULK_UPDATE', 'Bulk Updated'
        BULK_DELETE = 'BULK_DELETE', 'Bulk Deleted'
    
    # Who did it?
    user = models.ForeignKey(
        'User',
        on_delete=models.SET_NULL,
        null=True,
        related_name='audit_logs',
        help_text="User who performed the action"
    )
    
    # What was done?
    action = models.CharField(
        max_length=20,
        choices=Action.choices,
        help_text="Type of action performed"
    )
    
    # On which object?
    model_name = models.CharField(
        max_length=100,
        help_text="Name of the model that was changed (e.g., 'Exhibition', 'SystemSettings')"
    )
    object_id = models.CharField(
        max_length=255,
        null=True,
        blank=True,
        help_text="ID of the object that was changed (null for bulk operations)"
    )
    object_repr = models.CharField(
        max_length=255,
        help_text="String representation of the object (e.g., 'Ancient Egypt Exhibition')"
    )
    
    # What changed?
    changes = models.JSONField(
        default=dict,
        blank=True,
        help_text="Dictionary of field changes: {'field_name': {'old': ..., 'new': ...}}"
    )
    
    # Additional context
    ip_address = models.GenericIPAddressField(
        null=True,
        blank=True,
        help_text="IP address of the user who made the change"
    )
    user_agent = models.TextField(
        blank=True,
        help_text="User agent string (browser/app info)"
    )
    
    # When?
    timestamp = models.DateTimeField(
        default=timezone.now,
        db_index=True,
        help_text="When the action was performed"
    )
    
    class Meta:
        verbose_name = "Audit Log"
        verbose_name_plural = "Audit Logs"
        ordering = ['-timestamp']
        indexes = [
            models.Index(fields=['-timestamp']),
            models.Index(fields=['user', '-timestamp']),
            models.Index(fields=['model_name', '-timestamp']),
            models.Index(fields=['model_name', 'object_id']),
        ]
    
    def __str__(self):
        return f"{self.user} {self.action} {self.model_name} at {self.timestamp.strftime('%Y-%m-%d %H:%M')}"
    
    @classmethod
    def log_create(cls, user, instance, request=None):
        """
        Log object creation.
        
        Args:
            user: User who created the object
            instance: Django model instance that was created
            request: HTTP request object (optional, for IP/user agent)
        """
        return cls.objects.create(
            user=user,
            action=cls.Action.CREATE,
            model_name=instance.__class__.__name__,
            object_id=str(instance.pk),
            object_repr=str(instance),
            changes={},
            ip_address=cls._get_client_ip(request) if request else None,
            user_agent=request.META.get('HTTP_USER_AGENT', '') if request else '',
        )
    
    @classmethod
    def log_update(cls, user, instance, changed_fields, request=None):
        """
        Log object update with field changes.
        
        Args:
            user: User who updated the object
            instance: Django model instance that was updated
            changed_fields: Dict of {field_name: {'old': old_value, 'new': new_value}}
            request: HTTP request object (optional)
        """
        return cls.objects.create(
            user=user,
            action=cls.Action.UPDATE,
            model_name=instance.__class__.__name__,
            object_id=str(instance.pk),
            object_repr=str(instance),
            changes=changed_fields,
            ip_address=cls._get_client_ip(request) if request else None,
            user_agent=request.META.get('HTTP_USER_AGENT', '') if request else '',
        )
    
    @classmethod
    def log_delete(cls, user, instance, request=None):
        """
        Log object deletion.
        
        Args:
            user: User who deleted the object
            instance: Django model instance that was deleted
            request: HTTP request object (optional)
        """
        return cls.objects.create(
            user=user,
            action=cls.Action.DELETE,
            model_name=instance.__class__.__name__,
            object_id=str(instance.pk),
            object_repr=str(instance),
            changes={},
            ip_address=cls._get_client_ip(request) if request else None,
            user_agent=request.META.get('HTTP_USER_AGENT', '') if request else '',
        )
    
    @staticmethod
    def _get_client_ip(request):
        """Extract client IP from request (handles proxies)"""
        x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
        if x_forwarded_for:
            ip = x_forwarded_for.split(',')[0]
        else:
            ip = request.META.get('REMOTE_ADDR')
        return ip
