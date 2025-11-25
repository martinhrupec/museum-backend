"""
Django management command to create default user groups with permissions.

Run once after migrations: python manage.py create_default_groups
"""
from django.core.management.base import BaseCommand
from django.contrib.auth.models import Group, Permission
from django.contrib.contenttypes.models import ContentType


class Command(BaseCommand):
    help = 'Create default groups with permissions for museum staff'

    def handle(self, *args, **options):
        # Create Museum Admin group
        museum_admin_group, created = Group.objects.get_or_create(name='Museum Admin')
        
        if created or not museum_admin_group.permissions.exists():
            # Get all permissions for api models
            api_content_types = ContentType.objects.filter(app_label='api')
            all_permissions = Permission.objects.filter(content_type__in=api_content_types)
            
            # Grant all permissions except delete
            permissions_to_grant = all_permissions.exclude(codename__startswith='delete_')
            museum_admin_group.permissions.set(permissions_to_grant)
            
            self.stdout.write(
                self.style.SUCCESS(
                    f'✓ Created Museum Admin group with {permissions_to_grant.count()} permissions'
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING('Museum Admin group already exists with permissions')
            )
        
        self.stdout.write(
            self.style.SUCCESS(
                '\nDone! New admin users will automatically be added to this group.'
            )
        )
