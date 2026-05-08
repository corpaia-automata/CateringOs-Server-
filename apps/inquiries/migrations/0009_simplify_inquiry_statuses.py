from django.db import migrations, models


def migrate_statuses_forward(apps, schema_editor):
    Inquiry = apps.get_model('inquiries', 'Inquiry')

    Inquiry.objects.filter(status='REJECTED').update(status='LOST')
    Inquiry.objects.filter(status='CONFIRMED').update(status='SUCCESS')
    Inquiry.objects.filter(
        status__in=['NEW', 'QUALIFIED', 'FOLLOW_UP', 'QUOTED']
    ).update(status='PLANNING')


def migrate_statuses_backward(apps, schema_editor):
    Inquiry = apps.get_model('inquiries', 'Inquiry')

    Inquiry.objects.filter(status='LOST').update(status='REJECTED')
    Inquiry.objects.filter(status='SUCCESS').update(status='CONFIRMED')
    Inquiry.objects.filter(status='PLANNING').update(status='NEW')


class Migration(migrations.Migration):

    dependencies = [
        ('inquiries', '0008_inquiry_converted_at_inquiry_converted_event_and_more'),
    ]

    operations = [
        migrations.RunPython(migrate_statuses_forward, migrate_statuses_backward),
        migrations.AlterField(
            model_name='inquiry',
            name='status',
            field=models.CharField(
                choices=[
                    ('PLANNING', 'Planning'),
                    ('SUCCESS', 'Success'),
                    ('LOST', 'Lost'),
                ],
                db_index=True,
                default='PLANNING',
                max_length=15,
            ),
        ),
    ]
