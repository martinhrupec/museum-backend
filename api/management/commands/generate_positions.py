from django.core.management.base import BaseCommand
from background_tasks.tasks import generate_weekly_positions


class Command(BaseCommand):
    help = 'Manually generate positions for next week'

    def handle(self, *args, **options):
        self.stdout.write('Generating positions for next week...')
        result = generate_weekly_positions()
        self.stdout.write(self.style.SUCCESS(result))
