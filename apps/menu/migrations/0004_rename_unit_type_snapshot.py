"""
Migration 0004 — Rename unit_type_snapshot → serving_unit_snapshot

Aligns EventMenuItem with the unified serving_unit concept on Dish.
No data is lost — it is a column rename.
"""

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('menu', '0003_add_tenant_system'),
        ('master', '0009_master_schema_v2'),  # serving_unit exists on Dish before we rename snapshot
    ]

    operations = [
        migrations.RenameField(
            model_name='eventmenuitem',
            old_name='unit_type_snapshot',
            new_name='serving_unit_snapshot',
        ),
    ]
