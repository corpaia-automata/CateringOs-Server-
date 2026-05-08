from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from config.admin_dashboard import patch_admin_index

from apps.authentication.views import BillingStatusView
from apps.master.views import CategoryListView
from apps.quotations.views import PublicQuotationView
from apps.quotations.urls import (
    branding_urlpatterns,
    quotation_urlpatterns,
    tenant_branding_urlpatterns,
    tenant_quotation_urlpatterns,
)
from apps.tenants.views import OnboardView

patch_admin_index(admin.site)

urlpatterns = [
    path('admin/', admin.site.urls),

    # Public onboarding (no auth, no tenant context)
    path('api/onboard/', OnboardView.as_view(), name='onboard'),

    # Public shared quotation (no auth)
    path('api/q/<str:public_token>/', PublicQuotationView.as_view(), name='public-quotation'),
    # Keep generate-pdf as a dedicated public route used by the public action bar.
    path('api/q/<str:public_token>/generate-pdf/', PublicQuotationView.as_view(), name='public-quotation-generate-pdf'),

    # Public global categories (no auth, no tenant context)
    path('api/categories/', CategoryListView.as_view(), name='categories'),

    # Quotation + branding (JWT tenant via user.tenant_id; TrialEnforcementMiddleware sets RLS)
    path('api/quotations/', include((quotation_urlpatterns, 'api_quotations'))),
    path('api/branding/', include((branding_urlpatterns, 'branding'))),

    # Global auth (non-tenant-scoped)
    path('api/auth/', include('apps.authentication.urls')),
    path('api/billing/status/', BillingStatusView.as_view(), name='billing-status'),

    # ── Tenant-scoped routes ──────────────────────────────────────────────────
    # TenantResolverMiddleware resolves slug → sets request.tenant_id + RLS.
    path('api/app/<slug:slug>/', include('apps.tenants.urls')),
    path('api/app/<slug:slug>/events/', include('apps.events.urls')),
    path('api/app/<slug:slug>/inquiries/', include('apps.inquiries.urls')),
    path('api/app/<slug:slug>/master/', include('apps.master.urls')),
    path('api/app/<slug:slug>/engine/', include('apps.engine.urls')),
    path('api/app/<slug:slug>/grocery/', include('apps.grocery.urls')),
    path('api/app/<slug:slug>/quotations/', include((tenant_quotation_urlpatterns, 'tenant_quotations'))),
    path('api/app/<slug:slug>/branding/', include((tenant_branding_urlpatterns, 'tenant_branding'))),
    path('api/app/<slug:slug>/reports/', include('apps.reports.urls')),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
