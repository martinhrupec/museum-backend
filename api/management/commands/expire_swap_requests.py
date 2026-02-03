"""
Management command to manually expire swap requests.

Safe to run anytime - checks current time and expires requests
that are past their deadline (shift start time).

Usage:
    python manage.py expire_swap_requests
"""
from django.core.management.base import BaseCommand
from background_tasks.tasks import expire_swap_requests


class Command(BaseCommand):
    help = 'Expire swap requests that are past their deadline'

    def handle(self, *args, **options):
        self.stdout.write("Expiring swap requests...")
        
        try:
            result = expire_swap_requests()
            self.stdout.write(self.style.SUCCESS(f'✓ {result}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Error: {e}'))
            raise
