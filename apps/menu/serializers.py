from rest_framework import serializers

from .models import EventMenuItem


class EventMenuItemSerializer(serializers.ModelSerializer):
    class Meta:
        model = EventMenuItem
        fields = (
            'id',
            'event',
            'dish',
            'dish_name_snapshot',
            'serving_unit_snapshot',
            'quantity',
            'quantity_unit',          # writable; defaults to dish.serving_unit in model.save()
            'recipe_snapshot',
            'sort_order',
            'created_at',
            'updated_at',
        )
        read_only_fields = (
            'id',
            'event',                  # set from URL in perform_create
            'dish_name_snapshot',     # frozen in save()
            'serving_unit_snapshot',  # frozen in save()
            'recipe_snapshot',        # frozen in save()
            'created_at',
            'updated_at',
        )

    def validate_quantity(self, value):
        if value <= 0:
            raise serializers.ValidationError('Quantity must be greater than zero.')
        return value
