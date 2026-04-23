from rest_framework import serializers

from .models import Quotation


class QuotationSerializer(serializers.ModelSerializer):
    version = serializers.IntegerField(source='version_number', read_only=True)

    # Snapshot fields sourced from the linked inquiry
    client_name = serializers.SerializerMethodField()
    event_type  = serializers.SerializerMethodField()
    event_date  = serializers.SerializerMethodField()
    event_code  = serializers.SerializerMethodField()

    def get_client_name(self, obj):
        return obj.inquiry.customer_name if obj.inquiry_id else None

    def get_event_type(self, obj):
        return obj.inquiry.event_type if obj.inquiry_id else None

    def get_event_date(self, obj):
        return obj.inquiry.tentative_date if obj.inquiry_id else None

    def get_event_code(self, obj):
        return None

    class Meta:
        model = Quotation
        fields = [
            'id', 'quote_number', 'inquiry', 'event_code',
            'client_name', 'event_type', 'event_date',
            'version', 'version_number', 'status',
            'line_items', 'manual_costs',
            'menu_dishes', 'menu_services',
            'subtotal', 'service_charge', 'total_amount',
            'final_selling_price', 'internal_cost', 'margin', 'advance_amount', 'payment_terms', 'is_locked',
            'notes',
            'sent_at', 'accepted_at', 'created_at', 'updated_at',
        ]
        read_only_fields = [
            'id', 'quote_number', 'event_code', 'client_name', 'event_type', 'event_date',
            'version', 'version_number', 'created_at', 'updated_at',
        ]
