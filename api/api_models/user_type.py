from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.conf import settings
import structlog

logger = structlog.get_logger(__name__)


class ActiveUserManager(UserManager):
    """Manager that returns only active users"""
    def get_queryset(self):
        return super().get_queryset().filter(is_active=True)


class ActiveGuardManager(models.Manager):
    """Manager that returns only guards with active users"""
    def get_queryset(self):
        return super().get_queryset().filter(user__is_active=True)


class User(AbstractUser):
    """
    Custom User model with role-based permissions.
    
    Extends Django's AbstractUser to add role field (admin/guard)
    and automatic permission management based on role.
    """
    
    ROLE_ADMIN = "admin"
    ROLE_GUARD = "guard"
    ROLE_CHOICES = [
        (ROLE_ADMIN, "Admin"),
        (ROLE_GUARD, "Guard"),
    ]

    role = models.CharField(
        max_length=20,
        choices=ROLE_CHOICES,
        default=ROLE_GUARD,
    )
    updated_at = models.DateTimeField(auto_now=True)
    last_mobile_login = models.DateTimeField(
        null=True,
        blank=True,
        verbose_name='last mobile login',
        help_text="Last login via mobile app (JWT authentication)"
    )
    # AbstractUser already provides: is_active, date_joined (use instead of created_at)
    # Note: AbstractUser's last_login tracks web/session login
    
    # Don't override 'objects' - AbstractUser provides the correct UserManager
    # active_users is a secondary manager for convenience
    active_users = ActiveUserManager()

    class Meta(AbstractUser.Meta):
        swappable = "AUTH_USER_MODEL"
    
    def save(self, *args, **kwargs):
        """
        OVERRIDE: Enforce role-based permissions before saving
        
        Business rules:
        1. Superusers are always ROLE_ADMIN with is_staff=True
        2. ROLE_ADMIN users must have is_staff=True (access to Django admin)
        3. ROLE_GUARD users must have is_staff=False (no admin access)
        
        This ensures clean separation between business roles and Django permissions.
        """
        # Rule 1: Superusers are always admins
        if self.is_superuser:
            self.role = self.ROLE_ADMIN
            self.is_staff = True
        
        # Rule 2: Business role drives Django permissions
        elif self.role == self.ROLE_ADMIN:
            self.is_staff = True  # Admins need Django admin access
        
        elif self.role == self.ROLE_GUARD:
            self.is_staff = False  # Guards don't need Django admin
        
        # Rule 3: Prevent inconsistent states
        # If someone tries to manually set is_staff opposite to role, fix it
        if not self.is_superuser:
            if self.role == self.ROLE_ADMIN and not self.is_staff:
                self.is_staff = True  # Force consistency
            elif self.role == self.ROLE_GUARD and self.is_staff:
                self.is_staff = False  # Force consistency
        
        # Track role changes for logging
        is_new = not self.pk
        old_role = None
        if not is_new:
            try:
                old_instance = User.objects.get(pk=self.pk)
                old_role = old_instance.role
            except User.DoesNotExist:
                pass
        
        super().save(*args, **kwargs)
        
        # Log role changes (after save to ensure pk exists)
        if not is_new and old_role and old_role != self.role:
            logger.info(
                "user_role_changed",
                user_id=self.id,
                username=self.username,
                old_role=old_role,
                new_role=self.role,
                is_staff=self.is_staff
            )


class Guard(models.Model):
    """
    Guard profile for users with ROLE_GUARD.
    
    Automatically created via signal when a guard user is created.
    Tracks guard-specific data like priority and availability.
    """
    
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='guard'
    )
    priority_number = models.DecimalField(
        max_digits=5, 
        decimal_places=2,
        null=True,
        blank=True,
        help_text="Priority ranking for assignment algorithm"
    )
    availability = models.IntegerField(
        null=True, 
        blank=True,
        help_text="Number of shifts guard is available for next week"
    )
    availability_updated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Last time availability was updated"
    )
    
    # Many-to-many relationships through intermediate models
    positions_from_history = models.ManyToManyField(
        'Position',
        through='PositionHistory',
        related_name='guards_from_history'
    )
    # NOTE: available_positions removed - replaced with GuardWorkPeriod system
    # Guards now select time periods (day + shift), positions calculated dynamically
    positions_from_reports = models.ManyToManyField(
        'Position',
        through='Report',
        related_name='guards_from_reports'
    )
    
    objects = models.Manager()
    active_guards = ActiveGuardManager()
    
    def __str__(self):
        return f"Guard: {self.user.username}"


# SIGNAL: Auto-create Guard profile for guard users
@receiver(post_save, sender=User)
def create_guard_profile(sender, instance, created, **kwargs):
    """
    Signal receiver that auto-creates Guard profile when a guard user is created
    and adds admin users to the Museum Admin group for permissions.
    
    Only triggers for newly created users.
    """
    if not created:
        return
    
    # Create Guard profile for guard users
    if instance.role == User.ROLE_GUARD:
        guard = Guard.objects.create(user=instance)
        
        logger.info(
            "guard_profile_created",
            user_id=instance.id,
            username=instance.username,
            guard_id=guard.id
        )
        
        # Assign initial priority based on average of existing guards
        from background_tasks.tasks import assign_initial_priority_to_new_guard
        assign_initial_priority_to_new_guard(guard)
    
    # Add admin users to Museum Admin group for permissions
    elif instance.role == User.ROLE_ADMIN and not instance.is_superuser:
        from django.contrib.auth.models import Group
        try:
            museum_admin_group = Group.objects.get(name='Museum Admin')
            instance.groups.add(museum_admin_group)
        except Group.DoesNotExist:
            # Group doesn't exist yet - run: python manage.py create_default_groups
            pass
