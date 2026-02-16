from rest_framework import serializers
from django.db import models
from .api_models import (
    User, Guard, Exhibition, Position, PositionHistory, Point,
    GuardAvailablePositions, AdminNotification, Report, SystemSettings,
    GuardExhibitionPreference, GuardDayPreference, NonWorkingDay, GuardWorkPeriod,
    AuditLog
)


# ========================================
# USER SERIALIZERS
# ========================================

class UserBasicSerializer(serializers.ModelSerializer):
    """
    Basic User info for public lists and references.
    Contains only essential, safe information.
    """
    full_name = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = ['id', 'username', 'first_name', 'last_name', 'full_name', 'role']
        read_only_fields = ['id', 'username', 'role', 'full_name']
    
    def get_full_name(self, obj):
        """Return formatted full name or username as fallback"""
        full_name = f"{obj.first_name} {obj.last_name}".strip()
        return full_name if full_name else obj.username


class UserDetailSerializer(serializers.ModelSerializer):
    """
    Detailed User info for authenticated users viewing profiles.
    Includes additional information like email, dates, activity status.
    """
    full_name = serializers.SerializerMethodField()
    guard_profile = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name',
            'role', 'is_active', 'date_joined', 'last_login', 'last_mobile_login', 'guard_profile'
        ]
        read_only_fields = ['id', 'username', 'date_joined', 'last_login', 'last_mobile_login', 'full_name', 'guard_profile']
    
    def get_full_name(self, obj):
        full_name = f"{obj.first_name} {obj.last_name}".strip()
        return full_name if full_name else obj.username
    
    def get_guard_profile(self, obj):
        """Return guard profile if user is a guard"""
        if obj.role == User.ROLE_GUARD and hasattr(obj, 'guard'):
            from .serializers import GuardBasicSerializer  # Avoid circular import
            return GuardBasicSerializer(obj.guard).data
        return None


