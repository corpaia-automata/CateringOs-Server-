from django.urls import path, include
from rest_framework.routers import DefaultRouter

from .views import DashboardReportView, RevenueTrendView, TopDishesView

router = DefaultRouter()

urlpatterns = [
    path('', include(router.urls)),
    path('dashboard/', DashboardReportView.as_view(), name='reports-dashboard'),
    path('revenue-trend/', RevenueTrendView.as_view(), name='reports-revenue-trend'),
    path('top-dishes/', TopDishesView.as_view(), name='reports-top-dishes'),
]
