from rest_framework import viewsets
from rest_framework.permissions import IsAuthenticated
from django.utils import timezone
import structlog

from ..api_models import NonWorkingDay, AuditLog
from ..serializers import NonWorkingDaySerializer
from ..permissions import IsAdminRole

logger = structlog.get_logger(__name__)


class NonWorkingDayViewSet(viewsets.ModelViewSet):
    """
    ViewSet for managing non-working days.
    
    - Only admins can create/update/delete
    - All authenticated users can view
    - Creating a non-working day deletes affected positions
    """
    
    queryset = NonWorkingDay.objects.all()
    serializer_class = NonWorkingDaySerializer
    permission_classes = [IsAuthenticated]
    
    def get_queryset(self):
        """Filter queryset based on query params
        
        Query params:
            in_future: Only return non-working days that haven't happened yet (true/false)
        """
        queryset = NonWorkingDay.objects.all()
        
        in_future = self.request.query_params.get('in_future')
        if in_future == 'true':
            today = timezone.now().date()
            queryset = queryset.filter(date__gte=today)
        
        return queryset
    
    def get_permissions(self):
        """
        Admin-only for create/update/delete.
        All authenticated users for list/retrieve.
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminRole()]
        return [IsAuthenticated()]
    
    def perform_create(self, serializer):
        """Save with current user and delete affected positions"""
        # Save with created_by
        non_working_day = serializer.save(created_by=self.request.user)
        
        # Audit log
        AuditLog.log_create(
            user=self.request.user,
            instance=non_working_day,
            request=self.request
        )
        
        logger.info(
            "non_working_day_created",
            date=str(non_working_day.date),
            is_full_day=non_working_day.is_full_day,
            shift=non_working_day.non_working_shift,
            reason=non_working_day.reason,
            user_id=self.request.user.id
        )
        
        # Delete affected positions using model method
        deleted_count = non_working_day.delete_affected_positions()
        
        logger.info(
            "positions_deleted_for_non_working_day",
            non_working_day_id=non_working_day.id,
            deleted_count=deleted_count,
            user_id=self.request.user.id
        )