class UserAdminSerializer(serializers.ModelSerializer):
    """
    Admin-level User serializer with full access to all fields.
    Used for admin operations - create, update, manage permissions.
    Password is required for CREATE, optional for UPDATE.
    """
    full_name = serializers.SerializerMethodField()
    guard_profile = serializers.SerializerMethodField()
    
    class Meta:
        model = User
        fields = [
            'id', 'username', 'email', 'first_name', 'last_name', 'full_name',
            'role', 'is_active', 'is_staff', 'is_superuser', 'date_joined', 
            'last_login', 'last_mobile_login', 'updated_at', 'guard_profile', 'password'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login', 'last_mobile_login', 'updated_at', 'full_name', 'guard_profile']
        extra_kwargs = {
            'password': {
                'write_only': True,
                'required': False,
                'help_text': 'Required for new user creation, optional for updates'
            }
        }
    
    def get_full_name(self, obj):
        full_name = f"{obj.first_name} {obj.last_name}".strip()
        return full_name if full_name else obj.username
    
    def get_guard_profile(self, obj):
        if obj.role == User.ROLE_GUARD and hasattr(obj, 'guard'):
            # Import here to avoid circular dependency
            return GuardBasicSerializer(obj.guard).data
        return None
    
    def validate(self, data):
        """Validate that password is provided for new user creation"""
        # If this is a CREATE operation (no instance exists) and no password provided
        if not self.instance and not data.get('password'):
            raise serializers.ValidationError({
                'password': 'Password is required when creating a new user.'
            })
        return data
    
    def update(self, instance, validated_data):
        """Handle password updates if provided"""
        password = validated_data.pop('password', None)
        if password:
            instance.set_password(password)
        return super().update(instance, validated_data)
    
    def create(self, validated_data):
        """Handle user creation with password"""
        password = validated_data.pop('password')  # Password je obavezan zbog validate()
        user = User.objects.create_user(password=password, **validated_data)
        return user


class ChangePasswordSerializer(serializers.Serializer):
    """
    Serializer for password change endpoint.
    Validates old password and ensures new password confirmation.
    """
    old_password = serializers.CharField(required=True)
    new_password = serializers.CharField(required=True, min_length=8)
    new_password_confirm = serializers.CharField(required=True)
    
    def validate_old_password(self, value):
        """Validate that the old password is correct"""
        user = self.context['request'].user
        if not user.check_password(value):
            raise serializers.ValidationError("Stara lozinka nije točna.")
        return value
    
    def validate(self, data):
        """Validate that new passwords match"""
        if data['new_password'] != data['new_password_confirm']:
            raise serializers.ValidationError({
                'new_password_confirm': 'Nove lozinke se ne slažu.'
            })
        return data
    
    def save(self, **kwargs):
        """Change the user's password"""
        user = self.context['request'].user
        user.set_password(self.validated_data['new_password'])
        user.save()
        return user


# ========================================
# GUARD SERIALIZERS  
# ========================================

class GuardBasicSerializer(serializers.ModelSerializer):
    """
    Basic Guard info for lists and references.
    Includes user basic info and essential guard data.
    """
    username = serializers.CharField(source='user.username', read_only=True)
    full_name = serializers.SerializerMethodField()
    is_active = serializers.BooleanField(source='user.is_active', read_only=True)
    
    class Meta:
        model = Guard
        fields = ['id', 'username', 'full_name', 'is_active', 'priority_number', 'availability', 'availability_updated_at']
        read_only_fields = ['id', 'username', 'full_name', 'is_active', 'priority_number', 'availability', 'availability_updated_at']
    
    def get_full_name(self, obj):
        full_name = f"{obj.user.first_name} {obj.user.last_name}".strip()
        return full_name if full_name else obj.user.username


class GuardDetailSerializer(serializers.ModelSerializer):
    """
    Detailed Guard info for guard profiles and detailed views.
    Includes user details and all guard-specific information.
    """
    user = UserDetailSerializer(read_only=True)
    total_points = serializers.SerializerMethodField()
    recent_positions_count = serializers.SerializerMethodField()
    
    class Meta:
        model = Guard
        fields = [
            'id', 'user', 'priority_number', 'availability', 'availability_updated_at',
            'total_points', 'recent_positions_count'
        ]
        read_only_fields = ['id', 'user', 'priority_number', 'availability_updated_at', 'total_points', 'recent_positions_count']
    
    def get_total_points(self, obj):
        """Calculate total points for this guard"""
        return obj.points.aggregate(total=models.Sum('points'))['total'] or 0
    
    def get_recent_positions_count(self, obj):
        """Count positions in last 30 days"""
        from django.utils import timezone
        from datetime import timedelta
        thirty_days_ago = timezone.now() - timedelta(days=30)
        return obj.position_histories.filter(
            action='ASSIGNED', 
            action_time__gte=thirty_days_ago
        ).count()


class GuardAdminSerializer(serializers.ModelSerializer):
    """
    Admin-level Guard serializer with full management capabilities.
    Includes user admin data and all guard statistics.
    
    NOTE: Admins can read all fields but cannot modify:
    - priority_number (system-managed)
    - availability (guard-only via set_availability action)
    
    Admins can only modify guard via user fields (username, password, is_active).
    """
    user = UserAdminSerializer(read_only=True)
    total_points = serializers.SerializerMethodField()
    position_stats = serializers.SerializerMethodField()
    
    class Meta:
        model = Guard
        fields = [
            'id', 'user', 'priority_number', 'availability', 'availability_updated_at',
            'total_points', 'position_stats'
        ]
        read_only_fields = ['id', 'user', 'priority_number', 'availability', 'availability_updated_at', 'total_points', 'position_stats']
    
    def get_total_points(self, obj):
        from django.db import models
        return obj.points.aggregate(total=models.Sum('points'))['total'] or 0
    
    def get_position_stats(self, obj):
        """Comprehensive position statistics"""
        from django.db import models
        from django.utils import timezone
        from datetime import timedelta
        
        # Calculate various stats
        thirty_days_ago = timezone.now() - timedelta(days=30)
        
        return {
            'total_assigned': obj.position_histories.filter(action='ASSIGNED').count(),
            'total_cancelled': obj.position_histories.filter(action='CANCELED').count(),
            'recent_assigned': obj.position_histories.filter(
                action='ASSIGNED', action_time__gte=thirty_days_ago
            ).count(),
            'available_positions': obj.guard_available_positions.count(),
            'completion_rate': self._calculate_completion_rate(obj)
        }
    
    def _calculate_completion_rate(self, guard):
        """Calculate position completion rate"""
        assigned = guard.position_histories.filter(action='ASSIGNED').count()
        cancelled = guard.position_histories.filter(action='CANCELED').count()
        
        if assigned == 0:
            return 0
        
        completed = assigned - cancelled
        return round((completed / assigned) * 100, 2)


# ========================================
# EXHIBITION SERIALIZERS
# ========================================

class ExhibitionBasicSerializer(serializers.ModelSerializer):
    """
    Basic Exhibition info for lists and references.
    Essential exhibition data without heavy details.
    """
    status = serializers.SerializerMethodField()
    duration_days = serializers.SerializerMethodField()
    
    class Meta:
        model = Exhibition
        fields = [
            'id', 'name', 'start_date', 'end_date', 'open_on',
            'status', 'duration_days', 'number_of_positions',
            'is_special_event', 'event_start_time', 'event_end_time'
        ]
        read_only_fields = ['id', 'status', 'duration_days']
    
    def get_status(self, obj):
        """Return exhibition status"""
        if obj.is_active():
            return 'active'
        elif obj.is_upcoming:
            return 'upcoming'
        else:
            return 'finished'
    
    def get_duration_days(self, obj):
        """Calculate exhibition duration in days"""
        return (obj.end_date.date() - obj.start_date.date()).days + 1


class ExhibitionDetailSerializer(serializers.ModelSerializer):
    """
    Detailed Exhibition info with positions and statistics.
    Used for exhibition detail pages and planning.
    """
    status = serializers.SerializerMethodField()
    duration_days = serializers.SerializerMethodField()
    position_count = serializers.SerializerMethodField()
    assigned_positions = serializers.SerializerMethodField()
    
    class Meta:
        model = Exhibition
        fields = [
            'id', 'name', 'number_of_positions', 'start_date', 'end_date', 'open_on',
            'rules', 'status', 'duration_days', 'position_count', 
            'assigned_positions', 'created_at', 'updated_at',
            'is_special_event', 'event_start_time', 'event_end_time'
        ]
        read_only_fields = [
            'id', 'status', 'duration_days', 'position_count', 
            'assigned_positions', 'created_at', 'updated_at'
        ]
    
    def get_status(self, obj):
        if obj.is_active():
            return 'active'
        elif obj.is_upcoming:
            return 'upcoming'
        else:
            return 'finished'
    
    def get_duration_days(self, obj):
        return (obj.end_date.date() - obj.start_date.date()).days + 1
    
    def get_position_count(self, obj):
        """Actual number of created positions"""
        return obj.positions.count()
    
    def get_assigned_positions(self, obj):
        """Number of positions that have been assigned"""
        from .api_models import PositionHistory
        assigned_position_ids = PositionHistory.objects.filter(
            position__exhibition=obj,
            action__in=[
                PositionHistory.Action.ASSIGNED,
                PositionHistory.Action.REPLACED,
                PositionHistory.Action.SWAPPED,
            ]
        ).values_list('position_id', flat=True).distinct()
        
        return len(assigned_position_ids)


class ExhibitionAdminSerializer(serializers.ModelSerializer):
    """
    Admin-level Exhibition serializer with full management data.
    Includes comprehensive statistics and management information.
    """
    status = serializers.SerializerMethodField()
    duration_days = serializers.SerializerMethodField()
    position_stats = serializers.SerializerMethodField()
    guard_stats = serializers.SerializerMethodField()
    
    class Meta:
        model = Exhibition
        fields = [
            'id', 'name', 'number_of_positions', 'start_date', 'end_date', 'open_on',
            'rules', 'status', 'duration_days', 'position_stats', 
            'guard_stats', 'created_at', 'updated_at',
            'is_special_event', 'event_start_time', 'event_end_time'
        ]
        read_only_fields = [
            'id', 'status', 'duration_days', 'position_stats', 
            'guard_stats', 'created_at', 'updated_at'
        ]
    
    def validate_open_on(self, value):
        """Validate that open_on days are subset of museum workdays"""
        from .api_models import SystemSettings
        settings = SystemSettings.load()
        
        if not set(value).issubset(set(settings.workdays)):
            raise serializers.ValidationError(
                f"Exhibition days must be a subset of museum workdays. "
                f"Museum workdays: {settings.workdays}, Provided: {value}"
            )
        
        return value
    
    def get_status(self, obj):
        if obj.is_active():
            return 'active'
        elif obj.is_upcoming:
            return 'upcoming'
        else:
            return 'finished'
    
    def get_duration_days(self, obj):
        return (obj.end_date.date() - obj.start_date.date()).days + 1
    
    def get_position_stats(self, obj):
        """Comprehensive position statistics"""
        from .api_models import PositionHistory
        
        total_positions = obj.positions.count()
        assigned_position_ids = PositionHistory.objects.filter(
            position__exhibition=obj,
            action__in=[
                PositionHistory.Action.ASSIGNED,
                PositionHistory.Action.REPLACED,
                PositionHistory.Action.SWAPPED,
            ]
        ).values_list('position_id', flat=True).distinct()
        
        cancelled_position_ids = PositionHistory.objects.filter(
            position__exhibition=obj,
            action=PositionHistory.Action.CANCELLED
        ).values_list('position_id', flat=True).distinct()
        
        assigned_count = len(assigned_position_ids)
        cancelled_count = len(cancelled_position_ids)
        
        return {
            'total_positions': total_positions,
            'required_positions': obj.number_of_positions,
            'assigned_positions': assigned_count,
            'cancelled_positions': cancelled_count,
            'unassigned_positions': total_positions - assigned_count,
            'assignment_rate': round((assigned_count / total_positions * 100), 2) if total_positions > 0 else 0
        }
    
    def get_guard_stats(self, obj):
        """Guard-related statistics for this exhibition"""
        from .api_models import PositionHistory
        
        # Get unique guards assigned to this exhibition
        guard_ids = PositionHistory.objects.filter(
            position__exhibition=obj,
            action__in=[
                PositionHistory.Action.ASSIGNED,
                PositionHistory.Action.REPLACED,
                PositionHistory.Action.SWAPPED,
            ]
        ).values_list('guard_id', flat=True).distinct()
        
        return {
            'unique_guards_assigned': len(guard_ids),
            'total_assignments': PositionHistory.objects.filter(
                position__exhibition=obj,
                action__in=[
                    PositionHistory.Action.ASSIGNED,
                    PositionHistory.Action.REPLACED,
                    PositionHistory.Action.SWAPPED,
                ]
            ).count()
        }


# ========================================
# POSITION SERIALIZERS
# ========================================

class PositionBasicSerializer(serializers.ModelSerializer):
    """Basic Position info for lists"""
    exhibition_name = serializers.CharField(source='exhibition.name', read_only=True)
    is_special_event = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Position
        fields = ['id', 'exhibition', 'exhibition_name', 'date', 'start_time', 'end_time', 'is_special_event']
        read_only_fields = ['id', 'exhibition_name', 'is_special_event']


class PositionDetailSerializer(serializers.ModelSerializer):
    """Detailed Position with exhibition and assignment info"""
    exhibition = ExhibitionBasicSerializer(read_only=True)
    exhibition_id = serializers.PrimaryKeyRelatedField(
        queryset=Exhibition.objects.all(),
        source='exhibition',
        write_only=True
    )
    assigned_guard = serializers.SerializerMethodField()
    is_special_event = serializers.BooleanField(read_only=True)
    
    class Meta:
        model = Position
        fields = [
            'id', 'exhibition', 'exhibition_id', 'date', 'start_time', 'end_time',
            'assigned_guard', 'is_special_event', 'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'assigned_guard', 'is_special_event', 'created_at', 'updated_at']
    
    def get_assigned_guard(self, obj):
        """Get currently assigned guard if any"""
        from .api_models import PositionHistory
        latest = obj.position_histories.filter(
            action__in=[
                PositionHistory.Action.ASSIGNED,
                PositionHistory.Action.REPLACED,
                PositionHistory.Action.SWAPPED,
            ]
        ).order_by('-action_time', '-id').first()
        
        if latest:
            return GuardBasicSerializer(latest.guard).data
        return None


# ========================================
# POSITION HISTORY SERIALIZERS
# ========================================

class PositionHistorySerializer(serializers.ModelSerializer):
    """Position history for audit trail"""
    guard = GuardBasicSerializer(read_only=True)
    position = PositionBasicSerializer(read_only=True)
    guard_id = serializers.PrimaryKeyRelatedField(
        queryset=Guard.objects.all(),
        source='guard',
        write_only=True,
        required=False
    )
    position_id = serializers.PrimaryKeyRelatedField(
        queryset=Position.objects.all(),
        source='position',
        write_only=True,
        required=False
    )
    
    class Meta:
        model = PositionHistory
        fields = ['id', 'position', 'guard', 'position_id', 'guard_id', 'action', 'action_time']
        read_only_fields = ['id', 'action_time']


class AssignedPositionScheduleSerializer(serializers.Serializer):
    """Serializer for current assignment snapshot per position"""
    position = PositionBasicSerializer(read_only=True)
    guard = GuardBasicSerializer(read_only=True, allow_null=True)
    is_taken = serializers.BooleanField()
    last_action = serializers.CharField()
    last_action_time = serializers.DateTimeField(allow_null=True)


# ========================================
# POINT SERIALIZERS
# ========================================

class PointSerializer(serializers.ModelSerializer):
    """Point record for guard scoring"""
    guard_name = serializers.CharField(source='guard.user.username', read_only=True)
    
    class Meta:
        model = Point
        fields = ['id', 'guard', 'guard_name', 'points', 'date_awarded', 'explanation']
        read_only_fields = ['id', 'guard_name', 'date_awarded']


# ========================================
# GUARD WORK PERIOD SERIALIZERS
# ========================================

class GuardWorkPeriodSerializer(serializers.ModelSerializer):
    """Serializer for guard work periods (time-based availability)"""
    
    class Meta:
        model = GuardWorkPeriod
        fields = ['id', 'guard', 'day_of_week', 'shift_type', 'is_template', 'next_week_start', 'created_at']
        read_only_fields = ['id', 'guard', 'created_at']
    
    def validate_day_of_week(self, value):
        """Validate day of week is between 0-6"""
        if not (0 <= value <= 6):
            raise serializers.ValidationError("Day of week must be between 0 (Monday) and 6 (Sunday)")
        return value
    
    def validate_shift_type(self, value):
        """Validate shift type is morning or afternoon"""
        if value not in ['morning', 'afternoon']:
            raise serializers.ValidationError("Shift type must be 'morning' or 'afternoon'")
        return value


# ========================================
# GUARD AVAILABLE POSITIONS SERIALIZERS
# ========================================

class GuardAvailablePositionsSerializer(serializers.ModelSerializer):
    """Guard availability for positions"""
    guard = GuardBasicSerializer(read_only=True)
    position = PositionBasicSerializer(read_only=True)
    
    class Meta:
        model = GuardAvailablePositions
        fields = ['id', 'guard', 'position', 'score', 'created_at', 'updated_at']
        read_only_fields = ['id', 'created_at', 'updated_at']


# ========================================
# ADMIN NOTIFICATION SERIALIZERS
# ========================================

class AdminNotificationSerializer(serializers.ModelSerializer):
    """
    Admin notifications/announcements with cast types.
    
    Cast Types:
    - broadcast: Shown to all users
    - unicast: Shown to specific user (to_user_id required)
    - multicast: Shown to guards on specific positions (notification_date required, 
                 optionally filtered by shift_type and/or exhibition_id)
    """
    created_by = UserBasicSerializer(read_only=True)
    to_user = UserBasicSerializer(read_only=True)
    exhibition = ExhibitionBasicSerializer(read_only=True)
    
    # Write fields for creating notifications
    created_by_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    to_user_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    exhibition_id = serializers.IntegerField(write_only=True, required=False, allow_null=True)
    
    class Meta:
        model = AdminNotification
        fields = [
            'id', 'created_by', 'created_by_id', 'title', 'message', 
            'cast_type', 'to_user', 'to_user_id', 
            'notification_date', 'shift_type',
            'exhibition', 'exhibition_id',
            'expires_at',
            'created_at', 'updated_at'
        ]
        read_only_fields = ['id', 'created_at', 'updated_at']
    
    def validate(self, attrs):
        """Validate notification based on cast_type"""
        cast_type = attrs.get('cast_type', AdminNotification.CAST_BROADCAST)
        
        if cast_type == AdminNotification.CAST_UNICAST:
            if not attrs.get('to_user_id'):
                raise serializers.ValidationError(
                    "Unicast notification must have to_user_id set."
                )
        
        elif cast_type == AdminNotification.CAST_MULTICAST:
            if not attrs.get('notification_date'):
                raise serializers.ValidationError(
                    "Multicast notification must have notification_date set."
                )
        
        return attrs


# ========================================
# REPORT SERIALIZERS
# ========================================

class ReportSerializer(serializers.ModelSerializer):
    """Guard reports about positions"""
    guard = GuardBasicSerializer(read_only=True)
    position = PositionBasicSerializer(read_only=True)
    position_id = serializers.PrimaryKeyRelatedField(
        queryset=Position.objects.all(),
        source='position',
        write_only=True,
        required=True
    )
    
    class Meta:
        model = Report
        fields = [
            'id', 'guard', 'position', 'position_id', 
            'report_text', 'created_at'
        ]
        read_only_fields = ['id', 'guard', 'created_at']


# ========================================
# SYSTEM SETTINGS SERIALIZERS
# ========================================

class SystemSettingsSerializer(serializers.ModelSerializer):
    """System-wide settings with version history"""
    
    updated_by_name = serializers.CharField(source='updated_by.get_full_name', read_only=True)
    
    # Read-only computed fields (derived from assignment time)
    config_start_day = serializers.IntegerField(read_only=True)
    config_start_time = serializers.TimeField(read_only=True)
    config_end_day = serializers.IntegerField(read_only=True)
    config_end_time = serializers.TimeField(read_only=True)
    manual_assignment_day = serializers.IntegerField(read_only=True)
    manual_assignment_time = serializers.TimeField(read_only=True)
    manual_assignment_end_day = serializers.IntegerField(read_only=True, allow_null=True)
    manual_assignment_end_time = serializers.TimeField(read_only=True, allow_null=True)
    grace_period_start_day = serializers.IntegerField(read_only=True)
    grace_period_start_time = serializers.TimeField(read_only=True)
    grace_period_end_day = serializers.IntegerField(read_only=True)
    grace_period_end_time = serializers.TimeField(read_only=True)
    timing_windows = serializers.SerializerMethodField()
    
    class Meta:
        model = SystemSettings
        fields = [
            'id', 'workdays', 
            'this_week_start', 'this_week_end',
            'next_week_start', 'next_week_end',
            # Automated assignment (admin-controlled)
            'day_for_assignments', 'time_of_assignments',
            # Computed timing (read-only)
            'config_start_day', 'config_start_time',
            'config_end_day', 'config_end_time',
            'manual_assignment_day', 'manual_assignment_time',
            'manual_assignment_end_day', 'manual_assignment_end_time',
            'grace_period_start_day', 'grace_period_start_time',
            'grace_period_end_day', 'grace_period_end_time',
            'timing_windows',
            # Point system
            'points_life_weeks',
            'minimal_number_of_positions_in_week', 'award_for_position_completion',
            'award_for_sunday_position_completion', 
            'award_for_jumping_in_on_cancelled_position',
            'penalty_for_being_late_with_notification',
            'penalty_for_being_late_without_notification',
            'penalty_for_position_cancellation_on_the_position_day',
            'penalty_for_position_cancellation_before_the_position_day',
            'penalty_for_assigning_less_then_minimal_positions',
            # Payroll
            'hourly_rate',
            # Shift times
            'weekday_morning_start', 'weekday_morning_end',
            'weekday_afternoon_start', 'weekday_afternoon_end',
            'weekend_morning_start', 'weekend_morning_end',
            'weekend_afternoon_start', 'weekend_afternoon_end',
            'created_at', 'updated_by', 'updated_by_name', 'is_active'
        ]
        read_only_fields = [
            'id', 'created_at', 'updated_by', 'updated_by_name', 'is_active', 
            'this_week_start', 'this_week_end', 'next_week_start', 'next_week_end',
            'timing_windows',
            # Assignment timing is controlled by Celery Beat schedule in settings.py
            'day_for_assignments', 'time_of_assignments',
            # Shift times are hardcoded for cron jobs - cannot be changed
            'weekday_morning_start', 'weekday_morning_end',
            'weekday_afternoon_start', 'weekday_afternoon_end',
            'weekend_morning_start', 'weekend_morning_end',
            'weekend_afternoon_start', 'weekend_afternoon_end'
        ]

    def get_timing_windows(self, obj):
        return obj.timing_windows


# ========================================
# PREFERENCE SERIALIZERS
# ========================================

class GuardExhibitionPreferenceSerializer(serializers.ModelSerializer):
    """Guard's exhibition preferences - bulk storage with template support"""
    guard = GuardBasicSerializer(read_only=True)
    
    class Meta:
        model = GuardExhibitionPreference
        fields = ['id', 'guard', 'exhibition_order', 'is_template', 'next_week_start', 'created_at']
        read_only_fields = ['id', 'created_at']


class GuardDayPreferenceSerializer(serializers.ModelSerializer):
    """Guard's day preferences - bulk storage with template support"""
    guard = GuardBasicSerializer(read_only=True)
    
    class Meta:
        model = GuardDayPreference
        fields = ['id', 'guard', 'day_order', 'is_template', 'next_week_start', 'created_at']
        read_only_fields = ['id', 'created_at']


# ========================================
# NON-WORKING DAY SERIALIZERS
# ========================================

class NonWorkingDaySerializer(serializers.ModelSerializer):
    """Non-working days serializer"""
    created_by_username = serializers.CharField(source='created_by.username', read_only=True)
    
    class Meta:
        model = NonWorkingDay
        fields = [
            'id', 'date', 'is_full_day', 'non_working_shift', 'reason',
            'created_by', 'created_by_username', 'created_at'
        ]
        read_only_fields = ['id', 'created_by', 'created_by_username', 'created_at']
    
    def validate(self, data):
        """Validate that non_working_shift is provided if not full day"""
        if not data.get('is_full_day') and not data.get('non_working_shift'):
            raise serializers.ValidationError({
                'non_working_shift': 'Ovo polje je obavezno kada dan nije potpuno neradni.'
            })
        return data


# ========================================
# POSITION SWAP REQUEST SERIALIZERS
# ========================================

class PositionSwapRequestSerializer(serializers.ModelSerializer):
    """Position swap request serializer"""
    requesting_guard_name = serializers.CharField(
        source='requesting_guard.user.get_full_name',
        read_only=True
    )
    position_to_swap_details = PositionBasicSerializer(
        source='position_to_swap',
        read_only=True
    )
    accepted_by_guard_name = serializers.CharField(
        source='accepted_by_guard.user.get_full_name',
        read_only=True,
        allow_null=True
    )
    position_offered_details = PositionBasicSerializer(
        source='position_offered_in_return',
        read_only=True,
        allow_null=True
    )
    
    class Meta:
        from api.api_models.textual_model import PositionSwapRequest
        model = PositionSwapRequest
        fields = [
            'id', 'requesting_guard', 'requesting_guard_name',
            'position_to_swap', 'position_to_swap_details',
            'status', 'accepted_by_guard', 'accepted_by_guard_name',
            'position_offered_in_return', 'position_offered_details',
            'expires_at', 'created_at', 'accepted_at'
        ]
        read_only_fields = [
            'id', 'requesting_guard', 'requesting_guard_name',
            'status', 'accepted_by_guard', 'accepted_by_guard_name',
            'position_offered_in_return', 'position_offered_details',
            'created_at', 'accepted_at'
        ]


class EligibleSwapRequestSerializer(serializers.Serializer):
    """
    Serializer for swap requests shown to eligible guards.
    Includes positions the guard can offer in return.
    """
    swap_request = PositionSwapRequestSerializer(read_only=True)
    positions_can_offer = PositionBasicSerializer(many=True, read_only=True)


# ========================================
# AUDIT LOG SERIALIZERS
# ========================================

class AuditLogSerializer(serializers.ModelSerializer):
    """
    Audit log serializer for tracking admin actions.
    Read-only serializer showing complete audit trail.
    """
    user_name = serializers.CharField(source='user.username', read_only=True)
    user_full_name = serializers.CharField(source='user.get_full_name', read_only=True)
    action_display = serializers.CharField(source='get_action_display', read_only=True)
    
    class Meta:
        model = AuditLog
        fields = [
            'id', 'user', 'user_name', 'user_full_name',
            'action', 'action_display',
            'model_name', 'object_id', 'object_repr',
            'changes', 'ip_address', 'user_agent',
            'timestamp'
        ]
        read_only_fields = fields  # All fields are read-only
