from django.urls import path

from apps.authentication.views import TenantLoginView
from .views import TenantConfigView

urlpatterns = [
    # POST /api/app/<slug>/auth/login/
    path('auth/login/', TenantLoginView.as_view(), name='tenant-login'),

    # GET/PATCH /api/app/<slug>/config/
    path('config/', TenantConfigView.as_view(), name='tenant-config'),
]
