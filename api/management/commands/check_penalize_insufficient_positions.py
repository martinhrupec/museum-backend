"""
Management command to manually check and penalize insufficient positions.

⚠️  WARNING: This checks guards who took fewer positions than minimum.
Normally scheduled to run on Sunday at 22:00 (end of week).

Safe to run manually for retroactive penalization.

Usage:
    python manage.py check_penalize_insufficient_positions
"""
from django.core.management.base import BaseCommand
from background_tasks.tasks import check_and_penalize_insufficient_positions


class Command(BaseCommand):
    help = 'Check and penalize guards with insufficient positions'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING(
            "⚠️  This penalizes guards who didn't meet minimum positions. "
            "Usually runs on Sunday at 22:00."
        ))
        self.stdout.write("Checking and penalizing insufficient positions...")
        
        try:
            result = check_and_penalize_insufficient_positions()
            self.stdout.write(self.style.SUCCESS(f'✓ {result}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Error: {e}'))
            raise
