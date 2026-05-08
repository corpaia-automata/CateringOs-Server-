from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    dependencies = [
        ('events', '0008_alter_event_managers'),
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.AddField(
            model_name='event',
            name='extra_charges',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.AddField(
            model_name='event',
            name='total_cost',
            field=models.DecimalField(decimal_places=2, default=0, max_digits=12),
        ),
        migrations.CreateModel(
            name='EventLog',
            fields=[
                ('id', models.UUIDField(default=uuid.uuid4, editable=False, primary_key=True, serialize=False)),
                ('created_at', models.DateTimeField(auto_now_add=True)),
                ('updated_at', models.DateTimeField(auto_now=True)),
                ('is_deleted', models.BooleanField(default=False)),
                ('deleted_at', models.DateTimeField(blank=True, null=True)),
                ('action_type', models.CharField(choices=[('ADD_DISH', 'Add Dish'), ('UPDATE_DISH', 'Update Dish'), ('REMOVE_DISH', 'Remove Dish'), ('UPDATE_QTY', 'Update Quantity'), ('ADD_SERVICE', 'Add Service'), ('UPDATE_SERVICE', 'Update Service'), ('REMOVE_SERVICE', 'Remove Service'), ('COST_CHANGE', 'Cost Change'), ('PRICE_CHANGE', 'Price Change'), ('EXTRA_CHARGE', 'Extra Charge')], max_length=30)),
                ('description', models.TextField(blank=True)),
                ('event', models.ForeignKey(db_column='event_id', on_delete=django.db.models.deletion.CASCADE, related_name='logs', to='events.event')),
                ('user', models.ForeignKey(blank=True, db_column='user_id', null=True, on_delete=django.db.models.deletion.SET_NULL, related_name='event_logs', to=settings.AUTH_USER_MODEL)),
            ],
            options={
                'db_table': 'event_logs',
                'ordering': ['-created_at'],
                'indexes': [
                    models.Index(fields=['event', 'created_at'], name='event_logs_event_i_9ed267_idx'),
                    models.Index(fields=['action_type'], name='event_logs_action__476d94_idx'),
                ],
            },
        ),
    ]
