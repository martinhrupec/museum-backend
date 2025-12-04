from rest_framework import serializers
from django.db import models
from .api_models import User, Guard, Exhibition


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
            'role', 'is_active', 'date_joined', 'last_login', 'guard_profile'
        ]
        read_only_fields = ['id', 'username', 'date_joined', 'last_login', 'full_name', 'guard_profile']
    
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
            'last_login', 'updated_at', 'guard_profile', 'password'
        ]
        read_only_fields = ['id', 'date_joined', 'last_login', 'updated_at', 'full_name', 'guard_profile']
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
        fields = ['id', 'username', 'full_name', 'is_active', 'priority_number']
        read_only_fields = ['id', 'username', 'full_name', 'is_active']
    
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
            'id', 'user', 'priority_number', 'availability', 
            'total_points', 'recent_positions_count'
        ]
        read_only_fields = ['id', 'user', 'total_points', 'recent_positions_count']
    
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
    """
    user = UserAdminSerializer(read_only=True)
    total_points = serializers.SerializerMethodField()
    position_stats = serializers.SerializerMethodField()
    
    class Meta:
        model = Guard
        fields = [
            'id', 'user', 'priority_number', 'availability',
            'total_points', 'position_stats'
        ]
        read_only_fields = ['id', 'user', 'total_points', 'position_stats']
    
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
            'id', 'name', 'start_date', 'end_date', 
            'status', 'duration_days', 'number_of_positions'
        ]
        read_only_fields = ['id', 'status', 'duration_days']
    
    def get_status(self, obj):
        """Return exhibition status"""
        if obj.is_active:
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
            'id', 'name', 'number_of_positions', 'start_date', 'end_date',
            'rules', 'status', 'duration_days', 'position_count', 
            'assigned_positions', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'status', 'duration_days', 'position_count', 
            'assigned_positions', 'created_at', 'updated_at'
        ]
    
    def get_status(self, obj):
        if obj.is_active:
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
            action=PositionHistory.Action.ASSIGNED
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
            'id', 'name', 'number_of_positions', 'start_date', 'end_date',
            'rules', 'status', 'duration_days', 'position_stats', 
            'guard_stats', 'created_at', 'updated_at'
        ]
        read_only_fields = [
            'id', 'status', 'duration_days', 'position_stats', 
            'guard_stats', 'created_at', 'updated_at'
        ]
    
    def get_status(self, obj):
        if obj.is_active:
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
            action=PositionHistory.Action.ASSIGNED
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
            action=PositionHistory.Action.ASSIGNED
        ).values_list('guard_id', flat=True).distinct()
        
        return {
            'unique_guards_assigned': len(guard_ids),
            'total_assignments': PositionHistory.objects.filter(
                position__exhibition=obj,
                action=PositionHistory.Action.ASSIGNED
            ).count()
        }
