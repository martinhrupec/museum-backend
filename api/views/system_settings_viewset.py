from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
import structlog

from ..api_models import SystemSettings
from ..serializers import SystemSettingsSerializer
from ..permissions import IsAdminRole
from ..mixins import AuditLogMixin

logger = structlog.get_logger(__name__)


class SystemSettingsViewSet(AuditLogMixin, viewsets.ModelViewSet):
    """
    ViewSet for system settings with version history.
    
    Permissions:
    - All authenticated users can view settings (list/retrieve)
    - Only admins can create and update settings
    - Cannot delete settings
    """
    
    queryset = SystemSettings.objects.all()
    serializer_class = SystemSettingsSerializer
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ['list', 'retrieve', 'current', 'workdays']:
            # All authenticated users can view settings
            return [permissions.IsAuthenticated()]
        else:
            # Only admins can create/update
            return [IsAdminRole()]
    
    def list(self, request, *args, **kwargs):
        """Return only the current active settings"""
        settings = SystemSettings.get_active()
        serializer = self.get_serializer(settings)
        return Response(serializer.data)
    
    def retrieve(self, request, *args, **kwargs):
        """Retrieve specific version (for history viewing)"""
        return super().retrieve(request, *args, **kwargs)
    
    def update(self, request, *args, **kwargs):
        """Update settings in-place (no versioning)"""
        instance = SystemSettings.get_active()
        
        # Capture old values for logging
        old_values = {}
        for field in request.data.keys():
            if hasattr(instance, field):
                old_values[field] = getattr(instance, field)
        
        serializer = self.get_serializer(instance, data=request.data, partial=kwargs.get('partial', False))
        serializer.is_valid(raise_exception=True)
        serializer.save(updated_by=request.user)
        
        # Log changes
        changed_fields = {}
        for field, old_value in old_values.items():
            new_value = getattr(instance, field)
            if str(old_value) != str(new_value):
                changed_fields[field] = {'old': str(old_value), 'new': str(new_value)}
        
        if changed_fields:
            logger.info(
                "system_settings_updated",
                changed_fields=changed_fields,
                user_id=request.user.id,
                username=request.user.username
            )
            
            # Log to audit log
            from ..api_models import AuditLog
            AuditLog.log_update(
                user=request.user,
                instance=instance,
                changed_fields=changed_fields,
                request=request
            )
        
        return Response(serializer.data, status=status.HTTP_200_OK)
    
    def partial_update(self, request, *args, **kwargs):
        """Partial update settings in-place"""
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)
    
    def create(self, request, *args, **kwargs):
        """Create initial settings (only if none exist)"""
        if SystemSettings.objects.filter(is_active=True).exists():
            return Response(
                {'error': 'Aktivne postavke već postoje. Koristite PUT/PATCH za ažuriranje.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        instance = serializer.save(updated_by=request.user, is_active=True)
        
        # Log to audit log
        from ..api_models import AuditLog
        AuditLog.log_create(
            user=request.user,
            instance=instance,
            request=request
        )
        
        return Response(serializer.data, status=status.HTTP_201_CREATED)
    
    def destroy(self, request, *args, **kwargs):
        """Prevent deletion"""
        return Response(
            {'error': 'Sistemske postavke se ne mogu obrisati'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    
    @action(detail=False, methods=['get'])
    def current(self, request):
        """Get current active settings (alias for list)"""
        settings = SystemSettings.get_active()
        serializer = self.get_serializer(settings)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def workdays(self, request):
        """
        Get museum workdays only.
        
        Returns array of integers representing days when museum is open:
        0=Monday, 1=Tuesday, ..., 6=Sunday
        
        GET /api/system-settings/workdays/
        
        Response:
        {
            "workdays": [1, 2, 3, 4, 5, 6]
        }
        """
        settings = SystemSettings.get_active()
        return Response({
            'workdays': settings.workdays
        })
