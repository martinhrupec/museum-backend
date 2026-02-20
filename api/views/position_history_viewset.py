from rest_framework import viewsets, status, permissions, serializers
from rest_framework.decorators import action
from rest_framework.response import Response
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.core.cache import cache
from datetime import datetime
from decimal import Decimal
import structlog

from ..api_models import User, Guard, Position, PositionHistory, Point, AdminNotification, SystemSettings, HourlyRateHistory
from ..serializers import PositionHistorySerializer, AssignedPositionScheduleSerializer, MonthlyPositionSnapshotSerializer
from ..throttles import AssignPositionThrottle, CancelPositionThrottle, BulkCancelThrottle
from ..mixins import AuditLogMixin
from ..permissions import IsAdminRole

logger = structlog.get_logger(__name__)


class PositionHistoryViewSet(AuditLogMixin, viewsets.ModelViewSet):
    """
    ViewSet for working with position history and assignment snapshots.
    
    - All authenticated users can view full history and weekly snapshots
    - Only admins can use CRUD operations (create/update/delete)
    - Guards can only use custom actions (assign, cancel, bulk_cancel, etc.)
    """
    
    queryset = PositionHistory.objects.all()
    serializer_class = PositionHistorySerializer
    permission_classes = [permissions.IsAuthenticated]
    _TAKEN_ACTIONS = {
        PositionHistory.Action.ASSIGNED,
        PositionHistory.Action.REPLACED,
        PositionHistory.Action.SWAPPED,
    }
    _EMPTY_LABEL = 'empty'
    
    def get_permissions(self):
        """
        Admin-only for create/update/delete.
        All authenticated users for list/retrieve and custom actions.
        """
        if self.action in ['create', 'update', 'partial_update', 'destroy']:
            return [IsAdminRole()]
        return [permissions.IsAuthenticated()]

    def get_queryset(self):
        """All authenticated users can inspect the full audit trail
        
        Query params:
            year: Filter by position date year (e.g., 2024)
            month: Filter by position date month (1-12)
            day: Filter by position date day (1-31)
            ordering: Sort order (action_time, -action_time)
        """
        queryset = PositionHistory.objects.select_related('guard__user', 'position__exhibition')
        
        # Date filtering
        year = self.request.query_params.get('year')
        month = self.request.query_params.get('month')
        day = self.request.query_params.get('day')
        
        if year:
            try:
                queryset = queryset.filter(position__date__year=int(year))
            except ValueError:
                pass
        
        if month:
            try:
                queryset = queryset.filter(position__date__month=int(month))
            except ValueError:
                pass
        
        if day:
            try:
                queryset = queryset.filter(position__date__day=int(day))
            except ValueError:
                pass
        
        # Ordering
        ordering = self.request.query_params.get('ordering')
        if ordering in ['action_time', '-action_time']:
            queryset = queryset.order_by(ordering)
        
        return queryset

    def _ensure_manual_window_open(self, period, now, settings):
        if period != 'next_week':
            return None
        manual_open = settings.manual_assignment_start_datetime
        if manual_open is None:
            return Response(
                {'error': 'Period ručnog upisivanja/ispisivanja još nije inicijaliziran. Pričekajte da se tjedni zadatak završi.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        if now < manual_open:
            return Response(
                {
                    'error': 'Ručno upisivanje/ispisivanje za sljedeći tjedan još nije otvoreno.',
                    'manual_assignment_window_opens_at': manual_open.isoformat(),
                },
                status=status.HTTP_403_FORBIDDEN
            )
        return None
    
    def _check_grace_period_restrictions(self, guard, settings, now):
        """
        Check if guard can assign during grace period.
        
        Grace period: First hour after automated assignment.
        Rules:
        - Guards with assigned_count >= minimum: CANNOT assign anything
        - Guards with assigned_count < minimum: CAN assign UP TO minimum only
        
        Returns:
            Response with error if not allowed, None if OK
        """
        grace_start = settings.grace_period_start_datetime
        grace_end = settings.grace_period_end_datetime
        
        if not grace_start or not grace_end:
            return None  # Grace period not initialized
        
        # Check if we're in grace period
        if not (grace_start <= now < grace_end):
            return None  # Not in grace period, no restrictions
        
        # We're in grace period - check guard's current assignment count
        minimum = settings.minimal_number_of_positions_in_week
        
        # Count how many next_week positions this guard is currently assigned to
        next_week_positions = Position.objects.filter(
            date__gte=settings.next_week_start,
            date__lte=settings.next_week_end
        )
        
        assigned_count = 0
        for position in next_week_positions:
            latest_history = position.position_histories.order_by('-action_time', '-id').first()
            if latest_history and latest_history.action in self._TAKEN_ACTIONS and latest_history.guard == guard:
                assigned_count += 1
        
        if assigned_count >= minimum:
            return Response(
                {
                    'error': f'Ograničenje fer perioda: Imate {assigned_count} pozicija (>= minimum {minimum}). Ne možete upisati više od toga tijekom prvog sata.',
                    'grace_period_ends_at': grace_end.isoformat(),
                    'your_assigned_positions': assigned_count,
                    'minimum_required': minimum
                },
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Guard has less than minimum - they can assign up to minimum
        # (Will be allowed, but we could add info message)
        return None

    def _resolve_guard_from_request(self, request):
        if request.user.role == User.ROLE_ADMIN:
            guard_id = request.data.get('guard_id')
            if not guard_id:
                raise serializers.ValidationError('guard_id je obavezan za administratorske akcije.')
            guard = get_object_or_404(Guard, pk=guard_id)
            if not guard.user.is_active:
                raise serializers.ValidationError('Odabrani čuvar nije aktivan.')
            return guard
        # Guard user
        try:
            guard = request.user.guard
        except Guard.DoesNotExist:
            raise serializers.ValidationError('Profil čuvara nije pronađen za trenutnog korisnika.')
        if not guard.user.is_active:
            raise serializers.ValidationError('Vaš račun nije aktivan.')
        return guard
    
    def _invalidate_schedule_cache(self, position, settings):
        """
        Invalidate schedule cache when position assignment changes.
        
        Args:
            position: Position instance that was modified
            settings: SystemSettings instance
        """
        # Check which week this position belongs to
        if settings.this_week_start and settings.this_week_end:
            if settings.this_week_start <= position.date <= settings.this_week_end:
                cache_key = f'schedule_this_week_{settings.this_week_start.isoformat()}'
                cache.delete(cache_key)
        
        if settings.next_week_start and settings.next_week_end:
            if settings.next_week_start <= position.date <= settings.next_week_end:
                cache_key = f'schedule_next_week_{settings.next_week_start.isoformat()}'
                cache.delete(cache_key)

    def _build_assigned_schedule(self, start_date, end_date):
        """Return serialized assignment snapshot for the provided date range"""
        positions_qs = Position.objects.filter(
            date__gte=start_date,
            date__lte=end_date
        ).select_related('exhibition').order_by('date', 'start_time', 'exhibition__name')
        positions = list(positions_qs)
        if not positions:
            return []
        histories = (
            PositionHistory.objects
            .filter(position__in=positions)
            .select_related('guard__user')
            .order_by('position_id', '-action_time', '-id')
        )
        latest_by_position = {}
        for history in histories:
            if history.position_id not in latest_by_position:
                latest_by_position[history.position_id] = history
        schedule_entries = []
        for position in positions:
            latest_history = latest_by_position.get(position.id)
            if latest_history:
                is_taken = latest_history.action in self._TAKEN_ACTIONS
                guard = latest_history.guard if is_taken else None
                last_action = latest_history.action
                last_action_time = latest_history.action_time
            else:
                is_taken = False
                guard = None
                last_action = self._EMPTY_LABEL
                last_action_time = None
            schedule_entries.append({
                'position': position,
                'guard': guard,
                'is_taken': is_taken,
                'last_action': last_action,
                'last_action_time': last_action_time,
            })
        serializer = AssignedPositionScheduleSerializer(schedule_entries, many=True)
        return serializer.data

    def _build_week_response(self, start_date, end_date):
        """Common response wrapper for week-based schedule endpoints"""
        schedule = self._build_assigned_schedule(start_date, end_date)
        return {
            'week_start': start_date,
            'week_end': end_date,
            'positions': schedule,
        }

    @action(detail=True, methods=['post'], url_path='assign', throttle_classes=[AssignPositionThrottle])
    def assign(self, request, pk=None):
        """Manually assign a guard to a position if slot is available"""
        from django.db import transaction
        
        settings = SystemSettings.get_active()
        now = timezone.now()
        
        # Resolve guard first (needed for grace period check)
        try:
            guard = self._resolve_guard_from_request(request)
        except serializers.ValidationError as exc:
            return Response({'error': exc.detail}, status=status.HTTP_400_BAD_REQUEST)
        
        # Race condition protection: Lock position during assignment
        with transaction.atomic():
            position = Position.objects.select_for_update().get(pk=pk)
            period = position.get_period(settings)
            if period is None:
                return Response(
                    {
                        'error': 'Pozicija nije dio rasporeda za ovaj ili sljedeći tjedan.',
                        'debug_info': {
                            'position_date': str(position.date),
                            'this_week_start': str(settings.this_week_start) if settings.this_week_start else None,
                            'this_week_end': str(settings.this_week_end) if settings.this_week_end else None,
                            'next_week_start': str(settings.next_week_start) if settings.next_week_start else None,
                            'next_week_end': str(settings.next_week_end) if settings.next_week_end else None,
                        }
                    },
                    status=status.HTTP_400_BAD_REQUEST
                )
            start_dt = position.get_start_datetime()
            if now >= start_dt:
                return Response(
                    {'error': 'Ne možete upisati poziciju koja je već započela.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Check for time conflicts with guard's other assigned positions on the same date
            same_day_positions = Position.objects.filter(
                date=position.date
            ).exclude(id=position.id).select_related('exhibition')
            
            for other_position in same_day_positions:
                latest_history = other_position.position_histories.order_by('-action_time', '-id').first()
                if latest_history and latest_history.action in self._TAKEN_ACTIONS and latest_history.guard == guard:
                    # Check for time overlap
                    # Positions overlap if: position.start_time < other_position.end_time AND other_position.start_time < position.end_time
                    if position.start_time < other_position.end_time and other_position.start_time < position.end_time:
                        return Response(
                            {
                                'error': f'Vremenski konflikt: već ste prijavljeni na: {other_position.exhibition.name} od {other_position.start_time.strftime("%H:%M")} do {other_position.end_time.strftime("%H:%M")} na taj dan.',
                                'conflicting_position': {
                                    'id': other_position.id,
                                    'exhibition': other_position.exhibition.name,
                                    'start_time': other_position.start_time.strftime('%H:%M'),
                                    'end_time': other_position.end_time.strftime('%H:%M')
                                }
                            },
                            status=status.HTTP_409_CONFLICT
                        )
            
            window_error = self._ensure_manual_window_open(period, now, settings)
            if window_error:
                return window_error
            
            # Check grace period restrictions (applies to both guards and admins)
            grace_error = self._check_grace_period_restrictions(guard, settings, now)
            if grace_error:
                return grace_error
            
            latest_history = position.position_histories.order_by('-action_time', '-id').first()
            if latest_history and latest_history.action in self._TAKEN_ACTIONS:
                return Response(
                    {'error': 'Pozicija je već zauzeta.'},
                    status=status.HTTP_409_CONFLICT
                )
            if latest_history and latest_history.action != PositionHistory.Action.CANCELLED:
                return Response(
                    {'error': 'Pozicija trenutno nije dostupna.'},
                    status=status.HTTP_409_CONFLICT
                )
            if latest_history is None:
                action_type = PositionHistory.Action.ASSIGNED
            else:
                action_type = PositionHistory.Action.REPLACED
            history = PositionHistory.objects.create(
                position=position,
                guard=guard,
                action=action_type
            )
            
            # Award points for jumping in on cancelled position (REPLACED action)
            # Only if:
            # - Position is in this_week OR
            # - Position is in next_week AND manual assignment period has ended
            reward_applied = None
            if action_type == PositionHistory.Action.REPLACED:
                should_reward = False
                if period == 'this_week':
                    should_reward = True
                elif period == 'next_week':
                    manual_end = settings.manual_assignment_end_datetime
                    if manual_end and now >= manual_end:
                        should_reward = True
                
                if should_reward:
                    reward = settings.award_for_jumping_in_on_cancelled_position
                    explanation = f"Award for jumping in on cancelled position ({position.exhibition.name}, {position.date})"
                    
                    reward_point = Point.objects.create(
                        guard=guard,
                        points=reward,
                        explanation=explanation
                    )
                    reward_applied = {
                        'points': float(reward),
                        'explanation': explanation
                    }
            
            # Invalidate schedule cache for affected week
            self._invalidate_schedule_cache(position, settings)
            
            logger.info(
                "position_assigned",
                guard_id=guard.id,
                guard_username=guard.user.username,
                position_id=position.id,
                exhibition=position.exhibition.name,
                date=str(position.date),
                action=action_type,
                reward_points=float(reward) if reward_applied else None,
                user_id=request.user.id
            )
            
            return Response(
                {
                    'message': 'Pozicija uspješno dodijeljena.',
                    'history': PositionHistorySerializer(history).data,
                    'reward_applied': reward_applied
                },
                status=status.HTTP_201_CREATED
            )

    @action(detail=True, methods=['post'], url_path='cancel', throttle_classes=[CancelPositionThrottle])
    def cancel(self, request, pk=None):
        """Cancel current guard assignment for a position"""
        position = get_object_or_404(Position, pk=pk)
        settings = SystemSettings.get_active()
        now = timezone.now()
        period = position.get_period(settings)
        if period is None:
            return Response(
                {
                    'error': 'Pozicija nije dio rasporeda za ovaj ili sljedeći tjedan.',
                    'debug_info': {
                        'position_date': str(position.date),
                        'this_week_start': str(settings.this_week_start) if settings.this_week_start else None,
                        'this_week_end': str(settings.this_week_end) if settings.this_week_end else None,
                        'next_week_start': str(settings.next_week_start) if settings.next_week_start else None,
                        'next_week_end': str(settings.next_week_end) if settings.next_week_end else None,
                    }
                },
                status=status.HTTP_400_BAD_REQUEST
            )
        start_dt = position.get_start_datetime()
        if now >= start_dt:
            return Response(
                {'error': 'Ne možete otkazati poziciju koja je već započela.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        window_error = self._ensure_manual_window_open(period, now, settings)
        if window_error:
            return window_error
        latest_history = position.position_histories.order_by('-action_time', '-id').first()
        if not latest_history or latest_history.action not in self._TAKEN_ACTIONS:
            return Response(
                {'error': 'Pozicija trenutno nije dodijeljena nijednom čuvaru.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        current_guard = latest_history.guard
        if request.user.role == User.ROLE_ADMIN:
            guard_id = request.data.get('guard_id')
            if not guard_id:
                return Response(
                    {'error': 'guard_id je obavezan za administratorska otkazivanja.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            try:
                parsed_guard_id = int(guard_id)
            except (TypeError, ValueError):
                return Response(
                    {'error': 'guard_id mora biti cijeli broj.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if parsed_guard_id != current_guard.id:
                return Response(
                    {'error': 'Navedeni čuvar nije dodijeljen ovoj poziciji.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            guard_for_cancel = current_guard
        else:
            try:
                requester_guard = request.user.guard
            except Guard.DoesNotExist:
                return Response(
                    {'error': 'Profil čuvara nije pronađen za trenutnog korisnika.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            if requester_guard != current_guard:
                return Response(
                    {'error': 'Možete ispisati samo pozicije na kojima ste upisani.'},
                    status=status.HTTP_403_FORBIDDEN
                )
            guard_for_cancel = requester_guard
        history = PositionHistory.objects.create(
            position=position,
            guard=guard_for_cancel,
            action=PositionHistory.Action.CANCELLED
        )
        
        # AUTO-CANCEL: If guard has pending swap request for this position, cancel it
        from ..api_models.textual_model import PositionSwapRequest
        pending_swap = PositionSwapRequest.objects.filter(
            requesting_guard=guard_for_cancel,
            position_to_swap=position,
            status='pending'
        ).first()
        
        if pending_swap:
            pending_swap.status = 'cancelled'
            pending_swap.save()
        
        # Apply penalty only if:
        # - Position is in this_week OR
        # - Position is in next_week AND manual assignment period has ended
        should_penalize = False
        if period == 'this_week':
            should_penalize = True
        elif period == 'next_week':
            manual_end = settings.manual_assignment_end_datetime
            if manual_end and now >= manual_end:
                should_penalize = True
        
        penalty_applied = None
        if should_penalize:
            # Determine penalty amount based on cancellation timing
            today = now.date()
            is_same_day = (position.date == today)
            
            if is_same_day:
                penalty = settings.penalty_for_position_cancellation_on_the_position_day
                explanation = f"Penalty for canceling position on position day ({position.exhibition.name}, {position.date})"
            else:
                penalty = settings.penalty_for_position_cancellation_before_the_position_day
                explanation = f"Penalty for canceling position before position day ({position.exhibition.name}, {position.date})"
            
            penalty_point = Point.objects.create(
                guard=guard_for_cancel,
                points=penalty,
                explanation=explanation
            )
            penalty_applied = {
                'points': float(penalty),
                'explanation': explanation
            }
        
        # Invalidate schedule cache for affected week
        self._invalidate_schedule_cache(position, settings)
        
        logger.info(
            "position_cancelled",
            guard_id=guard_for_cancel.id,
            guard_username=guard_for_cancel.user.username,
            position_id=position.id,
            exhibition=position.exhibition.name,
            date=str(position.date),
            penalty_points=float(penalty) if penalty_applied else None,
            cancelled_by_admin=(request.user.role == User.ROLE_ADMIN),
            user_id=request.user.id
        )
        
        return Response(
            {
                'message': 'Pozicija uspješno ispisana.',
                'history': PositionHistorySerializer(history).data,
                'penalty_applied': penalty_applied
            },
            status=status.HTTP_201_CREATED
        )

    @action(detail=False, methods=['get'], url_path='assigned/this-week')
    def get_this_week_assigned_schedule(self, request):
        """Return assignment snapshot for the current active week"""
        settings = SystemSettings.get_active()
        if not settings.this_week_start or not settings.this_week_end:
            return Response(
                {'error': 'Period ovog tjedna još nije definiran. Pričekajte da se tjedni zadatak završi.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        # Cache key based on week start date
        cache_key = f'schedule_this_week_{settings.this_week_start.isoformat()}'
        
        # Try to get from cache
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return Response(cached_data)
        
        # Build from DB if not cached
        data = self._build_week_response(settings.this_week_start, settings.this_week_end)
        
        # Cache for 2 hours
        cache.set(cache_key, data, timeout=7200)
        
        return Response(data)

    @action(detail=False, methods=['get'], url_path='assigned/next-week')
    def get_next_week_assigned_schedule(self, request):
        """Return assignment snapshot for the configured next week"""
        settings = SystemSettings.get_active()
        if not settings.next_week_start or not settings.next_week_end:
            return Response(
                {'error': 'Period sljedećeg tjedna još nije definiran. Pričekajte da se tjedni zadatak završi.'},
                status=status.HTTP_503_SERVICE_UNAVAILABLE
            )
        
        # Cache key based on week start date
        cache_key = f'schedule_next_week_{settings.next_week_start.isoformat()}'
        
        # Try to get from cache
        cached_data = cache.get(cache_key)
        if cached_data is not None:
            return Response(cached_data)
        
        # Build from DB if not cached
        data = self._build_week_response(settings.next_week_start, settings.next_week_end)
        
        # Cache for 5 minutes
        cache.set(cache_key, data, timeout=300)
        
        return Response(data)
    
    @action(detail=True, methods=['post'], url_path='report-lateness')
    def report_lateness(self, request, pk=None):
        """
        Guard reports being late to their assigned position.
        Automatically applies penalty and creates multicast notification.
        
        Only guards can report their own lateness. Admins cannot report lateness.
        
        POST /api/position-history/{position_id}/report-lateness/
        {
            "estimated_delay_minutes": 15  # Optional
        }
        """
        # Only guards can report their own lateness, admins cannot
        if request.user.role == User.ROLE_ADMIN:
            return Response(
                {'error': 'Administratori ne mogu prijavljivati kašnjenja. Samo čuvari mogu prijaviti svoje kašnjenje.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        position = get_object_or_404(Position, pk=pk)
        settings = SystemSettings.get_active()
        now = timezone.now()
        
        # Verify position is today
        today = now.date()
        if position.date != today:
            return Response(
                {'error': 'Možete prijaviti kašnjenje samo za pozicije koje se odvijaju danas.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verify guard is assigned to this position
        latest_history = position.position_histories.order_by('-action_time', '-id').first()
        if not latest_history or latest_history.action not in self._TAKEN_ACTIONS:
            return Response(
                {'error': 'Trenutno nema čuvara na ovoj poziciji.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Verify requester is the assigned guard
        try:
            requester_guard = request.user.guard
        except Guard.DoesNotExist:
            return Response(
                {'error': 'Profil čuvara nije pronađen za trenutnog korisnika.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if requester_guard != latest_history.guard:
            return Response(
                {'error': 'Možete prijaviti kašnjenje samo za svoje pozicije.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Apply penalty
        penalty = settings.penalty_for_being_late_with_notification
        estimated_delay = request.data.get('estimated_delay_minutes', '')
        delay_info = f" ({estimated_delay} min delay)" if estimated_delay else ""
        explanation = f"Kazna za kašnjenje (uz pravovremenu najavu) ({position.exhibition.name}, {position.date}){delay_info}"
        
        point = Point.objects.create(
            guard=requester_guard,
            points=penalty,
            explanation=explanation
        )
        
        # Create multicast notification for all guards working this shift today
        # Determine shift type based on position start time
        is_weekend = position.date.weekday() in [5, 6]
        if is_weekend:
            is_morning = position.start_time == settings.weekend_morning_start
            shift_type = AdminNotification.SHIFT_MORNING if is_morning else AdminNotification.SHIFT_AFTERNOON
        else:
            is_morning = position.start_time == settings.weekday_morning_start
            shift_type = AdminNotification.SHIFT_MORNING if is_morning else AdminNotification.SHIFT_AFTERNOON
        
        shift_label = 'jutarnja' if shift_type == AdminNotification.SHIFT_MORNING else 'popodnevna'
        notification = AdminNotification.objects.create(
            created_by=None,  # System-created
            title=f"Prijava kašnjenja - {shift_label.title()} smjena",
            message=f"{requester_guard.user.get_full_name() or requester_guard.user.username} prijavljuje kašnjenje {delay_info}.",
            cast_type=AdminNotification.CAST_MULTICAST,
            notification_date=today,
            shift_type=shift_type
        )
        
        return Response(
            {
                'message': 'Kašnjenje uspješno prijavljeno.',
                'penalty_applied': {
                    'points': float(penalty),
                    'explanation': explanation
                },
                'notification_created': {
                    'id': notification.id,
                    'title': notification.title
                }
            },
            status=status.HTTP_201_CREATED
        )
    
    @action(detail=False, methods=['post'], url_path='bulk-cancel', throttle_classes=[BulkCancelThrottle])
    def bulk_cancel(self, request):
        """
        Bulk cancel guard's positions within a date range.
        Only the guard themselves can use this endpoint. Admins are not allowed.
        Only first (closest to today) position incurs penalty.
        
        POST /api/position-history/bulk-cancel/
        {
            "start_date": "2026-01-15",
            "end_date": "2026-01-20"
        }
        """
        # Only guards can use bulk cancel
        if request.user.role == User.ROLE_ADMIN:
            return Response(
                {'error': 'Administratori ne mogu koristiti grupno otkazivanje. Samo čuvari mogu otkazati svoje smjene.'},
                status=status.HTTP_403_FORBIDDEN
            )
        start_date_str = request.data.get('start_date')
        end_date_str = request.data.get('end_date')
        
        if not start_date_str or not end_date_str:
            return Response(
                {'error': 'start_date i end_date su obavezni.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        try:
            from datetime import datetime as dt
            start_date = dt.strptime(start_date_str, '%Y-%m-%d').date()
            end_date = dt.strptime(end_date_str, '%Y-%m-%d').date()
        except ValueError:
            return Response(
                {'error': 'Neispravan format datuma. Koristite YYYY-MM-DD.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        if start_date > end_date:
            return Response(
                {'error': 'start_date mora biti prije ili jednak end_date.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        # Get guard
        try:
            guard = request.user.guard
        except Guard.DoesNotExist:
            return Response(
                {'error': 'Profil čuvara nije pronađen za trenutnog korisnika.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        settings = SystemSettings.get_active()
        now = timezone.now()
        today = now.date()
        
        # Find all positions in date range
        positions_in_range = Position.objects.filter(
            date__gte=start_date,
            date__lte=end_date
        ).prefetch_related('position_histories').order_by('date', 'start_time')
        
        positions_to_cancel = []
        for position in positions_in_range:
            # Check if position has already started
            position_start = position.get_start_datetime()
            if now >= position_start:
                continue  # Skip positions that already started
            
            # Check if this guard is currently assigned to this position
            latest_history = position.position_histories.order_by('-action_time', '-id').first()
            if latest_history and latest_history.action in self._TAKEN_ACTIONS and latest_history.guard == guard:
                positions_to_cancel.append(position)
        
        if not positions_to_cancel:
            return Response(
                {'error': 'Nema prijavljenih pozicija u navedenom rasponu datuma.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Determine penalty logic
        # Check if ALL positions are next_week AND we're in manual assignment period
        all_next_week = all(pos.get_period(settings) == 'next_week' for pos in positions_to_cancel)
        in_manual_period = False
        
        if all_next_week:
            manual_start = settings.manual_assignment_start_datetime
            manual_end = settings.manual_assignment_end_datetime
            if manual_start and manual_end:
                in_manual_period = manual_start <= now < manual_end
        
        # Cancel all positions
        cancelled_count = 0
        penalty_applied = None
        first_position = positions_to_cancel[0]  # Closest to today
        
        for position in positions_to_cancel:
            history = PositionHistory.objects.create(
                position=position,
                guard=guard,
                action=PositionHistory.Action.CANCELLED
            )
            cancelled_count += 1
            
            # Apply penalty only for the first position
            # NO penalty if: ALL positions are next_week AND in manual period
            # YES penalty otherwise
            if position == first_position and penalty_applied is None:
                should_penalize = not (all_next_week and in_manual_period)
                
                if should_penalize:
                    is_same_day = (position.date == today)
                    if is_same_day:
                        penalty = settings.penalty_for_position_cancellation_on_the_position_day
                        explanation = f"Kazna za otkazivanje više smjena odjednom (na dan smjene) - Prva pozicija: {position.exhibition.name}, {position.date}"
                    else:
                        penalty = settings.penalty_for_position_cancellation_before_the_position_day
                        explanation = f"Kazna za otkazivanje više smjena odjednom (više od jednog dana prije te smjene) - Prva pozicija: {position.exhibition.name}, {position.date}"
                    
                    point = Point.objects.create(
                        guard=guard,
                        points=penalty,
                        explanation=explanation
                    )
                    penalty_applied = {
                        'points': float(penalty),
                        'explanation': explanation
                    }
        # Invalidate schedule cache for all affected weeks
        # (positions_to_cancel can span multiple weeks)
        for position in positions_to_cancel:
            self._invalidate_schedule_cache(position, settings)
        return Response(
            {
                'message': f'Uspješno otkazivanje. Broj otkazanih pozicija: {cancelled_count}',
                'cancelled_count': cancelled_count,
                'penalty_applied': penalty_applied,
                'positions': [
                    {
                        'id': p.id,
                        'exhibition': p.exhibition.name,
                        'date': p.date.isoformat(),
                        'start_time': p.start_time.strftime('%H:%M')
                    }
                    for p in positions_to_cancel
                ]
            },
            status=status.HTTP_200_OK
        )
    
    @action(detail=False, methods=['get'], url_path='my-work-history')
    def my_work_history(self, request):
        """
        Get guard's work history with calculated earnings for a specific period.
        
        Query params:
        - month: Optional, 1-12
        - year: Required
        
        Returns:
        - List of completed positions (ASSIGNED, REPLACED, SWAPPED)
        - Total hours worked
        - Total earnings calculated with historical hourly rates
        
        GET /api/position-history/my-work-history/?year=2026&month=1
        GET /api/position-history/my-work-history/?year=2026
        """
        # Verify requester is a guard
        try:
            guard = request.user.guard
        except Guard.DoesNotExist:
            return Response(
                {'error': 'Profil čuvara nije pronađen za trenutnog korisnika.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Parse query parameters
        year_str = request.query_params.get('year')
        month_str = request.query_params.get('month')
        
        if not year_str:
            return Response(
                {'error': 'Parametar year je obavezan.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            year = int(year_str)
        except ValueError:
            return Response(
                {'error': 'year mora biti valjani cijeli broj.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Validate year range
        if year < 2020 or year > 2100:
            return Response(
                {'error': 'year mora biti između 2020 i 2100.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Parse month if provided
        month = None
        if month_str:
            try:
                month = int(month_str)
            except ValueError:
                return Response(
                    {'error': 'month mora biti valjani cijeli broj (1-12).'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            if month < 1 or month > 12:
                return Response(
                    {'error': 'month mora biti između 1 i 12.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        
        # Determine date range
        from datetime import date
        if month:
            # Specific month
            start_date = date(year, month, 1)
            if month == 12:
                end_date = date(year + 1, 1, 1)
            else:
                end_date = date(year, month + 1, 1)
            # Subtract 1 day to get last day of month
            from datetime import timedelta
            end_date = end_date - timedelta(days=1)
            period_label = f"{start_date.strftime('%B %Y')}"
        else:
            # Entire year
            start_date = date(year, 1, 1)
            end_date = date(year, 12, 31)
            period_label = str(year)
        
        # Get all positions in period where this specific guard worked
        # Strategy: Query PositionHistory for this guard, then extract unique positions
        # where guard's latest action was a "taken" action (ASSIGNED/REPLACED/SWAPPED)
        
        history_entries = PositionHistory.objects.filter(
            guard=guard,
            position__date__gte=start_date,
            position__date__lte=end_date
        ).select_related('position__exhibition').order_by('position__date', 'position__start_time', '-action_time', '-id')
        
        # Group by position and keep only latest history per position
        # Only include positions where latest action is "taken"
        seen_positions = set()
        completed_positions = []
        
        for history in history_entries:
            position = history.position
            
            # Skip if we already processed this position
            if position.id in seen_positions:
                continue
            
            seen_positions.add(position.id)
            
            # Verify this guard's latest action on this position is "taken"
            latest_history = position.position_histories.order_by('-action_time', '-id').first()
            
            if latest_history and latest_history.guard == guard and latest_history.action in self._TAKEN_ACTIONS:
                completed_positions.append(position)
        
        # Calculate earnings for each position
        position_details = []
        total_hours = Decimal('0.00')
        total_earnings = Decimal('0.00')
        
        for position in completed_positions:
            # Get duration in hours
            duration_hours = position.get_duration_hours()
            
            # Get position start datetime for rate lookup
            position_datetime = timezone.make_aware(
                datetime.combine(position.date, position.start_time),
                timezone.get_current_timezone()
            )
            
            # Get historical hourly rate for that date
            base_hourly_rate = HourlyRateHistory.get_rate_for_date(position_datetime)
            
            # Sunday bonus: 1.5x hourly rate
            is_sunday = position.date.weekday() == 6
            if is_sunday:
                hourly_rate = base_hourly_rate * Decimal('1.5')
            else:
                hourly_rate = base_hourly_rate
            
            # Calculate earnings
            earnings = duration_hours * hourly_rate
            
            total_hours += duration_hours
            total_earnings += earnings
            
            position_details.append({
                'id': position.id,
                'exhibition': position.exhibition.name,
                'date': position.date.isoformat(),
                'day_of_week': position.date.strftime('%A'),
                'start_time': position.start_time.strftime('%H:%M'),
                'end_time': position.end_time.strftime('%H:%M'),
                'duration_hours': float(duration_hours),
                'base_hourly_rate': float(base_hourly_rate),
                'hourly_rate': float(hourly_rate),
                'is_sunday': is_sunday,
                'earnings': float(earnings)
            })
        
        return Response(
            {
                'period': period_label,
                'guard': {
                    'id': guard.id,
                    'username': guard.user.username,
                    'full_name': guard.user.get_full_name()
                },
                'summary': {
                    'total_positions': len(completed_positions),
                    'total_hours': float(total_hours),
                    'total_earnings': float(total_earnings)
                },
                'positions': position_details
            },
            status=status.HTTP_200_OK
        )
    
    @action(detail=False, methods=['get'], url_path='monthly-snapshot')
    def monthly_snapshot(self, request):
        """
        Get monthly position snapshot with optional guard filtering.
        Returns all positions in a month with their latest history action.
        Includes positions without history (marked as 'empty').
        
        Query params:
        - month: Required, 1-12
        - year: Required
        - guard_id: Optional
          - For admins: 'all' or specific guard ID
          - For guards: 'all' or 'me' (defaults to 'all')
        
        GET /api/position-history/monthly-snapshot/?year=2026&month=1&guard_id=all
        GET /api/position-history/monthly-snapshot/?year=2026&month=1&guard_id=5
        GET /api/position-history/monthly-snapshot/?year=2026&month=1&guard_id=me
        """
        # Parse query parameters
        year_str = request.query_params.get('year')
        month_str = request.query_params.get('month')
        guard_filter = request.query_params.get('guard_id', 'all')
        
        if not year_str or not month_str:
            return Response(
                {'error': 'Parametri year i month su obavezni.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            year = int(year_str)
            month = int(month_str)
        except ValueError:
            return Response(
                {'error': 'year i month moraju biti valjani cijeli brojevi.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if year < 2020 or year > 2100:
            return Response(
                {'error': 'year mora biti između 2020 i 2100.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if month < 1 or month > 12:
            return Response(
                {'error': 'month mora biti između 1 i 12.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Determine date range
        from datetime import date, timedelta
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)
        
        # Resolve guard filter
        filter_guard = None
        is_admin = request.user.role == User.ROLE_ADMIN
        
        if guard_filter == 'me':
            if is_admin:
                return Response(
                    {'error': 'Administratori ne mogu koristiti filter "me". Koristite "all" ili specifični guard_id.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            try:
                filter_guard = request.user.guard
            except Guard.DoesNotExist:
                return Response(
                    {'error': 'Profil čuvara nije pronađen za trenutnog korisnika.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
        elif guard_filter != 'all':
            # Specific guard_id
            try:
                guard_id = int(guard_filter)
                filter_guard = Guard.objects.get(pk=guard_id)
            except (ValueError, TypeError):
                return Response(
                    {'error': 'guard_id mora biti "all", "me" ili valjani cijeli broj.'},
                    status=status.HTTP_400_BAD_REQUEST
                )
            except Guard.DoesNotExist:
                return Response(
                    {'error': f'Čuvar s ID-om {guard_filter} nije pronađen.'},
                    status=status.HTTP_404_NOT_FOUND
                )
        
        # Get all positions in the month
        positions_qs = Position.objects.filter(
            date__gte=start_date,
            date__lte=end_date
        ).select_related('exhibition').order_by('date', 'start_time', 'exhibition__name')
        positions = list(positions_qs)
        
        if not positions:
            return Response({
                'month': month,
                'year': year,
                'period_start': start_date.isoformat(),
                'period_end': end_date.isoformat(),
                'filter_guard_id': filter_guard.id if filter_guard else None,
                'positions': []
            })
        
        # Fetch all histories for these positions
        histories = (
            PositionHistory.objects
            .filter(position__in=positions)
            .select_related('guard__user')
            .order_by('position_id', '-action_time', '-id')
        )
        
        # Get latest history per position
        latest_by_position = {}
        for history in histories:
            if history.position_id not in latest_by_position:
                latest_by_position[history.position_id] = history
        
        # Build snapshot entries
        snapshot_entries = []
        for position in positions:
            latest_history = latest_by_position.get(position.id)
            
            if latest_history:
                is_taken = latest_history.action in self._TAKEN_ACTIONS
                guard = latest_history.guard if is_taken else None
                last_action = latest_history.action
                last_action_time = latest_history.action_time
                position_history_id = latest_history.id
            else:
                is_taken = False
                guard = None
                last_action = self._EMPTY_LABEL
                last_action_time = None
                position_history_id = None
            
            # Apply guard filter
            if filter_guard:
                # When filtering by guard, include only positions where that guard is assigned
                if guard != filter_guard:
                    continue
            
            snapshot_entries.append({
                'position': position,
                'guard': guard,
                'is_taken': is_taken,
                'last_action': last_action,
                'last_action_time': last_action_time,
                'position_history_id': position_history_id,
            })
        
        serializer = MonthlyPositionSnapshotSerializer(snapshot_entries, many=True)
        
        return Response({
            'month': month,
            'year': year,
            'period_start': start_date.isoformat(),
            'period_end': end_date.isoformat(),
            'filter_guard_id': filter_guard.id if filter_guard else None,
            'total_positions': len(snapshot_entries),
            'positions': serializer.data
        })
    
    @action(detail=False, methods=['post'], url_path='monthly-earnings-summary')
    def monthly_earnings_summary(self, request):
        """
        Admin-only endpoint: Get monthly earnings summary for all guards.
        Returns total earnings per guard with breakdown by exhibition.
        
        Uses same calculation logic as my_work_history:
        - Sunday = 1.5x hourly rate
        - Historical hourly rates are used
        
        POST /api/position-history/monthly-earnings-summary/
        {
            "month": 1,
            "year": 2026
        }
        
        Returns:
        {
            "month": 1,
            "year": 2026,
            "guards": [
                {
                    "guard_id": 5,
                    "username": "john",
                    "full_name": "John Doe",
                    "total_hours": 40.0,
                    "total_earnings": 320.0,
                    "exhibitions": [
                        {"exhibition_id": 1, "name": "Modern Art", "hours": 20.0, "earnings": 160.0},
                        {"exhibition_id": 2, "name": "Sculpture", "hours": 20.0, "earnings": 160.0}
                    ]
                },
                ...
            ]
        }
        """
        # Admin only
        if request.user.role != User.ROLE_ADMIN:
            return Response(
                {'error': 'Samo administratori mogu pristupiti mjesečnom pregledu zarade.'},
                status=status.HTTP_403_FORBIDDEN
            )
        
        # Parse request body
        month = request.data.get('month')
        year = request.data.get('year')
        
        if not month or not year:
            return Response(
                {'error': 'month i year su obavezni.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        try:
            month = int(month)
            year = int(year)
        except (ValueError, TypeError):
            return Response(
                {'error': 'month i year moraju biti valjani cijeli brojevi.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if year < 2020 or year > 2100:
            return Response(
                {'error': 'year mora biti između 2020 i 2100.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        if month < 1 or month > 12:
            return Response(
                {'error': 'month mora biti između 1 i 12.'},
                status=status.HTTP_400_BAD_REQUEST
            )
        
        # Determine date range
        from datetime import date, timedelta
        start_date = date(year, month, 1)
        if month == 12:
            end_date = date(year + 1, 1, 1) - timedelta(days=1)
        else:
            end_date = date(year, month + 1, 1) - timedelta(days=1)
        
        # Get all positions in the month with their latest "taken" history
        positions = Position.objects.filter(
            date__gte=start_date,
            date__lte=end_date
        ).select_related('exhibition').prefetch_related('position_histories__guard__user')
        
        # Dictionary to collect earnings by guard and exhibition
        # Structure: {guard_id: {'guard': Guard, 'exhibitions': {exhibition_id: {'exhibition': Exhibition, 'hours': Decimal, 'earnings': Decimal}}}}
        guard_earnings = {}
        
        for position in positions:
            # Get latest history for this position
            latest_history = position.position_histories.order_by('-action_time', '-id').first()
            
            if not latest_history or latest_history.action not in self._TAKEN_ACTIONS:
                continue  # Position not assigned
            
            guard = latest_history.guard
            exhibition = position.exhibition
            
            # Calculate earnings
            duration_hours = position.get_duration_hours()
            
            position_datetime = timezone.make_aware(
                datetime.combine(position.date, position.start_time),
                timezone.get_current_timezone()
            )
            
            base_hourly_rate = HourlyRateHistory.get_rate_for_date(position_datetime)
            
            # Sunday bonus: 1.5x
            is_sunday = position.date.weekday() == 6
            hourly_rate = base_hourly_rate * Decimal('1.5') if is_sunday else base_hourly_rate
            
            earnings = duration_hours * hourly_rate
            
            # Accumulate in dictionary
            if guard.id not in guard_earnings:
                guard_earnings[guard.id] = {
                    'guard': guard,
                    'exhibitions': {}
                }
            
            if exhibition.id not in guard_earnings[guard.id]['exhibitions']:
                guard_earnings[guard.id]['exhibitions'][exhibition.id] = {
                    'exhibition': exhibition,
                    'hours': Decimal('0.00'),
                    'earnings': Decimal('0.00')
                }
            
            guard_earnings[guard.id]['exhibitions'][exhibition.id]['hours'] += duration_hours
            guard_earnings[guard.id]['exhibitions'][exhibition.id]['earnings'] += earnings
        
        # Build response
        guards_summary = []
        for guard_id, data in guard_earnings.items():
            guard = data['guard']
            exhibitions = data['exhibitions']
            
            total_hours = sum(ex['hours'] for ex in exhibitions.values())
            total_earnings = sum(ex['earnings'] for ex in exhibitions.values())
            
            exhibition_details = [
                {
                    'exhibition_id': ex_id,
                    'name': ex_data['exhibition'].name,
                    'hours': float(ex_data['hours']),
                    'earnings': float(ex_data['earnings'])
                }
                for ex_id, ex_data in exhibitions.items()
            ]
            
            # Sort exhibitions by name
            exhibition_details.sort(key=lambda x: x['name'])
            
            guards_summary.append({
                'guard_id': guard.id,
                'username': guard.user.username,
                'full_name': guard.user.get_full_name(),
                'total_hours': float(total_hours),
                'total_earnings': float(total_earnings),
                'exhibitions': exhibition_details
            })
        
        # Sort guards by full_name
        guards_summary.sort(key=lambda x: x['full_name'] or x['username'])
        
        # Calculate grand totals
        grand_total_hours = sum(g['total_hours'] for g in guards_summary)
        grand_total_earnings = sum(g['total_earnings'] for g in guards_summary)
        
        return Response({
            'month': month,
            'year': year,
            'period_start': start_date.isoformat(),
            'period_end': end_date.isoformat(),
            'summary': {
                'total_guards': len(guards_summary),
                'total_hours': grand_total_hours,
                'total_earnings': grand_total_earnings
            },
            'guards': guards_summary
        })


