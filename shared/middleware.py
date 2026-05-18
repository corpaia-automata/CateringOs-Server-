"""
TenantResolverMiddleware

Intercepts every request whose path matches /api/app/{slug}/...
Resolves the tenant from cache or DB, then:
  - Attaches request.tenant        (dict with id/slug/name/plan/config)
  - Attaches request.tenant_id     (str UUID)
  - Attaches request.tenant_slug   (str)
  - Attaches request.tenant_config (dict)
  - Sets PostgreSQL session var app.current_tenant_id to activate RLS
  - Rejects (403) any JWT whose tenant_id doesn't match this slug's tenant
"""
import re

from django.db import connection
from django.http import JsonResponse

from shared import cache

TENANT_PATH_RE = re.compile(r'^/api/app/(?P<slug>[^/]+)/')


class TenantResolverMiddleware:

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        match = TENANT_PATH_RE.match(request.path)
        if match:
            slug = match.group('slug')
            cache_key = f'tenant:config:{slug}'

            tenant_data = cache.get(cache_key)

            if tenant_data is None:
                # Lazy import avoids app-registry issues at startup
                from apps.tenants.models import Tenant
                try:
                    tenant = Tenant.objects.get(slug=slug, status='active')
                    tenant_data = {
                        'id': str(tenant.id),
                        'slug': tenant.slug,
                        'name': tenant.name,
                        'plan': tenant.plan,
                        'config': tenant.config,
                    }
                    cache.set(cache_key, tenant_data, ttl=300)
                except Tenant.DoesNotExist:
                    return JsonResponse({'error': 'Workspace not found'}, status=404)

            request.tenant = tenant_data
            request.tenant_id = tenant_data['id']
            request.tenant_slug = tenant_data['slug']
            request.tenant_config = tenant_data['config']

            # Activate Row Level Security for this connection
            with connection.cursor() as cursor:
                cursor.execute(
                    "SET LOCAL app.current_tenant_id = %s",
                    [tenant_data['id']],
                )

            # ── Cross-tenant JWT guard ────────────────────────────────────────
            # If a Bearer token is present and valid, its tenant_id claim must
            # match this slug's tenant. Prevents user A's token accessing slug B.
            # Invalid / expired tokens are passed through — DRF returns 401.
            auth_header = request.META.get('HTTP_AUTHORIZATION', '')
            if auth_header.startswith('Bearer '):
                raw_token = auth_header[7:].strip()
                try:
                    from rest_framework_simplejwt.tokens import AccessToken
                    token = AccessToken(raw_token)
                    token_tenant_id = token.get('tenant_id')
                    if token_tenant_id and token_tenant_id != tenant_data['id']:
                        return JsonResponse(
                            {'error': 'Token does not belong to this workspace.'},
                            status=403,
                        )
                except Exception:
                    # Invalid / expired token — let DRF handle authentication
                    pass

        return self.get_response(request)


# class TrialEnforcementMiddleware:
#     EXEMPT_PATHS = (
#         '/api/auth/login/',
#         '/api/auth/logout/',
#         '/api/auth/signup/',
#         '/api/auth/refresh/',
#         '/api/health/',
#         '/admin/',
#     )

#     def __init__(self, get_response):
#         self.get_response = get_response

#     def __call__(self, request):
#         if request.path.startswith(self.EXEMPT_PATHS):
#             return self.get_response(request)

#         user = getattr(request, 'user', None)
#         if not getattr(user, 'is_authenticated', False):
#             self._activate_tenant_from_token(request)
#             user = self._authenticate_jwt(request)

#         if not getattr(user, 'is_authenticated', False):
#             return self.get_response(request)

#         if getattr(user, 'is_superuser', False):
#             return self.get_response(request)

#         try:
#             tenant = user.tenant
#         except AttributeError:
#             tenant = None

#         if tenant is None:
#             return self.get_response(request)

#         from apps.tenants.models import SubscriptionStatus

#         if tenant.subscription_status == SubscriptionStatus.TRIAL and tenant.is_trial_expired:
#             tenant.subscription_status = SubscriptionStatus.EXPIRED
#             tenant.save(update_fields=['subscription_status'])
#             return self._blocked_response(tenant, 'trial_expired')

#         if tenant.subscription_status in [SubscriptionStatus.EXPIRED, SubscriptionStatus.CANCELLED]:
#             return self._blocked_response(
#                 tenant,
#                 f'subscription_{tenant.subscription_status.lower()}',
#             )

#         request.trial_info = self._subscription_payload(tenant)
#         return self.get_response(request)

#     def _authenticate_jwt(self, request):
#         try:
#             from rest_framework_simplejwt.authentication import JWTAuthentication

#             authenticated = JWTAuthentication().authenticate(request)
#         except Exception:
#             return getattr(request, 'user', None)

#         if authenticated is None:
#             return getattr(request, 'user', None)

#         user, _token = authenticated
#         request.user = user
#         return user

#     def _activate_tenant_from_token(self, request):
#         if getattr(request, 'tenant_id', None):
#             return

#         auth_header = request.META.get('HTTP_AUTHORIZATION', '')
#         if not auth_header.startswith('Bearer '):
#             return

#         try:
#             from rest_framework_simplejwt.tokens import AccessToken

#             token = AccessToken(auth_header[7:].strip())
#             tenant_id = token.get('tenant_id')
#         except Exception:
#             return

#         if not tenant_id:
#             return

#         with connection.cursor() as cursor:
#             cursor.execute(
#                 "SET LOCAL app.current_tenant_id = %s",
#                 [tenant_id],
#             )

#     def _subscription_payload(self, tenant):
#         return {
#             'subscription_status': tenant.subscription_status,
#             'trial_days_left': tenant.trial_days_left,
#             'trial_ends_at': tenant.trial_ends_at.isoformat() if tenant.trial_ends_at else None,
#             'has_active_access': tenant.has_active_access,
#         }

#     def _blocked_response(self, tenant, reason):
#         return JsonResponse(
#             {
#                 'error': 'trial_ended',
#                 'message': 'Your trial has ended. We will be in touch soon.',
#                 'trial_ended': True,
#             },
#             status=403,
#         )
