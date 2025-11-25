from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .api_models import (
    User, Guard, Exhibition, Position, PositionHistory,
    GuardAvailablePositions, AdminNotification, Report, Point,
    SystemSettings
)


# Inline for displaying Guard info within User admin
class GuardInline(admin.StackedInline):
    model = Guard
    can_delete = False
    extra = 0
    fields = ('priority_number', 'availability')
    verbose_name = "Guard Profile"
    verbose_name_plural = "Guard Profile"


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    """Custom User admin with role field and full superuser access"""
    list_display = ['username', 'email', 'role', 'is_active', 'is_staff', 'is_superuser', 'date_joined', 'updated_at']
    list_filter = ['role', 'is_active', 'is_staff', 'is_superuser', 'date_joined']
    search_fields = ['username', 'email', 'first_name', 'last_name']
    date_hierarchy = 'date_joined'
    
    # Custom actions
    actions = ['mark_inactive', 'mark_active']
    
    # OVERRIDE: Show Guard inline only for guard users
    def get_inlines(self, request, obj=None):
        if obj and obj.role == User.ROLE_GUARD:
            return [GuardInline]
        return []
    
    def get_fieldsets(self, request, obj=None):
        """Superusers see ALL fields, staff see limited fields"""
        if not obj:
            # Adding new user - use add_fieldsets instead
            return self.add_fieldsets
        
        # Editing existing user
        if request.user.is_superuser:
            # Superuser sees everything
            return (
                (None, {'fields': ('username', 'password')}),
                ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
                ('Permissions', {
                    'fields': ('role', 'is_active', 'is_staff', 'is_superuser', 
                              'groups', 'user_permissions'),
                }),
                ('Important dates', {'fields': ('last_login', 'date_joined', 'updated_at')}),
            )
        else:
            # Staff users see limited fields
            return (
                (None, {'fields': ('username', 'password')}),
                ('Personal info', {'fields': ('first_name', 'last_name', 'email')}),
                ('Permissions', {'fields': ('role', 'is_active')}),
                ('Important dates', {'fields': ('last_login', 'date_joined')}),
            )
    
    # OVERRIDE: Dynamic fieldsets for adding new users based on permissions
    @property
    def add_fieldsets(self):
        """Can't make this dynamic with request, so use default"""
        return (
            (None, {
                'classes': ('wide',),
                'fields': ('username', 'password1', 'password2', 'role', 'email', 'is_staff'),
            }),
        )
    
    def get_actions(self, request):
        """Customize available actions based on user permissions"""
        actions = super().get_actions(request)
        
        # Remove default delete action for non-superusers
        if not request.user.is_superuser:
            if 'delete_selected' in actions:
                del actions['delete_selected']
        
        return actions
    
    def has_delete_permission(self, request, obj=None):
        """Only superusers can truly delete users"""
        return request.user.is_superuser
    
    def get_readonly_fields(self, request, obj=None):
        """Make certain fields readonly based on permissions"""
        if request.user.is_superuser:
            # Superuser can edit everything except these auto fields
            return ['last_login', 'date_joined', 'updated_at']
        else:
            # Staff users have many readonly fields
            return ['last_login', 'date_joined', 'updated_at', 'is_superuser', 
                   'is_staff', 'user_permissions', 'groups']
    
    @admin.action(description='Mark selected users as inactive')
    def mark_inactive(self, request, queryset):
        """Mark users as inactive (soft delete)"""
        updated = queryset.update(is_active=False)
        self.message_user(request, f'{updated} user(s) marked as inactive.')
    
    @admin.action(description='Mark selected users as active')
    def mark_active(self, request, queryset):
        """Mark users as active"""
        updated = queryset.update(is_active=True)
        self.message_user(request, f'{updated} user(s) marked as active.')


@admin.register(Guard)
class GuardAdmin(admin.ModelAdmin):
    list_display = ['user', 'priority_number', 'availability', 'get_is_active']
    list_filter = ['user__is_active']
    search_fields = ['user__username', 'user__email']
    raw_id_fields = ['user']
    
    # Custom actions
    actions = ['mark_guard_inactive', 'mark_guard_active']
    
    def get_is_active(self, obj):
        return obj.user.is_active
    get_is_active.boolean = True
    get_is_active.short_description = 'Active'
    
    def has_delete_permission(self, request, obj=None):
        """Only superusers can truly delete guards"""
        return request.user.is_superuser
    
    @admin.action(description='Mark selected guards as inactive')
    def mark_guard_inactive(self, request, queryset):
        """Mark guards' users as inactive"""
        user_ids = queryset.values_list('user_id', flat=True)
        updated = User.objects.filter(id__in=user_ids).update(is_active=False)
        self.message_user(request, f'{updated} guard(s) marked as inactive.')
    
    @admin.action(description='Mark selected guards as active')
    def mark_guard_active(self, request, queryset):
        """Mark guards' users as active"""
        user_ids = queryset.values_list('user_id', flat=True)
        updated = User.objects.filter(id__in=user_ids).update(is_active=True)
        self.message_user(request, f'{updated} guard(s) marked as active.')


