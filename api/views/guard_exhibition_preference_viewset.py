from rest_framework import viewsets, permissions

from ..api_models import User, GuardExhibitionPreference
from ..serializers import GuardExhibitionPreferenceSerializer
from ..mixins import AuditLogMixin


class GuardExhibitionPreferenceViewSet(AuditLogMixin, viewsets.ReadOnlyModelViewSet):
    """
    ReadOnly ViewSet for guard exhibition preferences (for reporting/viewing).
    
    - Admins can view all preferences
    - Guards can view their own preferences
    - For SETTING preferences, use: POST /api/guards/{id}/set_exhibition_preferences/
    
    This ViewSet is READ-ONLY. All create/update/delete operations must go through
    GuardViewSet.set_exhibition_preferences() for proper validation.
    """
    
    queryset = GuardExhibitionPreference.objects.all()
    serializer_class = GuardExhibitionPreferenceSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter queryset based on user role"""
        if self.request.user.role == User.ROLE_ADMIN:
            return GuardExhibitionPreference.objects.all()
        else:
            # Guards see only their own preferences
            return GuardExhibitionPreference.objects.filter(guard__user=self.request.user)
