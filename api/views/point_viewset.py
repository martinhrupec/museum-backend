from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
import structlog

from ..api_models import User, Guard, Position, Point, SystemSettings, AuditLog
from ..serializers import PointSerializer
from ..permissions import IsAdminRole

logger = structlog.get_logger(__name__)


class PointViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing points.
    
    - Admins can view all points and create new ones (custom awards/penalties)
    - Guards can only view their own points
    - Points are awarded by system, admin, or automatically through actions
    """
    
    queryset = Point.objects.all()
    serializer_class = PointSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """Filter queryset based on user role"""
        if self.request.user.role == User.ROLE_ADMIN:
            return Point.objects.all()
        else:
            # Guards see only their own points
            return Point.objects.filter(guard__user=self.request.user)
    
    def get_permissions(self):
        """Only admins can create/update/delete points"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminRole()]
        return [permissions.IsAuthenticated()]
    
    def perform_create(self, serializer):
        """Admin creates custom award or penalty"""
        point = serializer.save()
        
        # Audit log
        AuditLog.log_create(
            user=self.request.user,
            instance=point,
            request=self.request
        )
    
    @action(detail=False, methods=['post'], permission_classes=[IsAdminRole])
    def penalize_unannounced_lateness(self, request):
        """
        Admin endpoint to penalize guard for being late without notification.
        
        POST /api/points/penalize-unannounced-lateness/
        {
            "guard_id": 5,
            "position_id": 123,  # Optional - for context in explanation
            "additional_notes": "Late for 30 minutes"  # Optional
        }
        """
        guard_id = request.data.get('guard_id')
        position_id = request.data.get('position_id')
        additional_notes = request.data.get('additional_notes', '')
        
        if not guard_id:
            return Response(
                {'error': 'guard_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        guard = get_object_or_404(Guard, pk=guard_id)
        settings = SystemSettings.get_active()
        
        explanation = f"Kazna za kašnjenje bez obavijesti"
        if position_id:
            try:
                position = Position.objects.get(pk=position_id)
                explanation += f" (Pozicija: {position.exhibition.name}, {position.date})"
            except Position.DoesNotExist:
                pass
        if additional_notes:
            explanation += f" - {additional_notes}"
        
        point = Point.objects.create(
            guard=guard,
            points=settings.penalty_for_being_late_without_notification,
            explanation=explanation
        )
        
        serializer = self.get_serializer(point)
        return Response(
            {
                'message': 'Penalty applied successfully',
                'point': serializer.data
            },
            status=status.HTTP_201_CREATED
        )
