from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.response import Response

from .filters import DishFilter, IngredientFilter
from .models import Dish, DishRecipe, Ingredient
from .serializers import DishRecipeSerializer, DishSerializer, IngredientSerializer


class IngredientViewSet(viewsets.ModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    filterset_class = IngredientFilter
    search_fields = ['name']
    ordering_fields = ['name', 'category']


class DishViewSet(viewsets.ModelViewSet):
    queryset = Dish.objects.prefetch_related('recipe_lines__ingredient').all()
    serializer_class = DishSerializer
    filterset_class = DishFilter
    search_fields = ['name', 'category']
    ordering_fields = ['name', 'category']

    def partial_update(self, request, *args, **kwargs):
        instance = self.get_object()
        # Prevent activating a dish that has no recipe lines
        if request.data.get('is_active') is True and not instance.has_recipe:
            return Response(
                {'detail': 'Cannot activate a dish that has no recipe lines.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        return super().partial_update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DishRecipeViewSet(viewsets.GenericViewSet):
    """
    Nested under dishes.
    GET  /api/master/dishes/{dish_pk}/recipe/  → all recipe lines for the dish
    PUT  /api/master/dishes/{dish_pk}/recipe/  → atomically replace all lines
    """
    serializer_class = DishRecipeSerializer

    def list(self, request, dish_pk=None):
        dish = get_object_or_404(Dish, pk=dish_pk)
        lines = DishRecipeSerializer(
            dish.recipe_lines.select_related('ingredient').all(), many=True
        ).data
        return Response({
            'batch_size': dish.batch_size,
            'batch_unit': dish.batch_unit,
            'lines': lines,
        })

    def replace_all(self, request, dish_pk=None):
        dish = get_object_or_404(Dish, pk=dish_pk)

        # Accept both new {batch_size, batch_unit, lines: [...]} and legacy [...] format
        if isinstance(request.data, dict):
            lines_data   = request.data.get('lines', [])
            new_batch_size = request.data.get('batch_size', dish.batch_size)
            new_batch_unit = request.data.get('batch_unit', dish.batch_unit)
        else:
            lines_data     = request.data if isinstance(request.data, list) else []
            new_batch_size = dish.batch_size
            new_batch_unit = dish.batch_unit

        # Deduplicate by ingredient before validation — keeps first occurrence,
        # silently drops repeated ingredient rows the frontend may send.
        seen_ingredients = set()
        deduplicated_lines = []
        for line in lines_data:
            ing_id = line.get('ingredient')
            if not ing_id:
                continue  # skip empty rows
            if ing_id not in seen_ingredients:
                seen_ingredients.add(ing_id)
                deduplicated_lines.append(line)

        serializer = DishRecipeSerializer(data=deduplicated_lines, many=True)
        serializer.is_valid(raise_exception=True)

        with transaction.atomic():
            # Use all_objects to bypass ActiveManager — hard-deletes stale soft-deleted
            # lines too, preventing unique_together IntegrityError on bulk_create.
            DishRecipe.all_objects.filter(dish=dish).delete()
            new_lines = [
                DishRecipe(dish=dish, **item)
                for item in serializer.validated_data
            ]
            DishRecipe.objects.bulk_create(new_lines)
            Dish.objects.filter(pk=dish.pk).update(
                has_recipe=bool(new_lines),
                batch_size=new_batch_size,
                batch_unit=new_batch_unit,
            )

        dish.refresh_from_db()
        lines = DishRecipeSerializer(
            dish.recipe_lines.select_related('ingredient').all(), many=True
        ).data
        return Response({
            'batch_size': dish.batch_size,
            'batch_unit': dish.batch_unit,
            'lines': lines,
        })
