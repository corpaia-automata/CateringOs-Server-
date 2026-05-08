from rest_framework import serializers

from .models import Event, EventLog
from .statuses import normalize_event_status


class EventSerializer(serializers.ModelSerializer):
    SYSTEM_MANAGED_FIELDS = {
        'total_amount',
        'advance_amount',
        'credited_amount',
        'extra_charges',
        'total_cost',
        'menu_snapshot',
        'services_snapshot',
        'costing_snapshot',
        'grocery_snapshot',
        'pricing_snapshot',
    }

    # Frontend uses client_name / event_name / event_id — map to model fields
    client_name = serializers.CharField(source='customer_name')
    event_name  = serializers.CharField(source='customer_name', read_only=True)
    event_id    = serializers.CharField(source='event_code', read_only=True)
    lead_id = serializers.UUIDField(source='inquiry_id', read_only=True)
    quotation_id = serializers.UUIDField(read_only=True)
    balance_amount = serializers.SerializerMethodField()
    internal_cost = serializers.SerializerMethodField()

    def get_balance_amount(self, obj):
        total = obj.total_amount or 0
        advance = obj.advance_amount or 0
        return total - advance

    def get_internal_cost(self, obj):
        return obj.total_cost or 0

    class Meta:
        model = Event
        fields = (
            'id', 'event_code', 'event_id',
            'lead_id', 'quotation_id',
            'customer_name', 'client_name', 'event_name',
            'contact_number',
            'event_type', 'event_date', 'event_time',
            'venue', 'guest_count',
            'service_type', 'service_type_narration',
            'status', 'payment_status',
            'total_amount', 'advance_amount', 'credited_amount', 'balance_amount',
            'extra_charges', 'total_cost', 'internal_cost',
            'menu_snapshot', 'services_snapshot', 'costing_snapshot', 'grocery_snapshot', 'pricing_snapshot',
            'menu_locked', 'notes',
            'created_at', 'updated_at',
        )
        read_only_fields = (
            'id', 'event_code', 'event_id', 'event_name',
            'customer_name',  # client_name is the writable alias
            'total_amount', 'advance_amount', 'credited_amount', 'balance_amount',
            'extra_charges', 'total_cost', 'internal_cost',
            'menu_snapshot', 'services_snapshot', 'costing_snapshot', 'grocery_snapshot', 'pricing_snapshot',
            'menu_locked', 'created_at', 'updated_at',
        )
        extra_kwargs = {
            'contact_number':         {'required': False, 'default': ''},
            'event_time':             {'required': False, 'allow_null': True},
            'event_date':             {'required': False, 'allow_null': True},
            'event_type':             {'required': False, 'default': ''},
            'venue':                  {'required': False, 'default': ''},
            'notes':                  {'required': False, 'default': ''},
            'service_type_narration': {'required': False, 'default': ''},
            'payment_status':         {'required': False, 'default': ''},
        }

    def validate_status(self, value):
        return normalize_event_status(value)

    def validate(self, attrs):
        attempted = self.SYSTEM_MANAGED_FIELDS.intersection(set(getattr(self, 'initial_data', {}) or {}))
        if attempted:
            fields = ', '.join(sorted(attempted))
            raise serializers.ValidationError({
                'detail': f'{fields} are managed by event execution endpoints.'
            })
        return attrs


class EventTransitionSerializer(serializers.Serializer):
    status = serializers.CharField()

    def validate_status(self, value):
        normalized = normalize_event_status(value)
        valid_statuses = {choice[0] for choice in Event.Status.choices}
        if normalized not in valid_statuses:
            raise serializers.ValidationError('Invalid status.')
        return normalized


class EventLogSerializer(serializers.ModelSerializer):
    action = serializers.CharField(source='action_type', read_only=True)
    user = serializers.SerializerMethodField()

    def get_user(self, obj):
        if not obj.user_id:
            return None
        return {
            'full_name': getattr(obj.user, 'full_name', '') or '',
            'email': getattr(obj.user, 'email', '') or '',
        }

    class Meta:
        model = EventLog
        fields = ('id', 'action', 'action_type', 'description', 'user', 'created_at')
