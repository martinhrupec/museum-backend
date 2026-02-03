"""
Management command to manually update guard priorities.

Usage:
    python manage.py update_guard_priorities
"""
from django.core.management.base import BaseCommand
from background_tasks.tasks import update_all_guard_priorities


class Command(BaseCommand):
    help = 'Manually update all guard priorities'

    def handle(self, *args, **options):
        self.stdout.write("Updating guard priorities...")
        
        try:
            result = update_all_guard_priorities()
            self.stdout.write(self.style.SUCCESS(f'✓ {result}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Error: {e}'))
            raise
