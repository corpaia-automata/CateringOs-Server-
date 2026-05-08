"""Remove stale migration history for the deleted ``quotation_builder`` app."""

from django.db import migrations


def drop_quotation_builder_migration_rows(apps, schema_editor):
    with schema_editor.connection.cursor() as cursor:
        cursor.execute('DELETE FROM django_migrations WHERE app = %s', ['quotation_builder'])


def noop(apps, schema_editor):
    pass


class Migration(migrations.Migration):

    dependencies = [
        ('quotations', '0021_builder_models_state_only'),
    ]

    operations = [
        migrations.RunPython(drop_quotation_builder_migration_rows, noop),
    ]
