import logging
from decimal import Decimal

from django.db import IntegrityError, transaction
from django.shortcuts import get_object_or_404
from rest_framework import serializers as drf_serializers
from rest_framework import status, viewsets
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

logger = logging.getLogger(__name__)

from shared.permissions import IsTenantScopedJWT

from .filters import DishFilter, IngredientFilter
from .models import Category, Dish, DishCategory, DishRecipe, Ingredient
from .serializers import (
    CategorySerializer,
    DishCategorySerializer,
    DishRecipeSerializer,
    DishSerializer,
    IngredientSerializer,
)


class CategoryListView(APIView):
    """Public endpoint — returns all active global categories, no auth required."""
    permission_classes = [AllowAny]

    def get(self, _request):
        qs = Category.objects.filter(is_active=True)
        return Response(CategorySerializer(qs, many=True).data)


class IngredientViewSet(viewsets.ModelViewSet):
    serializer_class = IngredientSerializer
    permission_classes = [IsAuthenticated, IsTenantScopedJWT]
    filterset_class = IngredientFilter
    search_fields = ['name']
    ordering_fields = ['name', 'category']

    def get_queryset(self):
        return Ingredient.objects.filter(tenant_id=self.request.tenant_id)

    def perform_create(self, serializer):
        # Explicitly check for duplicate before creating — no silent get_or_create.
        # The UniqueConstraint provides DB-level safety; this gives a clean 400.
        name = serializer.validated_data['name']
        if Ingredient.objects.filter(tenant_id=self.request.tenant_id, name=name).exists():
            from rest_framework import serializers as drf_serializers
            raise drf_serializers.ValidationError(
                {'name': f'An ingredient named "{name}" already exists in this workspace.'}
            )
        serializer.save(tenant_id=self.request.tenant_id)

    def perform_update(self, serializer):
        serializer.save()


class DishCategoryViewSet(viewsets.ModelViewSet):
    serializer_class = DishCategorySerializer
    permission_classes = [IsAuthenticated, IsTenantScopedJWT]
    pagination_class = None  # small master list — return plain array
    search_fields = ['name']
    ordering_fields = ['name', 'sort_order']

    def get_queryset(self):
        return DishCategory.objects.filter(tenant_id=self.request.tenant_id)

    def perform_create(self, serializer):
        serializer.save(tenant_id=self.request.tenant_id)


class DishViewSet(viewsets.ModelViewSet):
    serializer_class = DishSerializer
    permission_classes = [IsAuthenticated, IsTenantScopedJWT]
    filterset_class = DishFilter
    search_fields = ['name']
    ordering_fields = ['name', 'category__name']

    def get_queryset(self):
        return (
            Dish.objects
            .select_related('category')
            .prefetch_related('recipe_lines__ingredient')
            .filter(tenant_id=self.request.tenant_id)
        )

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        serializer.save(tenant_id=request.tenant_id)
        return Response(serializer.data, status=status.HTTP_201_CREATED)

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        partial = kwargs.pop('partial', False)
        instance = self.get_object()
        serializer = self.get_serializer(instance, data=request.data, partial=partial)
        serializer.is_valid(raise_exception=True)  # validation (including is_active check) runs HERE
        serializer.save()
        return Response(serializer.data)

    def partial_update(self, request, *args, **kwargs):
        kwargs['partial'] = True
        return self.update(request, *args, **kwargs)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)


