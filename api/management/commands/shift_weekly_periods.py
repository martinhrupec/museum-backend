"""
Management command to manually shift weekly periods.

Calls the Celery task directly for manual execution.
Useful for debugging, recovery, or initial setup.

Usage:
    python manage.py shift_weekly_periods
"""
from django.core.management.base import BaseCommand
from background_tasks.tasks import shift_weekly_periods


class Command(BaseCommand):
    help = 'Manually shift weekly periods (this_week → next_week)'

    def handle(self, *args, **options):
        self.stdout.write("Shifting weekly periods...")
        
        try:
            result = shift_weekly_periods()
            self.stdout.write(self.style.SUCCESS(f'✓ {result}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Error: {e}'))
            raise
