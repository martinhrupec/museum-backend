from django.core.management.base import BaseCommand
from background_tasks.tasks import penalize_insufficient_positions


class Command(BaseCommand):
    help = 'Penalize guards with insufficient positions. Use --week to target a specific week.'

    def add_arguments(self, parser):
        parser.add_argument(
            '--week',
            type=str,
            help='Week start date (YYYY-MM-DD). Defaults to current next_week_start.',
        )
        parser.add_argument(
            '--minimal',
            type=int,
            help='Minimum positions required. Defaults to SystemSettings value.',
        )

    def handle(self, *_, **options):
        week_arg = options.get('week')
        minimal_arg = options.get('minimal')

        if week_arg:
            from datetime import date, timedelta
            week_start = date.fromisoformat(week_arg)
            week_end = week_start + timedelta(days=6)
            self.stdout.write(f"Running penalty check for week {week_start} - {week_end}")
        else:
            week_start = None
            week_end = None
            self.stdout.write("Running penalty check for current next_week period")

        if minimal_arg is not None:
            self.stdout.write(f"Using minimal_positions override: {minimal_arg}")

        try:
            result = penalize_insufficient_positions(week_start=week_start, week_end=week_end, minimal_positions=minimal_arg)
            self.stdout.write(self.style.SUCCESS(f'✓ {result}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Error: {e}'))
            raise
