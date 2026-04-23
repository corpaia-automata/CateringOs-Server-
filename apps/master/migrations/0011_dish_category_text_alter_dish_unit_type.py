"""
Migration 0011 — State-only sync for transitional Dish fields

The `category` (text) and `unit_type` columns already exist in the DB from
prior migrations. This migration updates Django's ORM state to expose them
under their new Python names (`category_text` and updated `unit_type`)
WITHOUT running any DDL — the columns are already there.

SeparateDatabaseAndState is used so Django's migration graph stays in sync
with models.py while we wait for migration 0012 to clean up the legacy columns.
"""

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('master', '0010_backfill_categories_and_serving_unit'),
    ]

    operations = [
        migrations.SeparateDatabaseAndState(
            # ORM state: tell Django models.py has category_text (db_column='category')
            # and unit_type with blank=True/default=''.
            state_operations=[
                migrations.AddField(
                    model_name='dish',
                    name='category_text',
                    field=models.CharField(blank=True, db_column='category', default='', max_length=100),
                ),
                migrations.AlterField(
                    model_name='dish',
                    name='unit_type',
                    field=models.CharField(blank=True, db_column='unit_type', default='', max_length=10),
                ),
            ],
            # DB: nothing to do — both columns already exist.
            database_operations=[],
        ),
    ]
