"""
Management command to manually award daily completions.

⚠️  WARNING: This task processes completions for TODAY.
Normally scheduled to run daily at 23:00 (end of day).

Safe to run if you need to retroactively process missed completions.

Usage:
    python manage.py award_daily_completions
"""
from django.core.management.base import BaseCommand
from background_tasks.tasks import award_daily_completions


class Command(BaseCommand):
    help = 'Award points for daily position completions (processes yesterday)'

    def handle(self, *args, **options):
        self.stdout.write(self.style.WARNING(
            "⚠️  This processes completions for TODAY (by 23:00 all shifts have ended). "
            "Are you sure you want to continue?"
        ))
        self.stdout.write("Awarding daily completions...")
        
        try:
            result = award_daily_completions()
            self.stdout.write(self.style.SUCCESS(f'✓ {result}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Error: {e}'))
            raise
