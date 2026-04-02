from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from .models import Dish, DishRecipe, Ingredient


class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = (
            'id', 'name', 'category', 'unit_of_measure',
            'base_qty_ref', 'is_active', 'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')


class DishRecipeSerializer(serializers.ModelSerializer):
    ingredient_name = serializers.CharField(source='ingredient.name', read_only=True)
    ingredient_uom = serializers.CharField(source='ingredient.unit_of_measure', read_only=True)

    class Meta:
        model = DishRecipe
        fields = (
            'id', 'ingredient', 'ingredient_name', 'ingredient_uom',
            'qty_per_unit', 'unit',
        )
        read_only_fields = ('id', 'ingredient_name', 'ingredient_uom')


class DishSerializer(serializers.ModelSerializer):
    # Explicit validator: enforce uniqueness only among non-deleted dishes
    # (model no longer carries unique=True so DRF won't auto-generate this)
    name = serializers.CharField(
        max_length=255,
        validators=[UniqueValidator(
            queryset=Dish.objects.all(),
            message='A dish with this name already exists.',
        )],
    )
    recipe_lines = DishRecipeSerializer(many=True, read_only=True)

    class Meta:
        model = Dish
        fields = (
            'id', 'name', 'category', 'unit_type', 'is_active',
            'has_recipe', 'notes', 'batch_size', 'batch_unit',
            'recipe_lines', 'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'has_recipe', 'created_at', 'updated_at')
