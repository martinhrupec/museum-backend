from rest_framework import viewsets, permissions
from django_filters import rest_framework as filters

from ..api_models import User, GuardWorkPeriod
from ..serializers import GuardWorkPeriodSerializer
from ..mixins import AuditLogMixin


class GuardWorkPeriodFilter(filters.FilterSet):
    """Filter for GuardWorkPeriod"""
    guard = filters.NumberFilter(field_name='guard__id')
    is_template = filters.BooleanFilter(field_name='is_template')
    next_week_start = filters.DateFilter(field_name='next_week_start')
    
    class Meta:
        model = GuardWorkPeriod
        fields = ['guard', 'is_template', 'next_week_start']


class GuardWorkPeriodViewSet(AuditLogMixin, viewsets.ReadOnlyModelViewSet):
    """
    ReadOnly ViewSet for guard work periods (for reporting/viewing).
    
    - Admins can view all work periods
    - Guards can view their own work periods
    - For SETTING work periods, use: POST /api/guards/{id}/set_work_periods/
    
    This ViewSet is READ-ONLY. All create/update/delete operations must go through
    GuardViewSet.set_work_periods() for proper validation.
    
    Filtering:
    - ?guard={id} - filter by guard ID
    - ?is_template=true/false - filter template vs specific week periods
    - ?next_week_start=YYYY-MM-DD - filter by specific week
    """
    
    queryset = GuardWorkPeriod.objects.all()
    serializer_class = GuardWorkPeriodSerializer
    permission_classes = [permissions.IsAuthenticated]
    filterset_class = GuardWorkPeriodFilter
    
    def get_queryset(self):
        """Filter queryset based on user role"""
        if self.request.user.role == User.ROLE_ADMIN:
            return GuardWorkPeriod.objects.all().select_related('guard__user')
        else:
            # Guards see only their own work periods
            return GuardWorkPeriod.objects.filter(guard__user=self.request.user).select_related('guard__user')
