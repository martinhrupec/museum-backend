from rest_framework import viewsets, permissions, status
from rest_framework.response import Response

from ..api_models import User, Guard, Report, AuditLog
from ..serializers import ReportSerializer
from ..permissions import IsAdminRole


class ReportViewSet(viewsets.ModelViewSet):
    """
    ViewSet for guard reports.
    
    Permissions:
    - Admins: can view all reports (list/retrieve), CANNOT create/update/delete
    - Guards: can view all reports (list/retrieve), can create their own reports, CANNOT update/delete
    - Reports are immutable once created
    - Creating a report sends email to reception
    """
    
    queryset = Report.objects.all()
    serializer_class = ReportSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        """
        All authenticated users can see all reports.
        
        Query params:
            exhibition_id: Filter by exhibition ID
            ordering: Sort order (created_at, -created_at)
        """
        queryset = Report.objects.all().select_related('guard__user', 'position__exhibition')
        
        # Exhibition filtering
        exhibition_id = self.request.query_params.get('exhibition_id')
        if exhibition_id:
            try:
                queryset = queryset.filter(position__exhibition_id=int(exhibition_id))
            except ValueError:
                pass
        
        # Ordering
        ordering = self.request.query_params.get('ordering')
        if ordering in ['created_at', '-created_at']:
            queryset = queryset.order_by(ordering)
        
        return queryset
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ['list', 'retrieve']:
            # Both guards and admins can view all reports
            return [permissions.IsAuthenticated()]
        elif self.action == 'create':
            # Only guards can create reports
            return [permissions.IsAuthenticated()]
        else:
            # Nobody can update/delete
            return [IsAdminRole()]  # Even admins will be blocked via custom methods
    
    def create(self, request, *args, **kwargs):
        """
        Create a new report. Only guards can create reports.
        Admin cannot create reports.
        """
        # Check if user is admin
        if request.user.role == User.ROLE_ADMIN:
            return Response(
                {'detail': 'Admins cannot create reports.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Check if user has guard profile
        if not hasattr(request.user, 'guard'):
            return Response(
                {'detail': 'Only guards can create reports.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        return super().create(request, *args, **kwargs)
    
    def perform_create(self, serializer):
        """Save report with guard and queue email sending"""
        from background_tasks.tasks import send_report_email
        
        # Get guard profile for current user
        guard = self.request.user.guard
        report = serializer.save(guard=guard)
        
        # Audit log
        AuditLog.log_create(
            user=self.request.user,
            instance=report,
            request=self.request
        )
        
        # Queue email sending asynchronously
        # In tests with CELERY_TASK_ALWAYS_EAGER=True, this runs synchronously
        send_report_email.delay(report.id)
    
    def update(self, request, *args, **kwargs):
        """Reports cannot be updated"""
        return Response(
            {'error': 'Reports cannot be updated'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    
    def partial_update(self, request, *args, **kwargs):
        """Reports cannot be updated"""
        return Response(
            {'error': 'Reports cannot be updated'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    
    def destroy(self, request, *args, **kwargs):
        """Reports cannot be deleted"""
        return Response(
            {'error': 'Reports cannot be deleted'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
