from django.db import transaction
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from shared.permissions import IsTenantScopedJWT

from .filters import DishFilter, IngredientFilter
from .models import Dish, DishRecipe, Ingredient
from .serializers import DishRecipeSerializer, DishSerializer, IngredientSerializer


class IngredientViewSet(viewsets.ModelViewSet):
    serializer_class = IngredientSerializer
    permission_classes = [IsAuthenticated, IsTenantScopedJWT]
    filterset_class = IngredientFilter
    search_fields = ['name']
    ordering_fields = ['name', 'category']

    def get_queryset(self):
        return Ingredient.objects.filter(tenant_id=self.request.tenant_id)

    def perform_create(self, serializer):
        serializer.save(tenant_id=self.request.tenant_id)


class DishViewSet(viewsets.ModelViewSet):
    serializer_class = DishSerializer
    permission_classes = [IsAuthenticated, IsTenantScopedJWT]
    filterset_class = DishFilter
    search_fields = ['name', 'category']
    ordering_fields = ['name', 'category']

    def get_queryset(self):
        return Dish.objects.prefetch_related('recipe_lines__ingredient').filter(
            tenant_id=self.request.tenant_id
        )

    def perform_create(self, serializer):
        serializer.save(tenant_id=self.request.tenant_id)

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
    GET  /api/app/<slug>/master/dishes/{dish_pk}/recipe/  → all recipe lines
    PUT  /api/app/<slug>/master/dishes/{dish_pk}/recipe/  → atomically replace all
    """
    serializer_class = DishRecipeSerializer
    permission_classes = [IsAuthenticated, IsTenantScopedJWT]

    def _get_tenant_dish(self, dish_pk):
        """Fetch the dish, scoped to the current tenant (raises 404 on cross-tenant)."""
        return get_object_or_404(Dish, pk=dish_pk, tenant_id=self.request.tenant_id)

    def list(self, request, dish_pk=None):
        dish = self._get_tenant_dish(dish_pk)
        lines = DishRecipeSerializer(
            dish.recipe_lines.select_related('ingredient').all(), many=True
        ).data
        return Response({
            'batch_size': dish.batch_size,
            'batch_unit': dish.batch_unit,
            'lines': lines,
        })

    def replace_all(self, request, dish_pk=None):
        dish = self._get_tenant_dish(dish_pk)

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
                DishRecipe(dish=dish, tenant_id=request.tenant_id, **item)
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
