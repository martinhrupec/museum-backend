from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.auth.models import AbstractUser, UserManager
from django.db import models
from django.conf import settings


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
    # AbstractUser already provides: is_active, date_joined (use instead of created_at)
    
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
        
        super().save(*args, **kwargs)


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
        help_text="Availability score for scheduling"
    )
    
    # Many-to-many relationships through intermediate models
    positions_from_history = models.ManyToManyField(
        'Position',
        through='PositionHistory',
        related_name='guards_from_history'
    )
    available_positions = models.ManyToManyField(
        'Position',
        through='GuardAvailablePositions',
        related_name='available_guards'
    )
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
        Guard.objects.create(user=instance)
    
    # Add admin users to Museum Admin group for permissions
    elif instance.role == User.ROLE_ADMIN and not instance.is_superuser:
        from django.contrib.auth.models import Group
        try:
            museum_admin_group = Group.objects.get(name='Museum Admin')
            instance.groups.add(museum_admin_group)
        except Group.DoesNotExist:
            # Group doesn't exist yet - run: python manage.py create_default_groups
            pass
