from django.urls import include, path
from rest_framework.routers import DefaultRouter

from .views import InquiryViewSet, PreEstimateViewSet

router = DefaultRouter()
router.register(r'preestimates', PreEstimateViewSet, basename='preestimate')
router.register(r'', InquiryViewSet, basename='inquiry')

urlpatterns = [
    path('', include(router.urls)),
]
