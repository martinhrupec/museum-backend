"""
API Views Module
Refactored structure with each ViewSet in its own file.
"""

# Import all ViewSets
from .user_viewset import UserViewSet
from .guard_viewset import GuardViewSet
from .exhibition_viewset import ExhibitionViewSet
from .position_viewset import PositionViewSet
from .position_history_viewset import PositionHistoryViewSet
from .non_working_day_viewset import NonWorkingDayViewSet
from .point_viewset import PointViewSet
from .admin_notification_viewset import AdminNotificationViewSet
from .report_viewset import ReportViewSet
from .system_settings_viewset import SystemSettingsViewSet
from .guard_exhibition_preference_viewset import GuardExhibitionPreferenceViewSet
from .guard_day_preference_viewset import GuardDayPreferenceViewSet
from .position_swap_request_viewset import PositionSwapRequestViewSet
from .audit_log_viewset import AuditLogViewSet

# Import standalone view functions
from .general_views import session_login, session_logout, session_check, health_check
from .jwt_views import TokenObtainPairView, jwt_logout

__all__ = [
    # ViewSets
    'UserViewSet',
    'GuardViewSet',
    'ExhibitionViewSet',
    'PositionViewSet',
    'PositionHistoryViewSet',
    'NonWorkingDayViewSet',
    'PointViewSet',
    'AdminNotificationViewSet',
    'ReportViewSet',
    'SystemSettingsViewSet',
    'GuardExhibitionPreferenceViewSet',
    'GuardDayPreferenceViewSet',
    'PositionSwapRequestViewSet',
    'AuditLogViewSet',
    # Standalone views
    'session_login',
    'session_logout',
    'session_check',
    'health_check',
    'TokenObtainPairView',
    'jwt_logout',
]
