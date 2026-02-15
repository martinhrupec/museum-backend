from rest_framework import viewsets, permissions
from django_filters import rest_framework as filters

from ..api_models import User, GuardDayPreference
from ..serializers import GuardDayPreferenceSerializer
from ..mixins import AuditLogMixin


class GuardDayPreferenceFilter(filters.FilterSet):
    """Filter for GuardDayPreference"""
    guard = filters.NumberFilter(field_name='guard__id')
    is_template = filters.BooleanFilter(field_name='is_template')
    next_week_start = filters.DateFilter(field_name='next_week_start')
    
    class Meta:
        model = GuardDayPreference
        fields = ['guard', 'is_template', 'next_week_start']


class GuardDayPreferenceViewSet(AuditLogMixin, viewsets.ReadOnlyModelViewSet):
    """
    ReadOnly ViewSet for guard day preferences (for reporting/viewing).
    
    - Admins can view all preferences
    - Guards can view their own preferences
    - For SETTING preferences, use: POST /api/guards/{id}/set_day_preferences/
    
    This ViewSet is READ-ONLY. All create/update/delete operations must go through
    GuardViewSet.set_day_preferences() for proper validation.
    
    Filtering:
    - ?guard={id} - filter by guard ID
    - ?is_template=true/false - filter template vs specific week preferences
    - ?next_week_start=YYYY-MM-DD - filter by specific week
    """
    
    queryset = GuardDayPreference.objects.all()
    serializer_class = GuardDayPreferenceSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_class = GuardDayPreferenceFilter
    
    def get_queryset(self):
        """Filter queryset based on user role"""
        if self.request.user.role == User.ROLE_ADMIN:
            return GuardDayPreference.objects.all().select_related('guard__user')
        else:
            # Guards see only their own preferences
            return GuardDayPreference.objects.filter(guard__user=self.request.user).select_related('guard__user')
