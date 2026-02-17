from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
import structlog

from ..api_models import Position, SystemSettings
from ..serializers import PositionBasicSerializer, PositionDetailSerializer
from ..permissions import IsAdminRole
from ..throttles import SwapRequestThrottle
from ..mixins import AuditLogMixin

logger = structlog.get_logger(__name__)


class PositionViewSet(AuditLogMixin, viewsets.ModelViewSet):
    """
    ViewSet for managing positions.
    
    - All authenticated users can view positions
    - Only admins can create/update/delete
    
    Custom actions:
    - GET /positions/next_week/ - Get positions for next week
    - POST /positions/{id}/request_swap/ - Request to swap this position
    """
    
    queryset = Position.objects.all()
    
    def get_serializer_class(self):
        """Return appropriate serializer based on action"""
        if self.action == 'list':
            return PositionBasicSerializer
        else:
            return PositionDetailSerializer
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminRole()]
        else:
            return [permissions.IsAuthenticated()]
    
    @action(detail=False, methods=['get'])
    def next_week(self, request):
        """
        Get positions for next week.
        
        Uses fixed next_week period from SystemSettings (set by Monday midnight task).
        This ensures all guards see the same positions regardless of when they access it.
        
        GET /api/positions/next_week/
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
        
        positions = Position.objects.filter(
            date__gte=next_week_start,
            date__lte=next_week_end
        ).order_by('date', 'start_time', 'exhibition__name')
        
        serializer = PositionBasicSerializer(positions, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated], throttle_classes=[SwapRequestThrottle])
    def request_swap(self, request, pk=None):
        """
        Request to swap this position with another guard.
        
        Only allowed:
        - After manual configuration period has ended (if position is in next_week)
        - If guard is currently assigned to this position
        - If guard has work_periods configured (template or specific)
        - Only one active swap request per guard at a time
        
        POST /api/positions/{id}/request_swap/
        """
        from ..api_models.textual_model import PositionSwapRequest
        from ..api_models.schedule import PositionHistory
        from ..api_models.user_type import User
        from ..utils.swap_eligibility import guard_has_work_periods
        from datetime import timedelta
        from django.utils import timezone
        
        if request.user.role == User.ROLE_ADMIN:
            return Response(
                {'detail': 'Admins cannot request position swaps.'},
                status=status.HTTP_403_FORBIDDEN
            )
            
        position = self.get_object()
        guard = request.user.guard
        settings = SystemSettings.get_active()
                
        # 1. Check if manual configuration period has ended (samo za next_week)
        period = position.get_period(settings)
        if period == 'next_week':
            manual_end = settings.manual_assignment_end_datetime
            if manual_end is None or timezone.now() < manual_end:
                return Response(
                    {'error': 'Swap requests for next week can only be made after manual configuration period ends'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # 2. Check if guard has work_periods for this position's week
        if not guard_has_work_periods(guard, position):
            return Response(
                {'error': 'You must configure your work periods for this week before requesting swaps'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 3. Check if guard is assigned to this position
        latest_history = position.position_histories.order_by('-action_time').first()
        if not latest_history or latest_history.guard != guard:
            return Response(
                {'error': 'You are not assigned to this position'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if latest_history.action not in [
            PositionHistory.Action.ASSIGNED,
            PositionHistory.Action.REPLACED,
            PositionHistory.Action.SWAPPED
        ]:
            return Response(
                {'error': 'Position is not in assigned state'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 4. Check if guard already has an active swap request
        existing_swap = PositionSwapRequest.objects.filter(
            requesting_guard=guard,
            status='pending'
        ).first()
        
        if existing_swap:
            return Response(
                {'error': 'You already have an active swap request. Cancel it first.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 5. Check if position is not already in a swap request
        existing_position_swap = PositionSwapRequest.objects.filter(
            position_to_swap=position,
            status='pending'
        ).first()
        
        if existing_position_swap:
            return Response(
                {'error': 'This position already has a pending swap request'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # 6. Create swap request
        # Expires at position start time
        position_datetime = timezone.make_aware(
            timezone.datetime.combine(position.date, position.start_time)
        )
        
        swap_request = PositionSwapRequest.objects.create(
            requesting_guard=guard,
            position_to_swap=position,
            expires_at=position_datetime
        )
        
        logger.info(
            "swap_request_created",
            guard_id=guard.id,
            guard_username=guard.user.username,
            position_id=position.id,
            exhibition=position.exhibition.name,
            date=str(position.date),
            swap_request_id=swap_request.id,
            user_id=request.user.id
        )
        
        from ..serializers import PositionSwapRequestSerializer
        serializer = PositionSwapRequestSerializer(swap_request)
        
        return Response({
            'message': 'Swap request created successfully',
            'swap_request': serializer.data
        }, status=status.HTTP_201_CREATED)
