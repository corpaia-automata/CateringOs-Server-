import django_filters

from .models import Dish, Ingredient


class IngredientFilter(django_filters.FilterSet):
    class Meta:
        model = Ingredient
        fields = {
            'category': ['exact'],
            'is_active': ['exact'],
        }


class DishFilter(django_filters.FilterSet):
    # Filter by category name (case-insensitive) or by category PK
    category_name = django_filters.CharFilter(field_name='category__name', lookup_expr='icontains')
    category = django_filters.UUIDFilter(field_name='category__id')

    class Meta:
        model = Dish
        fields = {
            'is_active':    ['exact'],
            'has_recipe':   ['exact'],
            'veg_non_veg':  ['exact'],
            'dish_type':    ['exact'],
            'serving_unit': ['exact'],
        }
