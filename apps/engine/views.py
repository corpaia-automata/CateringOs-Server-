import django_filters
from rest_framework import mixins, viewsets

from .models import EventIngredient
from .serializers import EventIngredientSerializer


class EventIngredientFilter(django_filters.FilterSet):
    class Meta:
        model = EventIngredient
        fields = {
            'event':    ['exact'],
            'category': ['exact'],
        }


class EventIngredientViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    viewsets.GenericViewSet,
):
    """
    Read-only. EventIngredient rows are written exclusively by CalculationEngine.
    Supports ?event=<uuid> and ?category=MEAT|GROCERY|… filtering.
    """
    serializer_class = EventIngredientSerializer
    filterset_class  = EventIngredientFilter
    search_fields    = ['ingredient_name']
    ordering_fields  = ['category', 'ingredient_name', 'total_quantity']
    ordering         = ['category', 'ingredient_name']

    def get_queryset(self):
        return (
            EventIngredient.objects
            .select_related('ingredient')
            .filter(total_quantity__gt=0)
        )
