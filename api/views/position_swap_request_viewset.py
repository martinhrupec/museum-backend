from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.utils import timezone
from django.db import transaction
from django.core.exceptions import ValidationError
import structlog

from ..api_models.textual_model import PositionSwapRequest
from ..api_models.user_type import Guard, User
from ..api_models.schedule import Position, PositionHistory
from ..api_models.system_settings import SystemSettings
from ..serializers import (
    PositionSwapRequestSerializer,
    EligibleSwapRequestSerializer
)
from ..permissions import IsAdminRole
from ..throttles import AcceptSwapThrottle
from ..utils.swap_eligibility import (
    guard_has_work_periods,
    check_guard_eligibility_for_swap
)

logger = structlog.get_logger(__name__)
from ..utils.swap_execution import perform_position_swap


class PositionSwapRequestViewSet(viewsets.ModelViewSet):
    """
    ViewSet for position swap requests.
    
    Endpoints:
    - GET /position-swap-requests/ - View swap requests where you're eligible
    - GET /position-swap-requests/my_requests/ - View your own swap requests
    - POST /position-swap-requests/{id}/accept_swap/ - Accept a swap request
    - DELETE /position-swap-requests/{id}/ - Cancel your own swap request
    """
    
    queryset = PositionSwapRequest.objects.all()
    serializer_class = PositionSwapRequestSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """
        - Admins: see all swap requests
        - Guards: 
          - For destroy: can access their own pending requests
          - For list/retrieve: see only swap requests where they're eligible to accept
            (pending, not expired, not own)
        """
        user = self.request.user
        
        # Admins see all
        if user.role == User.ROLE_ADMIN:
            return PositionSwapRequest.objects.all().order_by('-created_at')
        
        # Guards must have guard profile
        if not hasattr(user, 'guard'):
            return PositionSwapRequest.objects.none()
        
        guard = user.guard
        
        # For destroy action, guards need access to their own requests
        if self.action == 'destroy':
            return PositionSwapRequest.objects.filter(requesting_guard=guard)
        
        # For other actions, get all pending, non-expired swap requests (excluding own)
        pending_swaps = PositionSwapRequest.objects.filter(
            status='pending',
            expires_at__gt=timezone.now()
        ).exclude(requesting_guard=guard)
        
        # Filter to only those where guard is eligible
        eligible_swap_ids = []
        for swap_request in pending_swaps:
            eligibility = check_guard_eligibility_for_swap(guard, swap_request)
            if eligibility['is_eligible']:
                eligible_swap_ids.append(swap_request.id)
        
        return PositionSwapRequest.objects.filter(id__in=eligible_swap_ids)
    
    def list(self, request, *args, **kwargs):
        """
        List swap requests.
        - Admins: all swap requests
        - Guards: only eligible swap requests with positions they can offer
        """
        # Admins get simple list
        if request.user.role == User.ROLE_ADMIN:
            queryset = self.get_queryset()
            serializer = self.get_serializer(queryset, many=True)
            return Response(serializer.data)
        
        # Guards get eligible swaps with positions they can offer
        guard = request.user.guard
        queryset = self.get_queryset()
        
        # Build response with positions guard can offer
        eligible_swaps = []
        for swap_request in queryset:
            eligibility = check_guard_eligibility_for_swap(guard, swap_request)
            eligible_swaps.append({
                'swap_request': swap_request,
                'positions_can_offer': eligibility['positions_can_offer']
            })
        
        serializer = EligibleSwapRequestSerializer(eligible_swaps, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'], url_path='all', permission_classes=[IsAdminRole])
    def all(self, request):
        """
        Admin-only endpoint: Return all swap requests (any status, any expiry).
        GET /api/position-swap-requests/all/
        """
        all_swaps = PositionSwapRequest.objects.all().order_by('-created_at')
        serializer = self.get_serializer(all_swaps, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'], url_path='all_active', permission_classes=[IsAdminRole])
    def all_active(self, request):
        """
        Admin-only endpoint: Return all active (pending, not expired) swap requests for all guards.
        GET /api/position-swap-requests/all_active/
        """
        now = timezone.now()
        active_swaps = PositionSwapRequest.objects.filter(status='pending', expires_at__gt=now).order_by('-created_at')
        serializer = self.get_serializer(active_swaps, many=True)
        return Response(serializer.data)
    
    @action(detail=False, methods=['get'])
    def my_requests(self, request):
        """
        Get swap requests created by current guard.
        Returns 403 if user is admin.
        GET /api/position-swap-requests/my_requests/
        """
        if request.user.role == User.ROLE_ADMIN:
            return Response(
                {'detail': 'Admins cannot access guard-only endpoints.'},
                status=status.HTTP_403_FORBIDDEN
            )
        guard = request.user.guard
        my_swaps = PositionSwapRequest.objects.filter(
            requesting_guard=guard
        ).order_by('-created_at')
        serializer = self.get_serializer(my_swaps, many=True)
        return Response(serializer.data)
    
    @action(detail=True, methods=['post'], permission_classes=[permissions.IsAuthenticated], throttle_classes=[AcceptSwapThrottle])
    def accept_swap(self, request, pk=None):
        """
        Accept a swap request by offering one of your positions.
        
        POST /api/position-swap-requests/{id}/accept_swap/
        Body: {
            "position_id": 123  # ID of position you're offering
        }
        """
        swap_request = self.get_object()
        
        if request.user.role == User.ROLE_ADMIN:
            return Response(
                {'detail': 'Admins cannot access guard-only endpoints.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        guard = request.user.guard
        
        position_id = request.data.get('position_id')
        if not position_id:
            return Response(
                {'error': 'position_id is required'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get position
        try:
            position_offered = Position.objects.get(id=position_id)
        except Position.DoesNotExist:
            return Response(
                {'error': 'Position not found'},
                status=status.HTTP_404_NOT_FOUND
            )
        
        # Check eligibility
        eligibility = check_guard_eligibility_for_swap(guard, swap_request)
        if not eligibility['is_eligible']:
            return Response(
                {'error': eligibility['reason']},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Check that position_offered is in the list of valid positions
        if position_offered not in eligibility['positions_can_offer']:
            return Response(
                {'error': 'You cannot offer this position'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Perform the swap
        try:
            result = perform_position_swap(swap_request, guard, position_offered)
            
            logger.info(
                "swap_request_accepted",
                swap_request_id=swap_request.id,
                requesting_guard_id=swap_request.requesting_guard.id,
                accepting_guard_id=guard.id,
                position_to_swap_id=swap_request.position_to_swap.id,
                position_offered_id=position_offered.id,
                user_id=request.user.id
            )
            
            return Response({
                'message': result['message'],
                'swap_request': PositionSwapRequestSerializer(result['swap_request']).data
            })
        except ValidationError as e:
            return Response(
                {'error': str(e)},
                status=status.HTTP_400_BAD_REQUEST
            )
    
    def destroy(self, request, *args, **kwargs):
        """
        Delete/cancel swap request.
        - Admins can delete any swap request
        - Guards can only cancel their own pending swap requests
        
        DELETE /api/position-swap-requests/{id}/
        """
        swap_request = self.get_object()
        
        # Admins can delete any swap request
        if request.user.role == User.ROLE_ADMIN:
            swap_request.delete()
            logger.info(
                "swap_request_deleted_by_admin",
                swap_request_id=swap_request.id,
                admin_id=request.user.id
            )
            return Response(status=status.HTTP_204_NO_CONTENT)
        
        # Guards can only cancel their own pending requests
        guard = request.user.guard
        
        # Check ownership
        if swap_request.requesting_guard != guard:
            return Response(
                {'error': 'You can only cancel your own swap requests'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check status
        if swap_request.status != 'pending':
            return Response(
                {'error': 'Can only cancel pending swap requests'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Cancel by setting status
        swap_request.status = 'cancelled'
        swap_request.save()
        
        logger.info(
            "swap_request_cancelled_by_guard",
            swap_request_id=swap_request.id,
            guard_id=guard.id
        )
        
        return Response(
            {'message': 'Swap request cancelled successfully'},
            status=status.HTTP_200_OK
        )
    
    def create(self, request, *args, **kwargs):
        """Disable direct creation - use position endpoint instead"""
        return Response(
            {'error': 'Use POST /api/positions/{id}/request_swap/ to create swap requests'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    
    def update(self, request, *args, **kwargs):
        """Disable updates"""
        return Response(
            {'error': 'Swap requests cannot be updated'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    
    def partial_update(self, request, *args, **kwargs):
        """Disable partial updates"""
        return Response(
            {'error': 'Swap requests cannot be updated'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
