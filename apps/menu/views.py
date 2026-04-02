from django.core.exceptions import ValidationError
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError as DRFValidationError
from rest_framework.response import Response

from apps.engine.models import EventIngredient

from .models import EventMenuItem
from .serializers import EventMenuItemSerializer
from .services import MenuService


class EventMenuItemViewSet(viewsets.ModelViewSet):
    """
    Nested under /api/events/{event_pk}/menu-items/.
    All mutations go through MenuService to enforce business rules.
    """
    serializer_class = EventMenuItemSerializer

    def get_queryset(self):
        return (
            EventMenuItem.objects
            .filter(event_id=self.kwargs['event_pk'])
            .select_related('dish')
        )

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        try:
            instance = MenuService.add_dish(
                event_id=self.kwargs['event_pk'],
                validated_data=serializer.validated_data,
            )
        except ValidationError as exc:
            raise DRFValidationError(exc.message)
        return Response(
            EventMenuItemSerializer(instance).data,
            status=status.HTTP_201_CREATED,
        )

    def perform_destroy(self, instance):
        MenuService.remove_dish(instance)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=False, methods=['get'], url_path='ingredients')
    def ingredients(self, request, event_pk=None):
        """
        GET /api/events/{event_pk}/menu-items/ingredients/?categories=MEAT,GROCERY
        Returns calculated EventIngredient rows for this event, optionally
        filtered by one or more comma-separated category values.

        Response envelope:
        {
            "ingredients": [{ingredient_id, ingredient_name, category, total_quantity, unit}],
            "calculated_at": "<iso-datetime of latest calculation>",
            "total_items": <int>
        }
        """
        queryset = (
            EventIngredient.objects
            .filter(event_id=event_pk)
            .select_related('ingredient')
            .order_by('category', 'ingredient_name')
        )

        categories_param = request.query_params.get('categories', '').strip()
        if categories_param:
            category_list = [c.strip() for c in categories_param.split(',') if c.strip()]
            queryset = queryset.filter(category__in=category_list)

        rows = list(queryset)
        calculated_at = rows[-1].calculated_at.isoformat() if rows else None
        ingredients = [
            {
                'ingredient_id':   str(row.ingredient_id),
                'ingredient_name': row.ingredient_name,
                'category':        row.category,
                'total_quantity':  row.total_quantity,
                'unit':            row.unit,
            }
            for row in rows
        ]
        return Response({
            'ingredients':   ingredients,
            'calculated_at': calculated_at,
            'total_items':   len(ingredients),
        })
