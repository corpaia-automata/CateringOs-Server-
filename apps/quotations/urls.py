from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import QuotationItemView, QuotationViewSet

router = DefaultRouter()
router.register(r'', QuotationViewSet, basename='quotation')

urlpatterns = [
    path('quotation-items/', QuotationItemView.as_view(), name='quotation-items-create'),
    path('quotation-items/<str:item_id>/', QuotationItemView.as_view(), name='quotation-items-mutate'),
    path('', include(router.urls)),
]
