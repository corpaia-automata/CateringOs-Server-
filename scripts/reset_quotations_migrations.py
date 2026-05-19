"""One-off: point django_migrations at squashed quotations.0001_initial (tables already exist)."""

import os
import sys

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

import django

os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings.development')
django.setup()

from django.db import connection
from django.utils import timezone

with connection.cursor() as cursor:
    cursor.execute("DELETE FROM django_migrations WHERE app = %s", ['quotations'])
    deleted = cursor.rowcount
    cursor.execute(
        """
        INSERT INTO django_migrations (app, name, applied)
        VALUES (%s, %s, %s)
        """,
        ['quotations', '0001_initial', timezone.now()],
    )

print(f'Removed {deleted} old quotations migration record(s).')
print('Recorded quotations.0001_initial as applied (squashed; tables unchanged).')
print('Run: python manage.py showmigrations quotations')
print('Run: python manage.py migrate  (should report no changes)')
