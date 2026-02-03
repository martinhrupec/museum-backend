"""
Management command to manually run automated assignment algorithm.

⚠️  WARNING: This runs assignment WITHOUT time checks!
Normally scheduled for Wednesday at configured time (default 20:00).

Only use this if:
- Scheduled task failed
- Testing/debugging
- Manual trigger needed

Usage:
    python manage.py run_automated_assignment
"""
from django.core.management.base import BaseCommand
from background_tasks.tasks import run_automated_assignment


class Command(BaseCommand):
    help = 'Manually run automated position assignment algorithm'

    def add_arguments(self, parser):
        parser.add_argument(
            '--force',
            action='store_true',
            help='Skip confirmation prompt',
        )

    def handle(self, *args, **options):
        if not options['force']:
            self.stdout.write(self.style.WARNING(
                "\n⚠️  WARNING: This runs automated assignment WITHOUT time checks!\n"
                "This will:\n"
                "  - Assign positions to guards based on current availability\n"
                "  - Calculate and set minimum positions\n"
                "  - Send notifications\n\n"
                "Normally this runs on Wednesday at configured time.\n"
                "Are you sure you want to continue? (yes/no): "
            ))
            
            # In non-interactive mode, require --force
            try:
                confirm = input().strip().lower()
                if confirm not in ['yes', 'y']:
                    self.stdout.write(self.style.ERROR('Aborted.'))
                    return
            except (EOFError, KeyboardInterrupt):
                self.stdout.write(self.style.ERROR('\nAborted.'))
                return
        
        self.stdout.write("Running automated assignment algorithm...")
        
        try:
            result = run_automated_assignment()
            self.stdout.write(self.style.SUCCESS(f'\n✓ {result}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Error: {e}'))
            raise
