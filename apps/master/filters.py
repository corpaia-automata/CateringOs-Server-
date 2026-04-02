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
    # category is free-form text so support icontains in addition to exact
    category = django_filters.CharFilter(lookup_expr='icontains')

    class Meta:
        model = Dish
        fields = {
            'is_active':   ['exact'],
            'has_recipe':  ['exact'],   # allows ?has_recipe=true to filter menu-ready dishes
        }
