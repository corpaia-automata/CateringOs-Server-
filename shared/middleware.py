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
