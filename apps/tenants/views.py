import copy
import logging
import re

from django.db import IntegrityError, ProgrammingError
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from shared import cache
from shared.tenant_rls import with_tenant_rls

from apps.quotations.template_defaults import ensure_tenant_default_quotation_template_fk

from .models import Tenant
from .serializers import OnboardSerializer

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Country → default tenant config
# ---------------------------------------------------------------------------

COUNTRY_CONFIGS = {
    'IN': {
        'currency': 'INR',
        'timezone': 'Asia/Kolkata',
        'tax': {'type': 'GST', 'cgst': 9, 'sgst': 9, 'total': 18},
    },
    'GB': {
        'currency': 'GBP',
        'timezone': 'Europe/London',
        'tax': {'type': 'VAT', 'rate': 20},
    },
    'US': {
        'currency': 'USD',
        'timezone': 'America/New_York',
        'tax': None,
    },
}


# ---------------------------------------------------------------------------
# Slug helpers
# ---------------------------------------------------------------------------

def _base_slug(company_name: str) -> str:
    slug = company_name.lower().strip()
    slug = re.sub(r'[^a-z0-9\s-]', '', slug)
    slug = re.sub(r'\s+', '-', slug)
    slug = slug[:30].rstrip('-')
    return slug or 'workspace'


def _unique_slug(base: str) -> str:
    if not Tenant.objects.filter(slug=base).exists():
        return base
    n = 1
    while Tenant.objects.filter(slug=f'{base}-{n}').exists():
        n += 1
    return f'{base}-{n}'


# ---------------------------------------------------------------------------
# Deep-merge utility
# ---------------------------------------------------------------------------

def _deep_merge(base: dict, override: dict) -> None:
    for key, val in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(val, dict):
            _deep_merge(base[key], val)
        else:
            base[key] = val


def _subscription_payload(tenant):
    return {
        'subscription_status': tenant.subscription_status,
        'trial_days_left': tenant.trial_days_left,
        'trial_ends_at': tenant.trial_ends_at.isoformat() if tenant.trial_ends_at else None,
        'has_active_access': tenant.has_active_access,
    }


# ---------------------------------------------------------------------------
# Views
# ---------------------------------------------------------------------------

class OnboardView(APIView):
    """
    POST /api/onboard/
    Public. Creates tenant + admin user. Returns slug and app URL.
    """
    permission_classes = (AllowAny,)

    def post(self, request):
        serializer = OnboardSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        data = serializer.validated_data

        # Resolve slug
        slug = _unique_slug(_base_slug(data['companyName']))

        # Build config from country (default IN)
        country = (data.get('country') or 'IN').upper()
        config = copy.deepcopy(COUNTRY_CONFIGS.get(country, COUNTRY_CONFIGS['IN']))

        # When ``defaultTemplate`` is omitted or null, use classic.
        raw_tpl = data.get('defaultTemplate')
        default_template = 'classic' if raw_tpl is None else raw_tpl

        tenant = Tenant.objects.create(
            slug=slug,
            name=data['companyName'],
            plan=data.get('plan') or 'starter',
            config=config,
            status='active',
            default_template=default_template,
        )

        try:
            with with_tenant_rls(tenant.id):
                ensure_tenant_default_quotation_template_fk(tenant)

                # Create admin user (lazy import avoids circular deps)
                from apps.authentication.models import User

                user = User.objects.create_user(
                    email=data['email'],
                    password=data['password'],
                    tenant=tenant,
                    role=User.Role.ADMIN,
                    first_name='',
                    last_name='',
                )
                refresh = RefreshToken.for_user(user)
                refresh['tenant_id'] = str(user.tenant_id)
                refresh['tenant_slug'] = tenant.slug
                refresh['role'] = user.role
                refresh['email'] = user.email
        except IntegrityError:
            logger.exception('Onboard failed for slug=%s email=%s', slug, data['email'])
            tenant.delete()
            return Response(
                {'email': ['An account with this email already exists.']},
                status=status.HTTP_400_BAD_REQUEST,
            )
        except ProgrammingError:
            logger.exception('Onboard database schema error slug=%s', slug)
            tenant.delete()
            return Response(
                {
                    'detail': [
                        'Server database is out of date. Run migrations on the API server, then try again.',
                    ]
                },
                status=status.HTTP_503_SERVICE_UNAVAILABLE,
            )

        return Response(
            {
                'slug': slug,
                'appUrl': f'/app/{slug}/dashboard',
                'tenant_slug': slug,
                'access': str(refresh.access_token),
                'refresh': str(refresh),
                'user': {
                    'id': str(user.id),
                    'email': user.email,
                    'name': user.full_name,
                },
                'subscription': _subscription_payload(tenant),
            },
            status=status.HTTP_201_CREATED,
        )


class TenantConfigView(APIView):
    """
    GET  /api/app/<slug>/config/  — return tenant config (auth required)
    PATCH /api/app/<slug>/config/ — deep-merge update (admin only)
    """
    permission_classes = (IsAuthenticated,)

    def get(self, request, slug):
        return Response(request.tenant_config)

    def patch(self, request, slug):
        from apps.authentication.models import User
        if request.user.role != User.Role.ADMIN:
            return Response(
                {'error': 'Admin access required'},
                status=status.HTTP_403_FORBIDDEN,
            )

        merged = copy.deepcopy(request.tenant_config)
        _deep_merge(merged, request.data)

        Tenant.objects.filter(id=request.tenant_id).update(config=merged)
        cache.delete(f'tenant:config:{slug}')

        return Response({'success': True, 'config': merged})
