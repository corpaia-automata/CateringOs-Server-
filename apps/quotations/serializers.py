from rest_framework import serializers

from .models import Quotation


class QuotationSerializer(serializers.ModelSerializer):
    version = serializers.IntegerField(source='version_number', read_only=True)

    # Event snapshot fields for list display
    client_name = serializers.CharField(source='event.customer_name', read_only=True)
    event_type  = serializers.CharField(source='event.event_type',    read_only=True)
    event_date  = serializers.DateField(source='event.event_date',    read_only=True)
    event_code  = serializers.CharField(source='event.event_code',    read_only=True)

    class Meta:
        model = Quotation
        fields = [
            'id', 'quote_number', 'event', 'event_code',
            'client_name', 'event_type', 'event_date',
            'version', 'version_number', 'status',
            'line_items', 'manual_costs', 'subtotal', 'service_charge',
            'total_amount', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'quote_number', 'event_code', 'client_name', 'event_type', 'event_date',
            'version', 'version_number', 'created_at', 'updated_at',
        ]
