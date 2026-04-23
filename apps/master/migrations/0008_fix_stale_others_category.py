from django.db import migrations


def fix_others_to_other(apps, schema_editor):
    """Rename any stale 'OTHERS' category values to the correct 'OTHER'."""
    Ingredient = apps.get_model('master', 'Ingredient')
    Ingredient.objects.filter(category='OTHERS').update(category='OTHER')


class Migration(migrations.Migration):

    dependencies = [
        ('master', '0007_ingredient_per_tenant_unique'),
    ]

    operations = [
        migrations.RunPython(fix_others_to_other, migrations.RunPython.noop),
    ]
