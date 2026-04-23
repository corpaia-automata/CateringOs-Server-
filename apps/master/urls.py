from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import DishCategoryViewSet, DishRecipeViewSet, DishViewSet, IngredientViewSet

router = DefaultRouter()
router.register('ingredients', IngredientViewSet, basename='ingredient')
router.register('dish-categories', DishCategoryViewSet, basename='dish-category')
router.register('dishes', DishViewSet, basename='dish')

urlpatterns = [
    path('', include(router.urls)),
    # Nested recipe endpoints
    path(
        'dishes/<str:dish_pk>/recipe/',
        DishRecipeViewSet.as_view({'get': 'list', 'put': 'replace_all'}),
        name='dish-recipe',
    ),
    path(
        'dishes/<str:dish_pk>/recipe/upload/',
        DishRecipeViewSet.as_view({'post': 'upload'}),
        name='dish-recipe-upload',
    ),
]
