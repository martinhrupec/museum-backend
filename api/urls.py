from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

# DRF Router za ViewSets
router = DefaultRouter()
router.register(r'users', views.UserViewSet)
router.register(r'guards', views.GuardViewSet)
router.register(r'exhibitions', views.ExhibitionViewSet)
router.register(r'positions', views.PositionViewSet)
router.register(r'position-history', views.PositionHistoryViewSet)
router.register(r'non-working-days', views.NonWorkingDayViewSet)
router.register(r'points', views.PointViewSet)
router.register(r'admin-notifications', views.AdminNotificationViewSet)
router.register(r'reports', views.ReportViewSet)
router.register(r'system-settings', views.SystemSettingsViewSet)
router.register(r'guard-work-periods', views.GuardWorkPeriodViewSet)
router.register(r'guard-exhibition-preferences', views.GuardExhibitionPreferenceViewSet)
router.register(r'guard-day-preferences', views.GuardDayPreferenceViewSet)
router.register(r'position-swap-requests', views.PositionSwapRequestViewSet)
router.register(r'audit-logs', views.AuditLogViewSet)

urlpatterns = [
    # JWT Authentication endpoints (Mobile) - with throttling
    path('token/', views.TokenObtainPairView.as_view(), name='token_obtain_pair'),
    path('token/refresh/', TokenRefreshView.as_view(), name='token_refresh'),
    path('token/logout/', views.jwt_logout, name='jwt_logout'),
    
    # Session Authentication endpoints (Browser) - with throttling
    path('login/', views.session_login, name='session_login'),
    path('logout/', views.session_logout, name='session_logout'),
    path('auth/check/', views.session_check, name='session_check'),
    
    # Health check for load balancers and monitoring
    path('health/', views.health_check, name='health_check'),
    
    # DRF ViewSet endpoints
    path('', include(router.urls)),
]