from rest_framework import viewsets, permissions

from ..api_models import User, GuardDayPreference
from ..serializers import GuardDayPreferenceSerializer
from ..mixins import AuditLogMixin


class GuardDayPreferenceViewSet(AuditLogMixin, viewsets.ReadOnlyModelViewSet):
    """
    ReadOnly ViewSet for guard day preferences (for reporting/viewing).
    
    - Admins can view all preferences
    - Guards can view their own preferences
    - For SETTING preferences, use: POST /api/guards/{id}/set_day_preferences/
    
    This ViewSet is READ-ONLY. All create/update/delete operations must go through
    GuardViewSet.set_day_preferences() for proper validation.
    """
    
    queryset = GuardDayPreference.objects.all()
    serializer_class = GuardDayPreferenceSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter queryset based on user role"""
        if self.request.user.role == User.ROLE_ADMIN:
            return GuardDayPreference.objects.all()
        else:
            # Guards see only their own preferences
            return GuardDayPreference.objects.filter(guard__user=self.request.user)
