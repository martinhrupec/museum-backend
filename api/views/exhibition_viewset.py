from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
import structlog

from ..api_models import User, Exhibition, Position, SystemSettings
from ..serializers import ExhibitionBasicSerializer, ExhibitionDetailSerializer, ExhibitionAdminSerializer
from ..permissions import IsAdminRole
from ..mixins import AuditLogMixin

logger = structlog.get_logger(__name__)


class ExhibitionViewSet(AuditLogMixin, viewsets.ModelViewSet):
    """
    ViewSet for managing exhibitions.
    
    - All authenticated users can view exhibitions
    - Only admins can create/update/delete
    """
    
    queryset = Exhibition.objects.all()
    
    # Valid ordering fields for sorting
    VALID_ORDERINGS = [
        'name', '-name',
        'start_date', '-start_date',
        'end_date', '-end_date',
    ]
    
    def get_queryset(self):
        """Filter queryset based on query params
        
        Query params:
            status: Filter by status (all/active/upcoming/finished)
            ordering: Sort order (name, -name, start_date, -start_date, end_date, -end_date)
        """
        queryset = Exhibition.objects.all()
        now = timezone.now()
        
        # Status filtering
        status_param = self.request.query_params.get('status')
        if status_param == 'active':
            queryset = queryset.filter(start_date__lte=now, end_date__gte=now)
        elif status_param == 'upcoming':
            queryset = queryset.filter(start_date__gt=now)
        elif status_param == 'finished':
            queryset = queryset.filter(end_date__lt=now)
        # 'all' or no status param returns everything
        
        # Ordering
        ordering = self.request.query_params.get('ordering')
        if ordering in self.VALID_ORDERINGS:
            queryset = queryset.order_by(ordering)
        
        return queryset
    
    def get_serializer_class(self):
        """Return appropriate serializer based on user role and action"""
        if self.request.user.role == User.ROLE_ADMIN:
            return ExhibitionAdminSerializer
        elif self.action == 'list':
            return ExhibitionBasicSerializer
        else:
            return ExhibitionDetailSerializer
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminRole()]
        elif self.action in ['list', 'retrieve']:
            return [permissions.IsAuthenticated()]
        else:
            return [permissions.IsAuthenticated()]
    
    @action(detail=False, methods=['get'])
    def next_week(self, request):
        """
        Get exhibitions that have positions scheduled for next week.
        
        Uses fixed next_week period from SystemSettings (set by Monday midnight task).
        This ensures all guards see the same period regardless of when they access it.
        
        GET /api/exhibitions/next_week/
        
        Returns exhibitions that are active and have positions in the next week period.
        """
        settings = SystemSettings.get_active()
        
        if not settings.next_week_start or not settings.next_week_end:
            return Response(
                {'error': 'Next week period not set yet. Weekly task needs to run first.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        # Use fixed period from SystemSettings
        next_week_start = settings.next_week_start
        next_week_end = settings.next_week_end
        
        # Get exhibitions that have positions in next week
        exhibitions = Exhibition.objects.filter(
            positions__date__gte=next_week_start,
            positions__date__lte=next_week_end
        ).distinct()
        
        serializer = self.get_serializer(exhibitions, many=True)
        return Response(serializer.data)
