"""
ViewSet for AuditLog management.

Admins can view audit logs to track changes and administrative actions.
"""

from rest_framework import viewsets, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django_filters import rest_framework as filters

from ..api_models import AuditLog
from ..serializers import AuditLogSerializer
from ..permissions import IsAdminRole


class AuditLogFilter(filters.FilterSet):
    """Filter for AuditLog queryset"""
    user = filters.NumberFilter(field_name='user__id')
    model = filters.CharFilter(field_name='model_name', lookup_expr='iexact')
    action = filters.ChoiceFilter(choices=AuditLog.Action.choices)
    date_from = filters.DateTimeFilter(field_name='timestamp', lookup_expr='gte')
    date_to = filters.DateTimeFilter(field_name='timestamp', lookup_expr='lte')
    
    class Meta:
        model = AuditLog
        fields = ['user', 'model', 'action', 'date_from', 'date_to']


class AuditLogViewSet(viewsets.ReadOnlyModelViewSet):
    """
    ViewSet for viewing audit logs (read-only).
    
    Only admins can access audit logs.
    Provides filtering by user, model, action type, and date range.
    """
    
    queryset = AuditLog.objects.all().select_related('user')
    serializer_class = AuditLogSerializer
    permission_classes = [IsAdminRole]
    filterset_class = AuditLogFilter
    ordering = ['-timestamp']
    
    @action(detail=False, methods=['get'])
    def summary(self, request):
        """
        Get summary statistics for audit logs.
        
        Returns counts by action type, recent activity, top users.
        """
        from django.db.models import Count
        from datetime import timedelta
        from django.utils import timezone
        
        # Last 30 days
        thirty_days_ago = timezone.now() - timedelta(days=30)
        recent_logs = AuditLog.objects.filter(timestamp__gte=thirty_days_ago)
        
        # Count by action type
        by_action = recent_logs.values('action').annotate(
            count=Count('id')
        ).order_by('-count')
        
        # Count by model
        by_model = recent_logs.values('model_name').annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        # Top users (by activity)
        top_users = recent_logs.values(
            'user__id', 'user__username', 'user__first_name', 'user__last_name'
        ).annotate(
            count=Count('id')
        ).order_by('-count')[:10]
        
        return Response({
            'period': '30_days',
            'total_actions': recent_logs.count(),
            'by_action': list(by_action),
            'by_model': list(by_model),
            'top_users': list(top_users),
        })
