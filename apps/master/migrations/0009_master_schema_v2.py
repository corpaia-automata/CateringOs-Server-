"""
Migration 0009 — Master schema v2

Fixes the gap between models.py and the database.

What was missing from the DB (fields added to models.py without makemigrations):
  dishes: description, image_url, dish_type, veg_non_veg, base_price,
          selling_price, labour_cost

What is NEW from the audit refactor:
  dishes:      serving_unit, category_id (FK to dish_categories — nullable during backfill)
  ingredients: unit_cost
  dish_recipes: unit_cost_snapshot
  dish_categories: new table

SAFETY:
  - All new columns use safe defaults so existing rows get valid values.
  - category_id is nullable — will be backfilled in migration 0010,
    and made NOT NULL in migration 0011 after verification.
  - The old `category` text column and `unit_type` column are NOT dropped here.
    They are preserved in the DB so 0010 can read them during backfill.
    They will be dropped in migration 0011 once all data is migrated.
"""

import uuid
import django.db.models.deletion
from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('master', '0008_fix_stale_others_category'),
        ('tenants', '0001_add_tenant_system'),
    ]

    operations = [

        # ----------------------------------------------------------------
        # 1. Create DishCategory table
        # ----------------------------------------------------------------
        migrations.CreateModel(
            name='DishCategory',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_deleted', models.BooleanField(default=False)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('tenant', models.ForeignKey(
                    'tenants.Tenant',
                    db_column='tenant_id',
                    on_delete=django.db.models.deletion.PROTECT,
                    related_name='dish_categories',
                )),
                ('name', models.CharField(max_length=100)),
                ('sort_order', models.PositiveIntegerField(default=0)),
            ],
            options={
                'db_table': 'dish_categories',
                'ordering': ['sort_order', 'name'],
            },
        ),
        migrations.AddConstraint(
            model_name='dishcategory',
            constraint=models.UniqueConstraint(
                fields=['tenant', 'name'],
                name='unique_dish_category_per_tenant',
            ),
        ),

        # ----------------------------------------------------------------
        # 2. Add fields to Dish that were in models.py but never migrated
        # ----------------------------------------------------------------
        migrations.AddField(
            model_name='dish',
            name='description',
            field=models.TextField(blank=True, default=''),
        ),
        migrations.AddField(
            model_name='dish',
            name='image_url',
            field=models.URLField(blank=True, default='', max_length=500),
        ),
        migrations.AddField(
            model_name='dish',
            name='dish_type',
            field=models.CharField(
                choices=[('recipe', 'Recipe'), ('live_counter', 'Live Counter'), ('fixed_price', 'Fixed Price')],
                default='recipe',
                max_length=20,
            ),
        ),
        migrations.AddField(
            model_name='dish',
            name='veg_non_veg',
            field=models.CharField(
                choices=[('veg', 'Veg'), ('non_veg', 'Non-Veg')],
                default='veg',
                max_length=10,
            ),
        ),
        migrations.AddField(
            model_name='dish',
            name='base_price',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name='dish',
            name='selling_price',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name='dish',
            name='labour_cost',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),

        # ----------------------------------------------------------------
        # 3. New Dish fields from audit refactor
        # ----------------------------------------------------------------
        migrations.AddField(
            model_name='dish',
            name='serving_unit',
            field=models.CharField(
                choices=[
                    ('PLATE', 'Per Plate'), ('KG', 'Per KG'), ('PIECE', 'Per Piece'),
                    ('LITRE', 'Per Litre'), ('PORTION', 'Per Portion'),
                ],
                default='PLATE',
                max_length=10,
            ),
        ),
        # category FK — nullable during backfill period
        # db_column='category_id' is the default Django convention;
        # the old text column stays as 'category' (not touched here).
        migrations.AddField(
            model_name='dish',
            name='category',
            field=models.ForeignKey(
                'master.DishCategory',
                blank=True,
                db_column='category_id',
                null=True,
                on_delete=django.db.models.deletion.PROTECT,
                related_name='dishes',
            ),
        ),

        # ----------------------------------------------------------------
        # 4. Add unit_cost to Ingredient
        # ----------------------------------------------------------------
        migrations.AddField(
            model_name='ingredient',
            name='unit_cost',
            field=models.DecimalField(decimal_places=4, default=0, max_digits=12),
        ),

        # ----------------------------------------------------------------
        # 5. Add unit_cost_snapshot + extend UOM choices on Ingredient
        # ----------------------------------------------------------------
        migrations.AddField(
            model_name='dishrecipe',
            name='unit_cost_snapshot',
            field=models.DecimalField(decimal_places=4, default=0, max_digits=12),
        ),
        migrations.AlterField(
            model_name='ingredient',
            name='unit_of_measure',
            field=models.CharField(
                choices=[
                    ('kg', 'Kilogram'), ('g', 'Gram'), ('litre', 'Litre'),
                    ('ml', 'Millilitre'), ('piece', 'Piece'),
                    ('packet', 'Packet'), ('box', 'Box'), ('dozen', 'Dozen'),
                ],
                max_length=10,
            ),
        ),
    ]