class DishRecipeViewSet(viewsets.GenericViewSet):
    """
    Nested under dishes.
    GET /api/.../master/dishes/{dish_pk}/recipe/  → all recipe lines
    PUT /api/.../master/dishes/{dish_pk}/recipe/  → atomically replace all
    """
    serializer_class = DishRecipeSerializer
    permission_classes = [IsAuthenticated, IsTenantScopedJWT]
    # Required by GenericViewSet / filter & pagination backends
    queryset = DishRecipe.objects.none()

    def _get_tenant_dish(self, dish_pk):
        return get_object_or_404(Dish, pk=dish_pk, tenant_id=self.request.tenant_id)

    def list(self, request, dish_pk=None, **kwargs):
        try:
            dish = self._get_tenant_dish(dish_pk)
            qs = DishRecipe.objects.filter(
                dish=dish,
                ingredient__isnull=False   
            ).select_related('ingredient')
            if not qs.exists():
                return Response({
                    'exists': False,
                    'batch_size': str(dish.batch_size) if dish.batch_size is not None else None,
                    'batch_unit': dish.batch_unit,
                    'lines': [],
                })
            serializer = DishRecipeSerializer(qs, many=True)
            return Response({
                'exists': True,
                'batch_size': str(dish.batch_size) if dish.batch_size is not None else None,
                'batch_unit': dish.batch_unit,
                'lines': serializer.data,
            })
        except Exception as exc:
            import logging
            logging.getLogger(__name__).exception('Unexpected error in DishRecipeViewSet.list')
            return Response({'detail': 'Could not load recipe.', 'lines': []}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def replace_all(self, request, dish_pk=None, **kwargs):
        dish = self._get_tenant_dish(dish_pk)

        if isinstance(request.data, dict):
            lines_data     = request.data.get('lines', [])
            new_batch_size = request.data.get('batch_size', dish.batch_size)
            new_batch_unit = request.data.get('batch_unit', dish.batch_unit)
        else:
            lines_data     = request.data if isinstance(request.data, list) else []
            new_batch_size = dish.batch_size
            new_batch_unit = dish.batch_unit

        # Coerce batch_size to Decimal to avoid float → DecimalField coercion issues.
        try:
            new_batch_size = Decimal(str(new_batch_size)) if new_batch_size else Decimal('1')
        except Exception:
            new_batch_size = Decimal('1')

        # Reject duplicates explicitly — do not silently drop them.
        seen = set()
        for line in lines_data:
            ing_id = line.get('ingredient')
            if not ing_id:
                continue
            if ing_id in seen:
                from rest_framework import serializers as drf_serializers
                raise drf_serializers.ValidationError(
                    {'lines': f'Ingredient id {ing_id} appears more than once. Each ingredient can appear only once per recipe.'}
                )
            seen.add(ing_id)
            
        # 🔥 VALIDATE qty BEFORE serializer
        for line in lines_data:
            qty = line.get('qty_per_unit')

            try:
                if qty is None:
                    raise drf_serializers.ValidationError({'lines': 'Quantity is required'})

                qty_val = Decimal(str(qty))

                if qty_val <= 0:
                    raise drf_serializers.ValidationError(
                        {'lines': 'Quantity must be greater than 0'}
                    )

            except Exception:
                raise drf_serializers.ValidationError(
            {'lines': f'Invalid quantity: {qty}'}
        )

        # Validate all lines before touching the DB.
        serializer = DishRecipeSerializer(data=lines_data, many=True, context={'request': request})
        serializer.is_valid(raise_exception=True)

        try:
            with transaction.atomic():
                DishRecipe.all_objects.filter(dish=dish).delete()
                new_lines = []
                for item in serializer.validated_data:
                    item = dict(item)
                    # Validate ingredient is scoped to this tenant.
                    ing = item.get('ingredient')
                    if ing and str(ing.tenant_id) != str(request.tenant_id):
                        from rest_framework import serializers as drf_serializers
                        raise drf_serializers.ValidationError(
                            {'lines': f'Ingredient "{ing.name}" does not belong to this workspace.'}
                        )
                    new_lines.append(
                        DishRecipe(
                            dish=dish,
                            tenant_id=request.tenant_id,
                            # bulk_create skips save(), so snapshot must be set explicitly
                            unit_cost_snapshot=ing.unit_cost if ing else Decimal('0'),
                            **item,
                        )
                    )
                DishRecipe.objects.bulk_create(new_lines)
                Dish.objects.filter(pk=dish.pk).update(
                    has_recipe=bool(new_lines),
                    batch_size=new_batch_size,
                    batch_unit=new_batch_unit,
                )

            # Response serialization is now inside the try/except so any failure
            # here is logged and returns a clean 500 rather than an unhandled crash.
            dish.refresh_from_db()
            qs = DishRecipe.objects.filter(dish=dish).select_related('ingredient')
            lines = DishRecipeSerializer(qs, many=True).data
            return Response({
                'batch_size': str(dish.batch_size),
                'batch_unit': dish.batch_unit,
                'lines': lines,
            })

        except IntegrityError as exc:
            logger.error('IntegrityError in replace_all for dish %s: %s', dish_pk, exc)
            return Response(
                {'detail': 'Duplicate ingredient detected — each ingredient may appear only once per recipe.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            logger.exception('Unexpected error in replace_all for dish %s', dish_pk)
            return Response(
                {'detail': 'Failed to save recipe. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    def upload(self, request, dish_pk=None, **kwargs):
        """
        POST /dishes/{dish_pk}/recipe/upload/
        Accepts an .xlsx file. Parses ingredient_name / quantity / unit columns.
        Auto-creates any ingredient that doesn't exist yet (avoids blocking the
        upload flow). Replaces the dish's full recipe with the uploaded rows.
        """
        import openpyxl

        dish = self._get_tenant_dish(dish_pk)

        uploaded = request.FILES.get('file')
        if not uploaded:
            return Response({'detail': 'No file provided.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            wb = openpyxl.load_workbook(uploaded, data_only=True, read_only=True)
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
            wb.close()
        except Exception:
            return Response({'detail': 'Invalid or unreadable Excel file.'}, status=status.HTTP_400_BAD_REQUEST)

        if len(rows) < 2:
            return Response({'detail': 'File is empty or has no data rows.'}, status=status.HTTP_400_BAD_REQUEST)

        # Normalise header
        def _norm(v):
            return str(v or '').strip().lower().replace(' ', '_').replace('-', '_')

        header = [_norm(h) for h in rows[0]]

        def _col(*names):
            for n in names:
                if n in header:
                    return header.index(n)
            return None

        name_idx = _col('ingredient_name', 'name', 'ingredient')
        qty_idx  = _col('quantity', 'qty')
        unit_idx = _col('unit')

        if name_idx is None or qty_idx is None:
            return Response(
                {'detail': 'Missing required columns: ingredient_name, quantity.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        VALID_UOM = {'kg', 'g', 'litre', 'ml', 'piece', 'packet', 'box', 'dozen'}

        def _uom(raw):
            v = str(raw or '').strip().lower()
            alias = {'liter': 'litre', 'ltr': 'litre', 'pcs': 'piece', 'pieces': 'piece',
                     'nos': 'piece', 'no': 'piece', 'grams': 'g', 'gram': 'g',
                     'pack': 'packet', 'packets': 'packet', 'ml': 'ml',
                     'milliliter': 'ml', 'millilitre': 'ml'}
            v = alias.get(v, v)
            return v if v in VALID_UOM else 'kg'

        parsed = []
        seen_names: set[str] = set()
        for row in rows[1:]:
            raw_name = str(row[name_idx] or '').strip()
            if not raw_name:
                continue

            try:
                raw_qty = row[qty_idx]

                if raw_qty is None or str(raw_qty).strip() == '':
                    continue

                qty = Decimal(str(raw_qty))

                if qty <= 0:
                    continue

            except Exception:
                continue
            raw_unit = row[unit_idx] if unit_idx is not None else 'kg'
            # Deduplicate by name (case-insensitive) — last row wins
            key = raw_name.lower()
            if key in seen_names:
                # update existing entry
                for entry in parsed:
                    if entry['name'].lower() == key:
                        entry['qty'] = qty
                        entry['unit'] = _uom(raw_unit)
                        break
            else:
                seen_names.add(key)
                parsed.append({'name': raw_name, 'qty': qty, 'unit': _uom(raw_unit)})

        if not parsed:
            return Response({'detail': 'No valid rows found in file.'}, status=status.HTTP_400_BAD_REQUEST)

        try:
            with transaction.atomic():
                # Resolve or auto-create each ingredient
                resolved = []
                for item in parsed:
                    ingredient = (
                        Ingredient.objects
                        .filter(tenant_id=request.tenant_id, name__iexact=item['name'])
                        .first()
                    )
                    if ingredient is None:
                        try:
                            ingredient = Ingredient.objects.create(
                                tenant_id=request.tenant_id,
                                name=item['name'],
                                category=Ingredient.Category.OTHER,
                                unit_of_measure=item['unit'],
                                unit_cost=0,
                            )
                        except IntegrityError:
                            # Race condition — another request created it simultaneously
                            ingredient = Ingredient.objects.get(
                                tenant_id=request.tenant_id, name__iexact=item['name']
                            )
                    resolved.append({
                        'ingredient': ingredient,
                        'qty_per_unit': item['qty'],
                        'unit': item['unit'],
                    })

                # Replace recipe
                DishRecipe.all_objects.filter(dish=dish).delete()
                new_lines = [
                    DishRecipe(
                        dish=dish,
                        tenant_id=request.tenant_id,
                        ingredient=r['ingredient'],
                        qty_per_unit=r['qty_per_unit'],
                        unit=r['unit'],
                        unit_cost_snapshot=r['ingredient'].unit_cost,
                    )
                    for r in resolved
                ]
                DishRecipe.objects.bulk_create(new_lines)
                Dish.objects.filter(pk=dish.pk).update(has_recipe=bool(new_lines))

            dish.refresh_from_db()
            qs = DishRecipe.objects.filter(dish=dish).select_related('ingredient')
            lines = DishRecipeSerializer(qs, many=True).data
            return Response({
                'batch_size': str(dish.batch_size),
                'batch_unit': dish.batch_unit,
                'lines': lines,
            }, status=status.HTTP_200_OK)

        except IntegrityError as exc:
            logger.error('IntegrityError in upload for dish %s: %s', dish_pk, exc)
            return Response(
                {'detail': 'Duplicate ingredient detected in uploaded file.'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except Exception as exc:
            logger.exception('Unexpected error in upload for dish %s', dish_pk)
            return Response(
                {'detail': 'Failed to save uploaded recipe. Please try again.'},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )
