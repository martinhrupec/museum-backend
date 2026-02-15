from rest_framework import viewsets, permissions
from django_filters import rest_framework as filters

from ..api_models import User, GuardExhibitionPreference
from ..serializers import GuardExhibitionPreferenceSerializer
from ..mixins import AuditLogMixin


class GuardExhibitionPreferenceFilter(filters.FilterSet):
    """Filter for GuardExhibitionPreference"""
    guard = filters.NumberFilter(field_name='guard__id')
    is_template = filters.BooleanFilter(field_name='is_template')
    next_week_start = filters.DateFilter(field_name='next_week_start')
    
    class Meta:
        model = GuardExhibitionPreference
        fields = ['guard', 'is_template', 'next_week_start']


class GuardExhibitionPreferenceViewSet(AuditLogMixin, viewsets.ReadOnlyModelViewSet):
    """
    ReadOnly ViewSet for guard exhibition preferences (for reporting/viewing).
    
    - Admins can view all preferences
    - Guards can view their own preferences
    - For SETTING preferences, use: POST /api/guards/{id}/set_exhibition_preferences/
    
    This ViewSet is READ-ONLY. All create/update/delete operations must go through
    GuardViewSet.set_exhibition_preferences() for proper validation.
    
    Filtering:
    - ?guard={id} - filter by guard ID
    - ?is_template=true/false - filter template vs specific week preferences
    - ?next_week_start=YYYY-MM-DD - filter by specific week
    """
    
    queryset = GuardExhibitionPreference.objects.all()
    serializer_class = GuardExhibitionPreferenceSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_class = GuardExhibitionPreferenceFilter
    
    def get_queryset(self):
        """Filter queryset based on user role"""
        if self.request.user.role == User.ROLE_ADMIN:
            return GuardExhibitionPreference.objects.all().select_related('guard__user', 'exhibition')
        else:
            # Guards see only their own preferences
            return GuardExhibitionPreference.objects.filter(guard__user=self.request.user).select_related('guard__user', 'exhibition')
