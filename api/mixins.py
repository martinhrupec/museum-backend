"""
Mixins for ViewSets to add common functionality.
"""
from .api_models import AuditLog


class AuditLogMixin:
    """
    Mixin that automatically logs all create/update/delete actions to AuditLog.
    
    IMPORTANT: Add this mixin FIRST in the inheritance chain:
        class MyViewSet(AuditLogMixin, viewsets.ModelViewSet):
    
    If your ViewSet has custom perform_create/update/destroy methods, they should:
    1. Call super().perform_create/update/destroy(serializer) instead of serializer.save()
    2. Use the returned instance from super() if needed
    
    Example:
        def perform_create(self, serializer):
            # Custom logic before save
            instance = super().perform_create(serializer)  # This calls mixin + saves + audits
            # Custom logic after save (use instance)
            send_notification(instance)
            return instance
    
    Only logs if request.user is authenticated (skips system/anonymous changes).
    """
    
    def perform_create(self, serializer):
        """Create instance and log to audit trail"""
        # Save the instance
        instance = serializer.save()
        
        # Log only if authenticated user made the change
        if hasattr(self, 'request') and self.request.user.is_authenticated:
            AuditLog.log_create(
                user=self.request.user,
                instance=instance,
                request=self.request
            )
        
        return instance
    
    def perform_update(self, serializer):
        """Update instance and log changes to audit trail"""
        # Capture old values before save
        old_instance = serializer.instance
        old_data = {}
        for field in serializer.validated_data.keys():
            if hasattr(old_instance, field):
                old_data[field] = getattr(old_instance, field)
        
        # Save changes
        instance = serializer.save()
        
        # Log only if authenticated user made changes
        if hasattr(self, 'request') and self.request.user.is_authenticated:
            # Build changed_fields dict with old -> new values
            changed_fields = {}
            for field, new_value in serializer.validated_data.items():
                old_value = old_data.get(field)
                # Compare values (handle different types)
                if str(old_value) != str(new_value):
                    changed_fields[field] = {
                        'old': str(old_value) if old_value is not None else None,
                        'new': str(new_value) if new_value is not None else None
                    }
            
            # Only log if something actually changed
            if changed_fields:
                AuditLog.log_update(
                    user=self.request.user,
                    instance=instance,
                    changed_fields=changed_fields,
                    request=self.request
                )
        
        return instance
    
    def perform_destroy(self, instance):
        """Delete instance and log to audit trail"""
        # Log BEFORE deletion (instance needs to exist)
        if hasattr(self, 'request') and self.request.user.is_authenticated:
            AuditLog.log_delete(
                user=self.request.user,
                instance=instance,
                request=self.request
            )
        
        # Actually delete
        instance.delete()
