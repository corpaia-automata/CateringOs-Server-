from rest_framework import serializers

from .models import Quotation


class QuotationSerializer(serializers.ModelSerializer):
    # Expose version_number as "version" for frontend compatibility
    version = serializers.IntegerField(source='version_number', read_only=True)

    class Meta:
        model = Quotation
        fields = [
            'id', 'event', 'version', 'version_number', 'status',
            'line_items', 'manual_costs', 'subtotal', 'service_charge',
            'total_amount', 'notes', 'created_at', 'updated_at',
        ]
        read_only_fields = ['id', 'version', 'version_number', 'created_at', 'updated_at']
