from django.db import migrations, models


def migrate_statuses(apps, schema_editor):
    Inquiry = apps.get_model('inquiries', 'Inquiry')
    # CONVERTED leads become QUALIFIED (still active pipeline leads)
    Inquiry.objects.filter(status='CONVERTED').update(status='QUALIFIED')
    # LOST leads become REJECTED
    Inquiry.objects.filter(status='LOST').update(status='REJECTED')


class Migration(migrations.Migration):

    dependencies = [
        ('inquiries', '0006_add_tenant_system'),
    ]

    operations = [
        # 1. Migrate existing data before removing choices/column
        migrations.RunPython(migrate_statuses, migrations.RunPython.noop),

        # 2. Update the status field choices (Django only stores choices as metadata)
        migrations.AlterField(
            model_name='inquiry',
            name='status',
            field=models.CharField(
                choices=[
                    ('NEW', 'New'),
                    ('QUALIFIED', 'Qualified'),
                    ('FOLLOW_UP', 'Follow Up'),
                    ('REJECTED', 'Rejected'),
                ],
                db_index=True,
                default='NEW',
                max_length=15,
            ),
        ),

        # 3. Drop the converted_event FK column
        migrations.RemoveField(
            model_name='inquiry',
            name='converted_event',
        ),
    ]
