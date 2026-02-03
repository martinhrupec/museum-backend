"""
Management command to manually validate preference templates.

Safe to run anytime - just validates current templates.

Usage:
    python manage.py validate_preference_templates
"""
from django.core.management.base import BaseCommand
from background_tasks.tasks import validate_preference_templates


class Command(BaseCommand):
    help = 'Validate guard preference templates'

    def handle(self, *args, **options):
        self.stdout.write("Validating preference templates...")
        
        try:
            result = validate_preference_templates()
            self.stdout.write(self.style.SUCCESS(f'✓ {result}'))
        except Exception as e:
            self.stdout.write(self.style.ERROR(f'✗ Error: {e}'))
            raise
