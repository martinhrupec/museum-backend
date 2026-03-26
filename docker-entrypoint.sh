#!/bin/bash
set -e

echo "Waiting for PostgreSQL..."
until PGPASSWORD=$DATABASE_PASSWORD psql -h "$DATABASE_HOST" -U "$DATABASE_USER" -d "$DATABASE_NAME" -c '\q'; do
  >&2 echo "Postgres is unavailable - sleeping"
  sleep 1
done

>&2 echo "PostgreSQL is up - executing migrations"

# Run migrations (only once, from web container)
if [ "$RUN_MIGRATIONS" = "true" ]; then
  echo "Running database migrations..."
  python manage.py migrate --noinput
  
  echo "Creating default groups..."
  python manage.py create_default_groups || echo "Groups already exist"
fi

# Execute the main container command
exec "$@"
