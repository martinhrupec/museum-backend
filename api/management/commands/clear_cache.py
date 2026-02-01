"""
Management command to clear specific cache keys.

Usage:
    python manage.py clear_cache --all
    python manage.py clear_cache --key system_settings
    python manage.py clear_cache --pattern positions_*
"""

from django.core.management.base import BaseCommand
from django.core.cache import cache
from django_redis import get_redis_connection


class Command(BaseCommand):
    help = 'Clear Django cache keys'

    def add_arguments(self, parser):
        parser.add_argument(
            '--all',
            action='store_true',
            help='Clear all cache keys',
        )
        parser.add_argument(
            '--key',
            type=str,
            help='Clear specific cache key (e.g., system_settings)',
        )
        parser.add_argument(
            '--pattern',
            type=str,
            help='Clear keys matching pattern (e.g., positions_*)',
        )

    def handle(self, *args, **options):
        if options['all']:
            cache.clear()
            self.stdout.write(
                self.style.SUCCESS('✅ All cache cleared successfully')
            )
            return

        if options['key']:
            key = options['key']
            result = cache.delete(key)
            if result:
                self.stdout.write(
                    self.style.SUCCESS(f'✅ Cache key "{key}" deleted successfully')
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f'⚠️ Cache key "{key}" not found')
                )
            return

        if options['pattern']:
            pattern = options['pattern']
            try:
                redis_conn = get_redis_connection("default")
                
                # Get all keys matching pattern
                keys = redis_conn.keys(f'*{pattern}*')
                
                if keys:
                    deleted_count = redis_conn.delete(*keys)
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'✅ Deleted {deleted_count} cache keys matching "{pattern}"'
                        )
                    )
                else:
                    self.stdout.write(
                        self.style.WARNING(f'⚠️ No keys found matching "{pattern}"')
                    )
            except Exception as e:
                self.stdout.write(
                    self.style.ERROR(f'❌ Error: {str(e)}')
                )
            return

        self.stdout.write(
            self.style.ERROR('❌ Please specify --all, --key, or --pattern')
        )