@admin.register(Exhibition)
class ExhibitionAdmin(admin.ModelAdmin):
    list_display = ['name', 'start_date', 'end_date', 'get_status', 'position_count']
    list_filter = ['start_date', 'end_date']
    search_fields = ['name']
    date_hierarchy = 'start_date'
    
    # Custom actions
    actions = ['duplicate_exhibition']
    
    def position_count(self, obj):
        """Show number of positions for this exhibition"""
        return obj.positions.count()
    position_count.short_description = 'Positions'
    
    def get_status(self, obj):
        if obj.is_active:
            return '🟢 Active'
        elif obj.is_upcoming:
            return '🔵 Upcoming'
        else:
            return '⚫ Finished'
    get_status.short_description = 'Status'
    
    @admin.action(description='Duplicate selected exhibitions')
    def duplicate_exhibition(self, request, queryset):
        """Create duplicates of selected exhibitions (superuser only)"""
        if not request.user.is_superuser:
            self.message_user(request, 'Only superusers can duplicate exhibitions.', level='error')
            return
        
        for exhibition in queryset:
            exhibition.pk = None  # Create new instance
            exhibition.name = f"{exhibition.name} (Copy)"
            exhibition.save()
        
        self.message_user(request, f'{queryset.count()} exhibition(s) duplicated.')


@admin.register(Position)
class PositionAdmin(admin.ModelAdmin):
    list_display = ['exhibition', 'date', 'start_time', 'end_time']
    list_filter = ['exhibition', 'date']
    search_fields = ['exhibition__name']
    date_hierarchy = 'date'
    raw_id_fields = ['exhibition']


@admin.register(PositionHistory)
class PositionHistoryAdmin(admin.ModelAdmin):
    list_display = ['position', 'guard', 'action', 'action_time']
    list_filter = ['action', 'action_time']
    search_fields = ['guard__user__username', 'position__exhibition__name']
    date_hierarchy = 'action_time'
    raw_id_fields = ['position', 'guard']


@admin.register(GuardAvailablePositions)
class GuardAvailablePositionsAdmin(admin.ModelAdmin):
    list_display = ['guard', 'position', 'score']
    list_filter = ['score']
    search_fields = ['guard__user__username', 'position__exhibition__name']
    raw_id_fields = ['guard', 'position']


@admin.register(AdminNotification)
class AdminNotificationAdmin(admin.ModelAdmin):
    list_display = ['user', 'exhibition', 'message_preview', 'created_at']
    list_filter = ['created_at']
    search_fields = ['user__username', 'message', 'exhibition__name']
    date_hierarchy = 'created_at'
    raw_id_fields = ['user', 'exhibition']
    
    def message_preview(self, obj):
        return obj.message[:50]
    message_preview.short_description = 'Message'


@admin.register(Report)
class ReportAdmin(admin.ModelAdmin):
    list_display = ['guard', 'position', 'created_at', 'report_preview']
    list_filter = ['created_at']
    search_fields = ['guard__user__username', 'report_text']
    date_hierarchy = 'created_at'
    raw_id_fields = ['guard', 'position']
    
    def report_preview(self, obj):
        return obj.report_text[:50]
    report_preview.short_description = 'Report'


@admin.register(Point)
class PointAdmin(admin.ModelAdmin):
    list_display = ['guard', 'points', 'date_awarded', 'explanation_preview']
    list_filter = ['date_awarded']
    search_fields = ['guard__user__username', 'explanation']
    date_hierarchy = 'date_awarded'
    raw_id_fields = ['guard']
    
    def explanation_preview(self, obj):
        return obj.explanation[:50]
    explanation_preview.short_description = 'Explanation'


@admin.register(SystemSettings)
class SystemSettingsAdmin(admin.ModelAdmin):
    """
    Admin for system-wide settings.
    Only superusers can access this.
    """
    
    fieldsets = (
        ('Assignment Settings', {
            'fields': ('day_for_assignments', 'time_of_assignments'),
            'description': 'Configure when position assignments are published'
        }),
        ('Point System', {
            'fields': ('points_life_weeks',),
            'description': 'Configure how long points remain valid'
        }),
        ('Position Requirements', {
            'fields': ('minimal_number_of_positions_in_week',),
            'description': 'Configure minimum position requirements for guards'
        }),
    )
    
    def has_add_permission(self, request):
        """Prevent adding more than one settings instance"""
        return not SystemSettings.objects.exists()
    
    def has_delete_permission(self, request, obj=None):
        """Prevent deletion of settings"""
        return False
    
    def has_module_permission(self, request):
        """Only superusers can see this in admin"""
        return request.user.is_superuser

