from rest_framework import serializers

from .calculation import format_quantity
from .models import EventIngredient


class EventIngredientSerializer(serializers.ModelSerializer):
    # Formatted at the display layer: sub-kg → grams, sub-litre → ml
    total_quantity = serializers.SerializerMethodField()
    unit           = serializers.SerializerMethodField()

    class Meta:
        model = EventIngredient
        fields = (
            'id', 'event', 'ingredient',
            'ingredient_name', 'category',
            'total_quantity', 'unit',
            'calculated_at',
        )
        read_only_fields = fields

    def get_total_quantity(self, obj):
        qty, _ = format_quantity(obj.total_quantity, obj.unit)
        return float(qty)

    def get_unit(self, obj):
        _, unit = format_quantity(obj.total_quantity, obj.unit)
        return unit
