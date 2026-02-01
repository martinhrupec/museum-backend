from rest_framework import viewsets, status, permissions
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db.models import Q
import structlog
from ..api_models import (
    User, Guard, NonWorkingDay, SystemSettings, GuardWorkPeriod,
    GuardExhibitionPreference, GuardDayPreference, Exhibition, Position
)
from ..utils.position_calculation import calculate_max_availability_for_week
from ..serializers import (
    GuardBasicSerializer, GuardDetailSerializer, GuardAdminSerializer,
    GuardWorkPeriodSerializer, GuardExhibitionPreferenceSerializer,
    GuardDayPreferenceSerializer
)
from ..permissions import IsAdminRole, IsAdminOrOwner
from ..mixins import AuditLogMixin

logger = structlog.get_logger(__name__)


class GuardViewSet(AuditLogMixin, viewsets.ModelViewSet):
    """
    ViewSet for managing guards.
    
    Guards are auto-created via signal when User with role=ROLE_GUARD is created.
    This viewset is READ-ONLY for standard CRUD, with custom actions for guards.
    
    - Admins can view all guards (list, retrieve)
    - Guards can only view themselves (retrieve via /me/)
    - NO create/update/delete - Guards managed via User creation and custom actions
    
    Custom actions (guard-only):
    - set_availability, set_work_periods, set_exhibition_preferences, set_day_preferences
    """
    
    queryset = Guard.objects.all()
    http_method_names = ['get', 'post', 'head', 'options']  # Read-only for standard CRUD, POST for custom actions
    
    def get_serializer_class(self):
        """Return appropriate serializer based on user role"""
        if self.request.user.role == User.ROLE_ADMIN:
            return GuardAdminSerializer
        elif self.action == 'list':
            return GuardBasicSerializer
        else:
            return GuardDetailSerializer
    
    def get_queryset(self):
        """Filter queryset based on user role"""
        if self.request.user.role == User.ROLE_ADMIN:
            return Guard.objects.filter(user__is_active=True)
        else:
            # Guards can only see themselves
            return Guard.objects.filter(user=self.request.user, user__is_active=True)
    
    def create(self, request, *args, **kwargs):
        """
        Disable direct Guard creation via API.
        Guards are auto-created via signal when User with role=ROLE_GUARD is created.
        """
        return Response(
            {'error': 'Guards cannot be created directly. Create a User with role=guard instead.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED
        )
    
    def get_permissions(self):
        """
        Set permissions based on action.
        
        Guards are NEVER created/updated/deleted directly through this viewset.
        Guard profiles are auto-created via signal when User with role=ROLE_GUARD is created.
        http_method_names restricts to GET only, so create/update/destroy return 405 automatically.
        
        - list, retrieve: Admin (all guards) or Guard (only self)
        - set_availability, set_work_periods, set_exhibition_preferences, set_day_preferences: 
          Only guards for themselves (admins cannot modify these)
        """
        if self.action in ['list', 'retrieve']:
            return [IsAdminOrOwner()]
        elif self.action in ['set_availability', 'set_work_periods', 'set_exhibition_preferences', 'set_day_preferences']:
            # Only guards can modify their own availability, periods, and preferences
            # Admins are explicitly NOT allowed to modify these
            return [permissions.IsAuthenticated()]
        else:
            return [permissions.IsAuthenticated()]
    
    def _ensure_configuration_window_open(self, settings):
        """
        Check if current time is within configuration window.
        Configuration window: Monday 08:00 - 1 hour before automated assignment
        
        Returns Response with error if window is closed, None if open.
        """
        config_start = settings.config_start_datetime
        config_end = settings.config_end_datetime
        
        if not config_start or not config_end:
            return Response(
                {'error': 'Configuration window not initialized yet. Weekly task must complete first.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        now = timezone.now()
        if now < config_start:
            return Response(
                {
                    'error': 'Configuration window is not open yet.',
                    'configuration_opens_at': config_start.isoformat(),
                },
                status=status.HTTP_403_FORBIDDEN
            )
        
        if now >= config_end:
            return Response(
                {
                    'error': 'Configuration window has closed. Changes can only be made Monday-Wednesday.',
                    'configuration_closed_at': config_end.isoformat(),
                },
                status=status.HTTP_403_FORBIDDEN
            )
        
        return None
    
    @action(detail=True, methods=['get'])
    def available_days(self, request, pk=None):
        """
        Get days available for guard's preferences based on their work periods.
        
        GET /api/guards/{id}/available_days/
        
        Returns list of days (0-6) that the guard has in their work periods.
        This is used to show which days guard can rank in their day preferences.
        
        Guards can only see their own available days.
        """
        guard = self.get_object()
        
        if request.user.role != User.ROLE_ADMIN and guard.user != request.user:
            return Response(
                {'error': 'Možete vidjeti samo svoje dostupne dane.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        settings = SystemSettings.get_active()
        
        if not settings.next_week_start or not settings.next_week_end:
            return Response(
                {'error': 'Next week period not set yet.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        # Get guard's work periods (template or specific week)
        guard_work_periods = GuardWorkPeriod.objects.filter(
            guard=guard
        ).filter(
            Q(is_template=True) | Q(next_week_start=settings.next_week_start)
        )
        
        if not guard_work_periods.exists():
            return Response({
                'days': [],
                'message': 'Čuvar nema postavljene periode rada.'
            })
        
        # Get unique days from work periods
        available_days = sorted(set(wp.day_of_week for wp in guard_work_periods))
        
        # Map day numbers to names for readability
        day_names = ['Ponedjeljak', 'Utorak', 'Srijeda', 'Četvrtak', 'Petak', 'Subota', 'Nedjelja']
        days_with_names = [
            {'day_of_week': day, 'name': day_names[day]}
            for day in available_days
        ]
        
        return Response({
            'days': available_days,
            'days_detailed': days_with_names,
            'count': len(available_days)
        })
    
    @action(detail=True, methods=['get'])
    def available_exhibitions(self, request, pk=None):
        """
        Get exhibitions available for guard's preferences based on their work periods.
        
        GET /api/guards/{id}/available_exhibitions/
        
        Returns list of exhibitions that have positions on days matching guard's work periods.
        This is used to show which exhibitions guard can rank in their exhibition preferences.
        
        Guards can only see their own available exhibitions.
        """
        guard = self.get_object()
        
        if request.user.role != User.ROLE_ADMIN and guard.user != request.user:
            return Response(
                {'error': 'Možete vidjeti samo svoje dostupne izložbe.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        settings = SystemSettings.get_active()
        
        if not settings.next_week_start or not settings.next_week_end:
            return Response(
                {'error': 'Next week period not set yet.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        # Get guard's work periods (template or specific week)
        guard_work_periods = GuardWorkPeriod.objects.filter(
            guard=guard
        ).filter(
            Q(is_template=True) | Q(next_week_start=settings.next_week_start)
        )
        
        if not guard_work_periods.exists():
            return Response({
                'exhibitions': [],
                'exhibition_ids': [],
                'message': 'Čuvar nema postavljene periode rada.'
            })
        
        # Get days from guard's work periods
        guard_work_days = set(wp.day_of_week for wp in guard_work_periods)
        
        # Get dates in next_week that match guard's work period days
        next_week_dates = Position.objects.filter(
            date__gte=settings.next_week_start,
            date__lte=settings.next_week_end
        ).values_list('date', flat=True).distinct()
        
        guard_work_dates = [d for d in next_week_dates if d.weekday() in guard_work_days]
        
        # Get exhibitions that have positions on those dates
        exhibitions = Exhibition.objects.filter(
            positions__date__in=guard_work_dates
        ).distinct()
        
        exhibition_data = [
            {
                'id': ex.id,
                'name': ex.name,
                'number_of_positions': ex.number_of_positions
            }
            for ex in exhibitions
        ]
        
        return Response({
            'exhibitions': exhibition_data,
            'exhibition_ids': [ex.id for ex in exhibitions],
            'count': len(exhibition_data)
        })
    
    @action(detail=True, methods=['post'])
    def set_availability(self, request, pk=None):
        """
        Set guard's availability for next week.
        
        POST /api/guards/{id}/set_availability/
        {
            "available_shifts": 5
        }
        
        If guard has a saved template with fewer periods than the new availability,
        the template will be automatically deleted with a warning.
        """
        guard = self.get_object()
        
        # Only the guard themselves can set their availability
        # Admins are NOT allowed to modify this
        if request.user.role == User.ROLE_ADMIN:
            return Response(
                {'error': 'Administratori ne mogu mijenjati dostupnost čuvara. Samo čuvari mogu postaviti svoju dostupnost.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if guard.user != request.user:
            return Response(
                {'error': 'Možete mijenjati samo svoju dostupnost.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        available_shifts = request.data.get('available_shifts')
        
        if available_shifts is None:
            return Response(
                {'error': 'Polje "available_shifts" je obavezno.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            available_shifts = int(available_shifts)
            if available_shifts < 0:
                raise ValueError()
        except (ValueError, TypeError):
            return Response(
                {'error': 'Broj smjena mora biti pozitivan cijeli broj.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get next_week period
        settings = SystemSettings.get_active()
        if not settings.next_week_start or not settings.next_week_end:
            return Response(
                {'error': 'Next week period nije još postavljen. Tjedni zadatak mora prvo završiti.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        # Check if configuration window is open
        window_error = self._ensure_configuration_window_open(settings)
        if window_error:
            return window_error
        
        # Calculate max availability for this week
        max_availability, breakdown = calculate_max_availability_for_week(
            settings.next_week_start,
            settings.next_week_end
        )
        
        # Validate against max availability
        if available_shifts > max_availability:
            return Response({
                'error': f'Dostupnost ne može biti veća od {max_availability} smjena za ovaj tjedan.',
                'Ukupan broj dostupnih smjena': max_availability,
                'Broj smjena koje ste pokušali postaviti': available_shifts,
                'breakdown': breakdown
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Check for template conflicts
        template_periods = GuardWorkPeriod.objects.filter(
            guard=guard,
            is_template=True
        )
        template_count = template_periods.count()
        
        warning_message = None
        if template_count > 0 and template_count < available_shifts:
            # Template has fewer periods than new availability - delete it
            template_periods.delete()
            warning_message = (
                f"Vaš spremljeni predložak je obrisan jer ste postavili "
                f"dostupnost na {available_shifts}, a predložak je imao {template_count} " 
                f"dostupnih perioda rada."
                f"Molimo postavite nove dostupne periode rada."
            )
        
        # Update availability
        guard.availability = available_shifts
        guard.availability_updated_at = timezone.now()
        guard.save()
        
        serializer = self.get_serializer(guard)
        response_data = {
            'message': 'Dostupnost uspješno ažurirana.',
            'guard': serializer.data
        }
        
        if warning_message:
            response_data['warning'] = warning_message
        
        return Response(response_data)
    
    @action(detail=True, methods=['post'])
    def set_work_periods(self, request, pk=None):
        """
        Set guard's work periods for next week.
        
        POST /api/guards/{id}/set_work_periods/
        {
            "periods": [
                {"day_of_week": 1, "shift_type": "morning"},
                {"day_of_week": 2, "shift_type": "afternoon"},
                {"day_of_week": 5, "shift_type": "morning"}
            ],
            "save_for_future_weeks": true
        }
        
        - periods: Array of time periods when guard can work
        - save_for_future_weeks: Boolean, if true saves as template for future weeks
        
        Only the guard themselves can set their work periods.
        Admins are NOT allowed to modify this.
        """
        guard = self.get_object()
        
        # Only the guard themselves can set their work periods
        # Admins are NOT allowed to modify this
        if request.user.role == User.ROLE_ADMIN:
            return Response(
                {'error': 'Administratori ne mogu mijenjati periode čuvara. Samo čuvari mogu postaviti svoje periode rada.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if guard.user != request.user:
            return Response(
                {'error': 'Možete mijenjati samo svoje periode rada.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        periods_data = request.data.get('periods', [])
        save_for_future = request.data.get('save_for_future_weeks', False)
        
        if not periods_data:
            return Response(
                {'error': 'Polje "periods" je obavezno i mora sadržavati barem jedan period.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate periods structure
        for i, period in enumerate(periods_data):
            if 'day_of_week' not in period or 'shift_type' not in period:
                return Response(
                    {'error': f'Period {i+1} mora imati "day_of_week" i "shift_type".'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            try:
                day = int(period['day_of_week'])
                if not (0 <= day <= 6):
                    raise ValueError()
            except (ValueError, TypeError):
                return Response(
                    {'error': f'Period {i+1}: "day_of_week" mora biti broj između 0 (ponedjeljak) i 6 (nedjelja).'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if period['shift_type'] not in ['morning', 'afternoon']:
                return Response(
                    {'error': f'Period {i+1}: "shift_type" mora biti "morning" ili "afternoon".'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Check if guard has set availability
        if guard.availability is None or guard.availability == 0:
            return Response(
                {'error': 'Prvo morate postaviti svoju dostupnost (available_shifts).'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate: number of periods >= availability
        if len(periods_data) < guard.availability:
            return Response(
                {'error': f'Broj perioda ({len(periods_data)}) mora biti veći ili jednak dostupnosti ({guard.availability}).'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get next_week from SystemSettings
        settings = SystemSettings.get_active()
        if not settings.next_week_start or not settings.next_week_end:
            return Response(
                {'error': 'Next week period nije još postavljen. Tjedni zadatak mora prvo završiti.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        # Check if configuration window is open
        window_error = self._ensure_configuration_window_open(settings)
        if window_error:
            return window_error
        
        # Delete old periods for this guard and week (or template if saving template)
        # IMPORTANT: When guard sets new periods, old templates no longer apply
        # Delete ALL old template periods first (regardless of save_for_future)
        GuardWorkPeriod.objects.filter(guard=guard, is_template=True).delete()
        
        # Then delete specific week periods if setting for specific week
        if not save_for_future:
            GuardWorkPeriod.objects.filter(
                guard=guard,
                next_week_start=settings.next_week_start,
                is_template=False
            ).delete()
        
        # Create new periods
        created_periods = []
        for period_data in periods_data:
            period = GuardWorkPeriod.objects.create(
                guard=guard,
                day_of_week=period_data['day_of_week'],
                shift_type=period_data['shift_type'],
                is_template=save_for_future,
                next_week_start=None if save_for_future else settings.next_week_start
            )
            created_periods.append(period)
        
        # CASCADE: When work periods change, preferences are no longer valid
        # Delete all day and exhibition preferences for this guard
        from api.api_models.preferences import GuardDayPreference, GuardExhibitionPreference
        deleted_day_prefs = GuardDayPreference.objects.filter(guard=guard).delete()[0]
        deleted_exhibition_prefs = GuardExhibitionPreference.objects.filter(guard=guard).delete()[0]
        
        if deleted_day_prefs > 0 or deleted_exhibition_prefs > 0:
            logger.info(
                "preferences_cascaded_delete",
                guard_id=guard.id,
                guard_username=guard.user.username,
                deleted_day_prefs=deleted_day_prefs,
                deleted_exhibition_prefs=deleted_exhibition_prefs,
                reason="work_periods_changed"
            )
        
        logger.info(
            "work_periods_set",
            guard_id=guard.id,
            guard_username=guard.user.username,
            period_count=len(created_periods),
            is_template=save_for_future,
            week_start=str(settings.next_week_start) if not save_for_future else None,
            user_id=request.user.id
        )
        
        serializer = GuardWorkPeriodSerializer(created_periods, many=True)
        
        message = 'Periodi rada uspješno postavljeni'
        if save_for_future:
            message += ' i spremljeni kao predložak za buduće tjedne.'
        else:
            message += f' za tjedan {settings.next_week_start} - {settings.next_week_end}.'
        
        return Response({
            'message': message,
            'periods': serializer.data,
            'count': len(created_periods)
        })
    
    @action(detail=True, methods=['post'])
    def set_exhibition_preferences(self, request, pk=None):
        """
        Set guard's exhibition preferences in bulk (ordered by priority).
        
        POST /api/guards/{id}/set_exhibition_preferences/
        {
            "exhibition_ids": [5, 2, 8, 1],  // Ordered from highest to lowest priority
            "save_as_template": true  // Optional: save for future weeks
        }
        
        Receives array of exhibition IDs in priority order (first = highest priority).
        Must send ALL exhibitions from next_week or NONE - partial lists are treated as no preferences.
        
        If save_as_template=true, preferences are saved for future weeks and validated weekly.
        Template remains valid only if exhibition set doesn't change.
        
        Server will:
        1. Validate that array contains ALL exhibitions from next_week
        2. Delete old preferences (template or specific)
        3. Create single preference record with exhibition_order array
        """
        guard = self.get_object()
        
        # Only the guard themselves can set their exhibition preferences
        # Admins are NOT allowed to modify this
        if request.user.role == User.ROLE_ADMIN:
            return Response(
                {'error': 'Administratori ne mogu mijenjati preferencije čuvara. Samo čuvari mogu postaviti svoje preferencije.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if guard.user != request.user:
            return Response(
                {'error': 'Možete mijenjati samo svoje preferencije.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        exhibition_ids = request.data.get('exhibition_ids', [])
        save_as_template = request.data.get('save_as_template', False)
        
        if not isinstance(exhibition_ids, list):
            return Response(
                {'error': 'exhibition_ids must be an array'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get settings
        settings = SystemSettings.get_active()
        
        if not settings.next_week_start or not settings.next_week_end:
            return Response(
                {'error': 'Next week period not set yet. Weekly task needs to run first.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        # Check if configuration window is open
        window_error = self._ensure_configuration_window_open(settings)
        if window_error:
            return window_error
        
        # If empty array provided, just delete preferences and return
        # (No work periods check needed for clearing)
        if not exhibition_ids:
            GuardExhibitionPreference.objects.filter(guard=guard, is_template=True).delete()
            GuardExhibitionPreference.objects.filter(
                guard=guard,
                next_week_start=settings.next_week_start,
                is_template=False
            ).delete()
            return Response({
                'message': 'Preferences cleared successfully',
                'preference': None
            })
        
        # PREREQUISITE: Guard must have work periods set (only for non-empty list)
        guard_work_periods = GuardWorkPeriod.objects.filter(
            guard=guard
        ).filter(
            Q(is_template=True) | Q(next_week_start=settings.next_week_start)
        )
        
        if not guard_work_periods.exists():
            return Response(
                {'error': 'Prvo morate postaviti svoje periode rada (work periods) prije postavljanja preferenci za izložbe.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get days from guard's work periods
        guard_work_days = set(wp.day_of_week for wp in guard_work_periods)
        
        # Get dates in next_week that match guard's work period days
        next_week_dates = Position.objects.filter(
            date__gte=settings.next_week_start,
            date__lte=settings.next_week_end
        ).values_list('date', flat=True).distinct()
        
        guard_work_dates = [d for d in next_week_dates if d.weekday() in guard_work_days]
        
        # Get exhibitions that have positions on those dates
        guard_exhibition_ids = set(
            Exhibition.objects.filter(
                positions__date__in=guard_work_dates
            ).distinct().values_list('id', flat=True)
        )
        
        provided_exhibition_ids = set(exhibition_ids)
        
        # Validate: must provide ALL exhibitions on guard's work days
        if provided_exhibition_ids != guard_exhibition_ids:
            return Response({
                'error': 'Morate navesti SVE izložbe koje su otvorene na dane vaših perioda rada ili nijednu. Djelomične liste nisu dopuštene.',
                'expected_count': len(guard_exhibition_ids),
                'received_count': len(provided_exhibition_ids),
                'missing': list(guard_exhibition_ids - provided_exhibition_ids),
                'extra': list(provided_exhibition_ids - guard_exhibition_ids)
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Delete old preferences (template or specific week)
        # Always delete template when setting new preferences
        GuardExhibitionPreference.objects.filter(guard=guard, is_template=True).delete()
        
        if not save_as_template:
            # Also delete specific week preferences
            GuardExhibitionPreference.objects.filter(
                guard=guard,
                next_week_start=settings.next_week_start,
                is_template=False
            ).delete()
        
        # Create single preference record with array
        
        # Create single preference record with array
        preference = GuardExhibitionPreference.objects.create(
            guard=guard,
            exhibition_order=exhibition_ids,
            is_template=save_as_template,
            next_week_start=None if save_as_template else settings.next_week_start
        )
        
        logger.info(
            "exhibition_preferences_set",
            guard_id=guard.id,
            guard_username=guard.user.username,
            exhibition_count=len(exhibition_ids),
            is_template=save_as_template,
            week_start=str(settings.next_week_start) if not save_as_template else None,
            user_id=request.user.id
        )
        
        serializer = GuardExhibitionPreferenceSerializer(preference)
        
        message = f'Successfully set preferences for {len(exhibition_ids)} exhibitions'
        if save_as_template:
            message += ' and saved as template for future weeks.'
        else:
            message += f' for week {settings.next_week_start} - {settings.next_week_end}.'
        
        return Response({
            'message': message,
            'preference': serializer.data
        })
    
    @action(detail=True, methods=['post'])
    def set_day_preferences(self, request, pk=None):
        """
        Set guard's day preferences in bulk (ordered by priority).
        
        POST /api/guards/{id}/set_day_preferences/
        {
            "day_of_week_list": [1, 5, 3, 2, 4, 6],  // Ordered from highest to lowest priority
            "save_as_template": true  // Optional: save for future weeks
        }
        
        Receives array of day_of_week integers in priority order (first = highest priority).
        Must send ALL workdays from next_week positions or NONE - partial lists not allowed.
        
        Day values: 0=Monday, 1=Tuesday, ..., 6=Sunday
        
        If save_as_template=true, preferences are saved for future weeks and validated weekly.
        Template remains valid only if workday set doesn't change.
        
        Server will:
        1. Validate that array contains ALL workdays from next_week positions
        2. Delete old preferences (template or specific)
        3. Create single preference record with day_order array
        """
        guard = self.get_object()
        
        # Only the guard themselves can set their day preferences
        # Admins are NOT allowed to modify this
        if request.user.role == User.ROLE_ADMIN:
            return Response(
                {'error': 'Administratori ne mogu mijenjati preferencije čuvara. Samo čuvari mogu postaviti svoje preferencije.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        if guard.user != request.user:
            return Response(
                {'error': 'Možete mijenjati samo svoje preferencije.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        day_of_week_list = request.data.get('day_of_week_list', [])
        save_as_template = request.data.get('save_as_template', False)
        
        if not isinstance(day_of_week_list, list):
            return Response(
                {'error': 'day_of_week_list must be an array'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get settings
        settings = SystemSettings.get_active()
        
        if not settings.next_week_start or not settings.next_week_end:
            return Response(
                {'error': 'Next week period not set yet. Weekly task needs to run first.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        # Check if configuration window is open
        window_error = self._ensure_configuration_window_open(settings)
        if window_error:
            return window_error
        
        # If empty array provided, just delete preferences and return
        # (No work periods check needed for clearing)
        if not day_of_week_list:
            GuardDayPreference.objects.filter(guard=guard, is_template=True).delete()
            GuardDayPreference.objects.filter(
                guard=guard,
                next_week_start=settings.next_week_start,
                is_template=False
            ).delete()
            return Response({
                'message': 'Preferences cleared successfully',
                'preference': None
            })
        
        # PREREQUISITE: Guard must have work periods set (only for non-empty list)
        guard_work_periods = GuardWorkPeriod.objects.filter(
            guard=guard
        ).filter(
            Q(is_template=True) | Q(next_week_start=settings.next_week_start)
        )
        
        if not guard_work_periods.exists():
            return Response(
                {'error': 'Prvo morate postaviti svoje periode rada (work periods) prije postavljanja preferenci za dane.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Get days from guard's work periods (not all next_week days)
        expected_workdays = set(wp.day_of_week for wp in guard_work_periods)
        provided_days = set(day_of_week_list)
        
        # Validate: must provide ALL guard's work period days
        if provided_days != expected_workdays:
            return Response({
                'error': 'Morate navesti SVE dane iz svojih perioda rada ili nijedan. Djelomične liste nisu dopuštene.',
                'expected_workdays': sorted(expected_workdays),
                'received_days': sorted(provided_days),
                'missing': sorted(expected_workdays - provided_days),
                'extra': sorted(provided_days - expected_workdays)
            }, status=status.HTTP_400_BAD_REQUEST)
        
        # Delete old preferences (template or specific week)
        # Always delete template when setting new preferences
        GuardDayPreference.objects.filter(guard=guard, is_template=True).delete()
        
        if not save_as_template:
            # Also delete specific week preferences
            GuardDayPreference.objects.filter(
                guard=guard,
                next_week_start=settings.next_week_start,
                is_template=False
            ).delete()
        
        # Create single preference record with array
        preference = GuardDayPreference.objects.create(
            guard=guard,
            day_order=day_of_week_list,
            is_template=save_as_template,
            next_week_start=None if save_as_template else settings.next_week_start
        )
        
        logger.info(
            "day_preferences_set",
            guard_id=guard.id,
            guard_username=guard.user.username,
            day_count=len(day_of_week_list),
            is_template=save_as_template,
            week_start=str(settings.next_week_start) if not save_as_template else None,
            user_id=request.user.id
        )
        
        serializer = GuardDayPreferenceSerializer(preference)
        
        message = f'Successfully set preferences for {len(day_of_week_list)} days'
        if save_as_template:
            message += ' and saved as template for future weeks.'
        else:
            message += f' for week {settings.next_week_start} - {settings.next_week_end}.'
        
        return Response({
            'message': message,
            'preference': serializer.data
        })
