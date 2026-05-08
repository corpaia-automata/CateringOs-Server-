from django.urls import path
from rest_framework.routers import DefaultRouter

from .views import (
    BrandingProfileViewSet,
    LegacyQuotationTemplateViewSet,
    LegacyQuotationViewSet,
    QuotationTemplateViewSet,
    QuotationViewSet,
    TenantScopedBrandingProfileViewSet,
)

router = DefaultRouter()
router.register(r'templates', LegacyQuotationTemplateViewSet, basename='quotation-template')
router.register(r'', LegacyQuotationViewSet, basename='quotation')

# /api/quotations/ … (JWT tenant; no /api/app/<slug>/ prefix)
quotation_urlpatterns = router.urls

branding_router = DefaultRouter()
branding_router.register(r'', BrandingProfileViewSet, basename='branding')
branding_urlpatterns = branding_router.urls

# /api/app/<slug>/quotations/ — slug-scoped ViewSets (TenantResolverMiddleware sets request.tenant_id + RLS)
_ts_router = DefaultRouter()
_ts_router.register(r'templates', QuotationTemplateViewSet, basename='tenant-quotation-template')
_ts_router.register(r'', QuotationViewSet, basename='tenant-quotation')

tenant_quotation_urlpatterns = _ts_router.urls

_ts_branding_router = DefaultRouter()
_ts_branding_router.register(r'', TenantScopedBrandingProfileViewSet, basename='tenant-branding')
tenant_branding_urlpatterns = _ts_branding_router.urls

urlpatterns = quotation_urlpatterns
