from django.contrib import admin
from django.urls import path, include

from apps.tenants.views import OnboardView

urlpatterns = [
    path('admin/', admin.site.urls),

    # Public onboarding (no auth, no tenant context)
    path('api/onboard/', OnboardView.as_view(), name='onboard'),

    # Global auth (non-tenant-scoped)
    path('api/auth/', include('apps.authentication.urls')),

    # ── Tenant-scoped routes ──────────────────────────────────────────────────
    # TenantResolverMiddleware resolves slug → sets request.tenant* + RLS.
    # Every route below requires a valid JWT whose tenant_id matches the slug.
    path('api/app/<slug:slug>/', include('apps.tenants.urls')),
    path('api/app/<slug:slug>/events/', include('apps.events.urls')),
    path('api/app/<slug:slug>/inquiries/', include('apps.inquiries.urls')),
    path('api/app/<slug:slug>/master/', include('apps.master.urls')),
    path('api/app/<slug:slug>/engine/', include('apps.engine.urls')),
    path('api/app/<slug:slug>/grocery/', include('apps.grocery.urls')),
    path('api/app/<slug:slug>/quotations/', include('apps.quotations.urls')),
    path('api/app/<slug:slug>/reports/', include('apps.reports.urls')),
]
