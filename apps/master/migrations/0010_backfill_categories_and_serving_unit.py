"""
Migration 0010 — Data backfill

After migration 0009 added the new columns, this migration:
1. Reads the OLD free-text `category` column (still present in DB as raw text)
   via raw SQL — the ORM field `category` now points to the FK column `category_id`,
   so we must bypass the ORM to access the original text data.
2. Creates DishCategory rows per (tenant, category_text).
3. Updates dish.category_id to point at the matching DishCategory.
4. Backfills dish.serving_unit from dish.unit_type.

Migration 0011 will then make category_id NOT NULL and drop the legacy columns.
"""

import uuid
from decimal import Decimal
from django.db import migrations
from django.utils import timezone


# Serving unit mapping (unit_type values → serving_unit choices — identical values)
UNIT_TYPE_MAP = {
    'PLATE':   'PLATE',
    'KG':      'KG',
    'PIECE':   'PIECE',
    'LITRE':   'LITRE',
    'PORTION': 'PORTION',
}


def forward(apps, schema_editor):
    db = schema_editor.connection
    DishCategory = apps.get_model('master', 'DishCategory')
    now = timezone.now()

    # --- 1. Read distinct (tenant_id, category_text) via raw SQL ---
    # The `category` TEXT column still exists in the DB even though the
    # migration state's ORM `category` field now refers to the FK (category_id).
    with db.cursor() as cursor:
        cursor.execute("""
            SELECT DISTINCT tenant_id, category
            FROM dishes
            WHERE category IS NOT NULL AND category != ''
        """)
        pairs = cursor.fetchall()

    # --- 2. Create DishCategory rows ---
    category_map = {}  # (str(tenant_id), name_lower) → DishCategory pk (uuid str)

    for tenant_id, raw_name in pairs:
        name = (raw_name or '').strip()
        if not name:
            continue
        key = (str(tenant_id), name.lower())
        if key in category_map:
            continue
        obj, _ = DishCategory.objects.get_or_create(
            tenant_id=tenant_id,
            name=name,
            defaults={'sort_order': 0},
        )
        category_map[key] = str(obj.pk)

    # --- 3. Update dish.category_id from the old category text ---
    with db.cursor() as cursor:
        cursor.execute("SELECT id, tenant_id, category, unit_type FROM dishes")
        rows = cursor.fetchall()

    updates_category = []
    updates_serving  = []

    for dish_id, tenant_id, raw_category, raw_unit_type in rows:
        name = (raw_category or '').strip()
        key  = (str(tenant_id), name.lower())
        cat_pk = category_map.get(key)

        if cat_pk:
            updates_category.append((cat_pk, str(dish_id)))

        serving = UNIT_TYPE_MAP.get((raw_unit_type or '').upper(), 'PLATE')
        updates_serving.append((serving, str(dish_id)))

    # Batch UPDATE category_id
    if updates_category:
        with db.cursor() as cursor:
            cursor.executemany(
                "UPDATE dishes SET category_id = %s WHERE id = %s",
                updates_category,
            )

    # Batch UPDATE serving_unit
    if updates_serving:
        with db.cursor() as cursor:
            cursor.executemany(
                "UPDATE dishes SET serving_unit = %s WHERE id = %s",
                updates_serving,
            )


def backward(apps, schema_editor):
    db = schema_editor.connection
    with db.cursor() as cursor:
        cursor.execute("UPDATE dishes SET category_id = NULL, serving_unit = 'PLATE'")


class Migration(migrations.Migration):

    dependencies = [
        ('master', '0009_master_schema_v2'),
    ]

    operations = [
        migrations.RunPython(forward, backward),
    ]
