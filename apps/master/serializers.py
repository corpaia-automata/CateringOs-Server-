from decimal import Decimal

from rest_framework import serializers

from .models import Category, Dish, DishCategory, DishRecipe, Ingredient


class CategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = Category
        fields = ('id', 'name')


class IngredientSerializer(serializers.ModelSerializer):
    class Meta:
        model = Ingredient
        fields = (
            'id', 'name', 'category', 'unit_of_measure',
            'unit_cost', 'base_qty_ref', 'is_active',
            'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')

    def validate_unit_cost(self, value):
        if value < Decimal('0'):
            raise serializers.ValidationError('unit_cost must be 0 or greater.')
        return value


class DishCategorySerializer(serializers.ModelSerializer):
    class Meta:
        model = DishCategory
        fields = ('id', 'name', 'sort_order', 'created_at', 'updated_at')
        read_only_fields = ('id', 'created_at', 'updated_at')


VALID_RECIPE_UNITS = {'kg', 'g', 'litre', 'ml', 'piece', 'packet', 'box', 'dozen'}


class DishRecipeSerializer(serializers.ModelSerializer):
    ingredient_name    = serializers.CharField(source='ingredient.name', read_only=True, allow_null=True, default=None)
    ingredient_uom     = serializers.CharField(source='ingredient.unit_of_measure', read_only=True, allow_null=True, default=None)
    ingredient_category = serializers.CharField(source='ingredient.category', read_only=True, allow_null=True, default=None)

    class Meta:
        model = DishRecipe
        fields = (
            'id', 'ingredient', 'ingredient_name', 'ingredient_uom',
            'ingredient_category', 'qty_per_unit', 'unit', 'unit_cost_snapshot',
        )
        read_only_fields = ('id', 'ingredient_name', 'ingredient_uom', 'ingredient_category', 'unit_cost_snapshot')

    def get_fields(self):
        fields = super().get_fields()
        # Scope ingredient lookups to the requesting tenant when context is available.
        request = self.context.get('request')
        if request and hasattr(request, 'tenant_id'):
            fields['ingredient'].queryset = Ingredient.objects.filter(
                tenant_id=request.tenant_id
            )
        return fields

    def validate_qty_per_unit(self, value):
        if value <= Decimal('0'):
            raise serializers.ValidationError('qty_per_unit must be greater than zero.')
        return value

    def validate_unit(self, value):
        if not value:
            raise serializers.ValidationError('Unit is required')

        normalised = str(value).strip().lower()

        if normalised not in VALID_RECIPE_UNITS:
            raise serializers.ValidationError(
                f'"{value}" is not a valid unit. Allowed: {", ".join(sorted(VALID_RECIPE_UNITS))}.'
            )

        return normalised


class DishSerializer(serializers.ModelSerializer):
    name        = serializers.CharField(max_length=255)
    description = serializers.CharField(required=False, allow_blank=True, default='')
    image_url   = serializers.URLField(required=False, allow_blank=True, default='')
    labour_cost = serializers.DecimalField(
        max_digits=12, decimal_places=2, required=False, default=Decimal('0')
    )

    # Expose category as PK for writes, category_name as label for reads
    # allow_null + default=None handles dishes where category FK is still unset
    category_name = serializers.CharField(source='category.name', read_only=True, allow_null=True, default=None)

    # Computed from recipe lines × ingredient.unit_cost + labour_cost
    estimated_cost_per_serving = serializers.SerializerMethodField()

    recipe_lines = DishRecipeSerializer(many=True, read_only=True)

    class Meta:
        model = Dish
        fields = (
            'id',
            'name',
            'category',
            'category_name',
            'dish_type',
            'veg_non_veg',
            'description',
            'serving_unit',
            'base_price',
            'selling_price',
            'labour_cost',
            'image_url',
            'estimated_cost_per_serving',
            'is_active',
            'has_recipe',
            'notes',
            'batch_size',
            'batch_unit',
            'recipe_lines',
            'created_at',
            'updated_at',
        )
        read_only_fields = (
            'id', 'category_name', 'has_recipe', 'estimated_cost_per_serving',
            'recipe_lines', 'created_at', 'updated_at',
        )

    def validate_category(self, value):
        # Category is global (not tenant-scoped) — any active category is valid.
        return value

    def validate_name(self, value):
        request = self.context.get('request')
        tenant_id = getattr(request, 'tenant_id', None)
        qs = Dish.objects.filter(name=value, tenant_id=tenant_id)
        if self.instance:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise serializers.ValidationError('A dish with this name already exists.')
        return value

    def validate(self, attrs):
        """Cross-field validation: cannot activate a dish with no recipe."""
        is_active = attrs.get('is_active', getattr(self.instance, 'is_active', True))
        if is_active and self.instance and not self.instance.has_recipe:
            # Only block on explicit activation attempt
            if attrs.get('is_active') is True:
                raise serializers.ValidationError(
                    {'is_active': 'Cannot activate a dish that has no recipe lines.'}
                )
        return attrs

    def get_estimated_cost_per_serving(self, dish) -> str:
        # Return as string to preserve Decimal precision in JSON
        cost = dish.estimated_cost_per_serving
        if cost is None:
            return '0.00'
        return str(cost.quantize(Decimal('0.01')))

    def create(self, validated_data):
        return super().create(validated_data)

    def update(self, instance, validated_data):
        return super().update(instance, validated_data)
