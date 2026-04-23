"""
Migration 0012 — Introduce global Category model; retarget Dish.category FK.

Why:
  DishCategory was tenant-scoped, so new tenants had zero categories and the
  dish-creation dropdown was always empty. Replacing it with a global Category
  table (no tenant FK) lets all tenants share a central list managed via admin.

What this migration does:
  1. Creates the global `categories` table.
  2. Seeds 7 default categories.
  3. NULLs out dish.category_id — existing values reference DishCategory UUIDs
     that do not exist in the new table and would violate the new FK constraint.
  4. Retargets Dish.category FK from dish_categories → categories.
"""

import uuid

import django.db.models.deletion
from django.db import migrations, models

DEFAULT_CATEGORIES = [
    ('Starter',     'starter',      0),
    ('Main Course', 'main-course',  1),
    ('Snacks',      'snacks',       2),
    ('Tea',         'tea',          3),
    ('Dessert',     'dessert',      4),
    ('Beverages',   'beverages',    5),
    ('Breads',      'breads',       6),
]


def seed_categories(apps, schema_editor):
    Category = apps.get_model('master', 'Category')
    for name, slug, sort_order in DEFAULT_CATEGORIES:
        Category.objects.create(
            id=uuid.uuid4(),
            name=name,
            slug=slug,
            is_active=True,
            sort_order=sort_order,
        )


class Migration(migrations.Migration):

    dependencies = [
        ('master', '0011_dish_category_text_alter_dish_unit_type'),
    ]

    operations = [
        # ── 1. Create global categories table ────────────────────────────────
        migrations.CreateModel(
            name='Category',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_deleted', models.BooleanField(default=False)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('name', models.CharField(max_length=100, unique=True)),
                ('slug', models.SlugField(max_length=100, unique=True)),
                ('is_active', models.BooleanField(default=True)),
                ('sort_order', models.PositiveIntegerField(default=0)),
            ],
            options={
                'db_table': 'categories',
                'ordering': ['sort_order', 'name'],
            },
        ),

        # ── 2. Seed default categories ────────────────────────────────────────
        migrations.RunPython(seed_categories, migrations.RunPython.noop),

        # ── 3. Clear stale category_id values (they pointed to DishCategory) ─
        migrations.RunSQL(
            'UPDATE dishes SET category_id = NULL',
            migrations.RunSQL.noop,
        ),

        # ── 4. Retarget Dish.category FK → global categories table ────────────
        migrations.AlterField(
            model_name='dish',
            name='category',
            field=models.ForeignKey(
                'master.Category',
                blank=True,
                db_column='category_id',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='dishes',
            ),
        ),
    ]
