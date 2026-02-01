from rest_framework import viewsets, permissions
from rest_framework.response import Response
from django.db.models import Q
from django.utils import timezone
from datetime import timedelta

from ..api_models import User, AdminNotification, PositionHistory, Position, SystemSettings, AuditLog
from ..serializers import AdminNotificationSerializer
from ..permissions import IsAdminRole
from ..utils.notification_matching import guard_matches_multicast


class AdminNotificationViewSet(viewsets.ModelViewSet):
    """
    ViewSet for admin notifications/announcements with cast types.
    
    Cast Types:
    - broadcast: Shown to all users
    - unicast: Shown to specific user (to_user)
    - multicast: Shown to guards assigned to positions matching filters
    
    Multicast filtering logic:
    notification_date set?
    ├─ DA → Check ONLY that day (ignore this/next week)
    │       ├─ + exhibition → only that exhibition that day
    │       ├─ + shift_type → only that shift that day
    │       └─ + both → combination
    │
    └─ NE → Check this_week(from today) + next_week period - intersection of 
    interval with from today to expires_at
            ├─ + exhibition → all on that exhibition in both periods
            ├─ + shift_type → all in that shift in both periods
            └─ + both → combination in both periods
    
    Permissions:
    - Only admins can create/update/delete notifications
    - All authenticated users can view notifications meant for them
    
    Queryset filtering:
    - Admins see all notifications
    - Guards see: broadcast + unicast to them + multicast where they match criteria
    """
    
    queryset = AdminNotification.objects.all()
    serializer_class = AdminNotificationSerializer
    
    def get_queryset(self):
        """Filter queryset based on user role and cast type"""
        user = self.request.user
        
        # Base filter: only non-expired notifications
        base_filter = Q(expires_at__isnull=True) | Q(expires_at__gte=timezone.now())
        
        if user.role == User.ROLE_ADMIN:
            # Admins see all notifications (including expired for history)
            return AdminNotification.objects.all()
        else:
            # Guards see only non-expired: broadcast OR unicast to them OR multicast where they're assigned
            
            # Start with broadcast and unicast
            queryset = AdminNotification.objects.filter(
                base_filter &
                (Q(cast_type=AdminNotification.CAST_BROADCAST) |
                 Q(cast_type=AdminNotification.CAST_UNICAST, to_user=user))
            )
            
            # Add multicast notifications where guard is assigned
            # Get guard profile
            try:
                guard = user.guard
                
                # Get all non-expired multicast notifications
                multicast_notifications = AdminNotification.objects.filter(
                    base_filter,
                    cast_type=AdminNotification.CAST_MULTICAST
                )
                
                # Filter multicast by checking if guard has assigned positions matching criteria
                matching_multicast_ids = []
                
                for notification in multicast_notifications:
                    if guard_matches_multicast(guard, notification):
                        matching_multicast_ids.append(notification.id)
                
                # Combine with broadcast/unicast
                if matching_multicast_ids:
                    queryset = queryset | AdminNotification.objects.filter(
                        id__in=matching_multicast_ids
                    )
            
            except AttributeError:
                # User is not a guard, only show broadcast/unicast
                pass
            
            return queryset.distinct()
    
    def perform_create(self, serializer):
        """Set created_by to current user when creating notification"""
        notification = serializer.save(created_by=self.request.user)
        
        # Audit log
        AuditLog.log_create(
            user=self.request.user,
            instance=notification,
            request=self.request
        )
    
    def get_permissions(self):
        """Set permissions based on action"""
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminRole()]
        else:
            return [permissions.IsAuthenticated()]
