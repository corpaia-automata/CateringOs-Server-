from copy import deepcopy
from decimal import Decimal, InvalidOperation
from uuid import UUID

from django.db import transaction
from django.db.models import Max
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.template.loader import render_to_string
from django.utils import timezone
from rest_framework import mixins, viewsets, status
from rest_framework.decorators import action
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from shared.permissions import HasTenantMembership, IsTenantScopedJWT

from .filters import QuotationFilter
from .models import BrandingProfile, Quotation, QuotationTemplate
from .pdf_utils import html_to_pdf_bytes, safe_quotation_pdf_filename
from .serializers import (
    PublicQuotationSerializer,
    QuotationDetailSerializer,
    QuotationTemplateReadSerializer,
    QuotationTemplateWriteSerializer,
)
from .writable_serializers import (
    BrandingProfileSerializer,
    QuotationSerializer,
    QuotationTemplateSerializer,
)
from .services import (
    build_grocery_sheet_payload,
    build_quotation_context,
    grocery_sheet_pdf_bytes,
    grocery_sheet_workbook_bytes,
    next_quote_number,
)


class PublicQuotationView(APIView):
    """
    Client-facing public endpoint: merged template + quotation payload keyed by ``public_token``.

    No authentication. Used for shareable quote links (``/api/q/<token>/``).
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    def _resolve_quotation(self, public_token):
        try:
            token = UUID(str(public_token))
        except ValueError as exc:
            raise Http404('Invalid quote link.') from exc

        return get_object_or_404(
            Quotation.objects.filter(is_deleted=False).select_related(
                'inquiry',
                'template',
                'template__tenant',
            ),
            public_token=token,
        )

    def get(self, request, public_token):
        quotation = self._resolve_quotation(public_token)
        # menu_dishes / menu_services are JSONField columns (not relations); no prefetch applies.
        serializer = PublicQuotationSerializer(quotation, context={'request': request})
        return Response(serializer.data)

    def post(self, request, public_token):
        # Guard the base public payload route so POST is only valid on /generate-pdf/.
        if not request.path.rstrip('/').endswith('generate-pdf'):
            return Response({'detail': 'Method "POST" not allowed.'}, status=status.HTTP_405_METHOD_NOT_ALLOWED)

        quotation = self._resolve_quotation(public_token)
        from .tasks import generate_quotation_pdf

        # Public quote action bar posts by token; queue the same celery task used in tenant APIs.
        async_result = generate_quotation_pdf.delay(str(quotation.pk))
        return Response(
            {'task_id': str(async_result.id), 'status': 'processing'},
            status=status.HTTP_202_ACCEPTED,
        )


class LegacyQuotationTemplateViewSet(viewsets.ModelViewSet):
    """Tenant quotation templates — branding + ``template_type`` (classic / premium / minimal)."""

    serializer_class = QuotationTemplateSerializer
    permission_classes = [HasTenantMembership]
    http_method_names = ['get', 'head', 'options', 'put', 'patch', 'post']

    def create(self, request, *args, **kwargs):
        return Response(
            {'detail': 'Template creation is not available via this API (use Django admin or onboarding).'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def destroy(self, request, *args, **kwargs):
        return Response(
            {'detail': 'Destroy not supported.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def get_queryset(self):
        tid = getattr(self.request, 'tenant_id', None)
        if tid is None:
            tid = getattr(self.request.user, 'tenant_id', None)
        if tid is None:
            return QuotationTemplate.objects.none()
        return QuotationTemplate.objects.filter(tenant_id=tid).order_by('-updated_at')

    @action(detail=True, methods=['post'], url_path='clone')
    def clone(self, request, pk=None):
        """Duplicate template under ``target_tenant_id`` (superuser may clone across tenants)."""
        src = self.get_object()
        raw_tid = (request.data or {}).get('target_tenant_id')
        if raw_tid is None or str(raw_tid).strip() == '':
            return Response({'detail': 'target_tenant_id is required.'}, status=status.HTTP_400_BAD_REQUEST)
        target_tid = str(raw_tid).strip()
        user_tid = getattr(request.user, 'tenant_id', None)
        if not request.user.is_superuser and str(user_tid) != target_tid:
            raise PermissionDenied('You may only clone into your own tenant.')

        dup = QuotationTemplate.objects.get(pk=src.pk)
        dup.pk = None
        dup.name = f'{src.name} (copy)'
        dup.tenant_id = target_tid
        dup.is_active = False
        dup.activated_at = None
        dup.configured_by = None
        dup.created_by = request.user if getattr(request.user, 'is_authenticated', False) else None
        dup.save()
        data = QuotationTemplateSerializer(dup, context=self.get_serializer_context()).data
        return Response(data, status=status.HTTP_201_CREATED)


class BrandingProfileViewSet(viewsets.ModelViewSet):
    """
    list, retrieve, create, update — tenant-scoped via request.user.tenant_id.

    When this view runs under /api/app/<slug>/..., TenantResolverMiddleware sets
    request.tenant_id; use TenantScopedBrandingProfileViewSet to enforce JWT == slug.
    """

    serializer_class = BrandingProfileSerializer
    permission_classes = [HasTenantMembership]
    http_method_names = ['get', 'post', 'head', 'options', 'put', 'patch']

    def get_queryset(self):
        tid = getattr(self.request.user, 'tenant_id', None)
        if tid is None:
            return BrandingProfile.objects.none()
        return BrandingProfile.objects.filter(tenant_id=tid).order_by('-updated_at')

    def perform_create(self, serializer):
        serializer.save(tenant_id=self.request.user.tenant_id)


class LegacyQuotationViewSet(viewsets.ModelViewSet):
    """JWT tenant-scoped quotations under ``/api/quotations/`` (legacy integrations, PDF, grocery, etc.)."""

    serializer_class = QuotationSerializer
    permission_classes = [HasTenantMembership]
    queryset = Quotation.objects.all()
    filterset_class = QuotationFilter

    def get_queryset(self):
        tid = getattr(self.request, 'tenant_id', None)
        if tid is None:
            tid = getattr(self.request.user, 'tenant_id', None)
        if tid is None:
            return Quotation.objects.none()
        return (
            Quotation.objects.filter(tenant_id=tid)
            .select_related('template', 'inquiry', 'tenant')
            .order_by('-created_at')
        )

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx

    @action(detail=True, methods=['get'], url_path='grocery-sheet/export-excel')
    def grocery_sheet_export_excel(self, request, pk=None, **kwargs):
        quotation = self.get_object()
        content = grocery_sheet_workbook_bytes(quotation, request.tenant_id)
        safe = (quotation.quote_number or str(quotation.pk)).replace(' ', '_')
        response = HttpResponse(
            content,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = f'attachment; filename="grocery-sheet-{safe}.xlsx"'
        return response

    @action(detail=True, methods=['get'], url_path='grocery-sheet/export-pdf')
    def grocery_sheet_export_pdf(self, request, pk=None, **kwargs):
        quotation = self.get_object()
        content = grocery_sheet_pdf_bytes(quotation, request.tenant_id)
        safe = (quotation.quote_number or str(quotation.pk)).replace(' ', '_')
        response = HttpResponse(content, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="grocery-sheet-{safe}.pdf"'
        return response

    @action(detail=True, methods=['get'], url_path='grocery-sheet')
    def grocery_sheet(self, request, pk=None, **kwargs):
        quotation = self.get_object()
        return Response(build_grocery_sheet_payload(quotation, request.tenant_id))

    @action(detail=True, methods=['get'], url_path='preview')
    def preview(self, request, pk=None, **kwargs):
        quotation = self.get_object()
        context = build_quotation_context(quotation)
        html = render_to_string('quotation/quotation.html', context)
        return HttpResponse(html, content_type='text/html; charset=utf-8')

    @action(detail=True, methods=['get'], url_path='pdf')
    def pdf(self, request, pk=None, **kwargs):
        quotation = self.get_object()
        context = build_quotation_context(quotation)
        html = render_to_string('quotation/quotation.html', context)
        base_url = request.build_absolute_uri('/')
        pdf_bytes = html_to_pdf_bytes(html, base_url=base_url)
        tenant_name = ''
        if quotation.tenant_id:
            tenant_name = getattr(quotation.tenant, 'name', '') or ''
        fname = safe_quotation_pdf_filename(tenant_name, quotation.quote_number or str(quotation.pk))
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{fname}"'
        return response

    @action(detail=True, methods=['post'], url_path='revise')
    def revise(self, request, pk=None, **kwargs):
        """Create a new quotation row copying pricing/menu from this one; bump version_number per inquiry."""
        source = self.get_object()
        tenant_id = source.tenant_id

        if source.inquiry_id:
            max_v = (
                Quotation.objects.filter(tenant_id=tenant_id, inquiry_id=source.inquiry_id).aggregate(
                    m=Max('version_number'),
                )['m']
                or 0
            )
        else:
            max_v = source.version_number
        next_version = max_v + 1

        quoted_by_id = None
        if getattr(request.user, 'is_authenticated', False):
            quoted_by_id = request.user.pk

        new_q = Quotation(
            tenant_id=tenant_id,
            inquiry_id=source.inquiry_id,
            version_number=next_version,
            status=Quotation.Status.DRAFT,
            line_items=deepcopy(source.line_items) if source.line_items else [],
            manual_costs=deepcopy(source.manual_costs) if source.manual_costs else [],
            subtotal=source.subtotal,
            service_charge=source.service_charge,
            total_amount=source.total_amount,
            notes=source.notes,
            accepted_at=None,
            quoted_by_id=quoted_by_id,
            sent_at=None,
            menu_dishes=deepcopy(source.menu_dishes) if source.menu_dishes else [],
            menu_services=deepcopy(source.menu_services) if source.menu_services else [],
            advance_amount=source.advance_amount,
            final_selling_price=source.final_selling_price,
            internal_cost=source.internal_cost,
            is_locked=False,
            margin=source.margin,
            payment_terms=source.payment_terms,
            credited_amount=source.credited_amount,
            costing_data=deepcopy(source.costing_data) if source.costing_data else {},
            grocery_data=deepcopy(source.grocery_data) if source.grocery_data else {},
            pricing_data=deepcopy(source.pricing_data) if source.pricing_data else {},
            pdf_file='',
            template_snapshot=deepcopy(source.template_snapshot) if source.template_snapshot else None,
            template_id=source.template_id,
        )
        new_q.quote_number = next_quote_number(tenant_id)
        new_q.save()
        data = QuotationSerializer(new_q, context=self.get_serializer_context()).data
        data['rev_number'] = data.get('version_number')
        return Response(data, status=status.HTTP_201_CREATED)

    @staticmethod
    def _coerce_decimal(value, fallback):
        if value is None:
            return fallback
        try:
            return Decimal(str(value))
        except (InvalidOperation, TypeError, ValueError):
            return fallback

    def _apply_finalize_quotation(self, request, pk=None, **kwargs):
        """Persist pricing/cost snapshots and lock quotation as sent (UI Finalise)."""
        quotation = self.get_object()
        if quotation.is_locked:
            return Response(
                {'detail': 'Quotation already finalised.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        data = getattr(request, 'data', {}) or {}

        fs = self._coerce_decimal(data.get('final_selling_price'), quotation.final_selling_price)
        ic = self._coerce_decimal(data.get('internal_cost'), quotation.internal_cost or Decimal('0'))
        aa = self._coerce_decimal(data.get('advance_amount'), quotation.advance_amount)

        quotation.final_selling_price = fs if fs is not None else quotation.final_selling_price
        quotation.total_amount = quotation.final_selling_price
        quotation.internal_cost = ic
        quotation.advance_amount = aa if aa is not None else quotation.advance_amount

        if 'payment_terms' in data:
            quotation.payment_terms = str(data.get('payment_terms') or '')

        cd = data.get('costing_data')
        if isinstance(cd, dict):
            quotation.costing_data = cd
        gd = data.get('grocery_data')
        if isinstance(gd, dict):
            quotation.grocery_data = gd
        pd = data.get('pricing_data')
        if isinstance(pd, dict):
            quotation.pricing_data = pd

        fin = quotation.final_selling_price or Decimal('0')
        if fin > 0:
            quotation.margin = (((fin - (quotation.internal_cost or Decimal('0'))) / fin) * Decimal('100')).quantize(
                Decimal('0.01'),
            )
        else:
            quotation.margin = Decimal('0')

        quotation.status = Quotation.Status.SENT
        quotation.is_locked = True
        quotation.sent_at = timezone.now()

        quotation.save()
        out = QuotationSerializer(quotation, context=self.get_serializer_context()).data
        return Response(out, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='finalize')
    def finalize(self, request, pk=None, **kwargs):
        return self._apply_finalize_quotation(request, pk=pk, **kwargs)

    @action(detail=True, methods=['post'], url_path='finalise')
    def finalise(self, request, pk=None, **kwargs):
        """UK spelling alias for clients that POST …/finalise/."""
        return self._apply_finalize_quotation(request, pk=pk, **kwargs)


class TenantScopedBrandingProfileViewSet(BrandingProfileViewSet):
    """JWT tenant_id must match workspace slug (defence in depth with middleware)."""

    permission_classes = [HasTenantMembership, IsTenantScopedJWT]


class QuotationTemplateViewSet(
    mixins.ListModelMixin,
    mixins.RetrieveModelMixin,
    mixins.UpdateModelMixin,
    viewsets.GenericViewSet,
):
    """
    Workspace templates under ``/api/app/<slug>/templates/`` (v1: list/retrieve/update only).

    TODO: add list pagination consistent with product defaults (global DRF pagination disabled here).
    """

    permission_classes = [IsAuthenticated]
    serializer_class = QuotationTemplateReadSerializer
    pagination_class = None
    http_method_names = ['get', 'head', 'options', 'put', 'patch']

    def get_queryset(self):
        slug = self.kwargs['slug']
        return (
            QuotationTemplate.objects.filter(tenant__slug=slug, is_deleted=False)
            .select_related('tenant')
            .order_by('-updated_at')
        )

    def get_serializer_class(self):
        if self.action in ('update', 'partial_update'):
            return QuotationTemplateWriteSerializer
        return QuotationTemplateReadSerializer

    def perform_update(self, serializer):
        with transaction.atomic():
            instance = serializer.save()
            if instance.is_default:
                (
                    QuotationTemplate.objects.filter(tenant_id=instance.tenant_id, is_deleted=False)
                    .exclude(pk=instance.pk)
                    .update(is_default=False)
                )


class QuotationViewSet(viewsets.ModelViewSet):
    """
    Tenant quotations keyed by URL ``slug`` (``/api/app/<slug>/quotations/``).

    TODO: add list pagination when product requirements are finalized.
    """

    permission_classes = [IsAuthenticated]
    pagination_class = None
    filterset_class = QuotationFilter
    http_method_names = ['get', 'head', 'options', 'post', 'put', 'patch', 'delete']

    def get_queryset(self):
        slug = self.kwargs['slug']
        return (
            Quotation.objects.filter(tenant__slug=slug, is_deleted=False)
            .select_related('inquiry', 'template', 'template__tenant', 'tenant')
            .order_by('-created_at')
        )

    def get_serializer_class(self):
        if self.action in ('list', 'retrieve'):
            return QuotationDetailSerializer
        return QuotationSerializer

    def get_serializer_context(self):
        ctx = super().get_serializer_context()
        ctx['request'] = self.request
        return ctx

    @action(detail=True, methods=['get'], url_path='grocery-sheet')
    def grocery_sheet(self, request, pk=None, **kwargs):
        quotation = self.get_object()
        return Response(build_grocery_sheet_payload(quotation, quotation.tenant_id))

    @action(detail=True, methods=['get'], url_path='grocery-sheet/export-excel')
    def grocery_sheet_export_excel(self, request, pk=None, **kwargs):
        quotation = self.get_object()
        content = grocery_sheet_workbook_bytes(quotation, quotation.tenant_id)
        safe = (quotation.quote_number or str(quotation.pk)).replace(' ', '_')
        response = HttpResponse(
            content,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = f'attachment; filename="grocery-sheet-{safe}.xlsx"'
        return response

    @action(detail=True, methods=['get'], url_path='grocery-sheet/export-pdf')
    def grocery_sheet_export_pdf(self, request, pk=None, **kwargs):
        quotation = self.get_object()
        content = grocery_sheet_pdf_bytes(quotation, quotation.tenant_id)
        safe = (quotation.quote_number or str(quotation.pk)).replace(' ', '_')
        response = HttpResponse(content, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="grocery-sheet-{safe}.pdf"'
        return response

    @action(detail=True, methods=['post'], url_path='generate-pdf')
    def generate_pdf(self, request, pk=None, **kwargs):
        quotation = self.get_object()
        from .tasks import generate_quotation_pdf

        async_result = generate_quotation_pdf.delay(str(quotation.pk))
        return Response(
            {'task_id': str(async_result.id), 'status': 'processing'},
            status=status.HTTP_202_ACCEPTED,
        )

    @action(detail=True, methods=['post'], url_path='finalize')
    def finalize(self, request, pk=None, **kwargs):
        quotation = self.get_object()
        data = request.data
        fin = data.get('final_selling_price')
        ic = data.get('internal_cost')
        try:
            fin = Decimal(str(fin)) if fin is not None else quotation.final_selling_price or Decimal('0')
            ic = Decimal(str(ic)) if ic is not None else quotation.internal_cost or Decimal('0')
        except (InvalidOperation, TypeError):
            fin = quotation.final_selling_price or Decimal('0')
            ic = quotation.internal_cost or Decimal('0')

        margin = round(float(((fin - ic) / fin) * 100), 2) if fin > 0 else 0

        update_fields = {
            'status': Quotation.Status.SENT,
            'is_locked': True,
            'final_selling_price': fin,
            'internal_cost': ic,
            'total_amount': fin,
            'margin': margin,
            'sent_at': timezone.now(),
        }
        for key in ('advance_amount', 'costing_data', 'grocery_data', 'pricing_data'):
            if key in data:
                update_fields[key] = data[key]

        for attr, value in update_fields.items():
            setattr(quotation, attr, value)
        quotation.save()

        serializer = QuotationDetailSerializer(quotation, context={'request': request})
        return Response(serializer.data)

    @action(detail=True, methods=['post'], url_path='revise')
    def revise(self, request, pk=None, **kwargs):
        source = self.get_object()
        from .services import next_quote_number

        max_version = (
            Quotation.objects.filter(
                tenant_id=source.tenant_id,
                inquiry_id=source.inquiry_id,
                is_deleted=False,
            )
            .aggregate(m=Max('version_number'))['m']
        ) or source.version_number
        new_version = max_version + 1

        new_quotation = Quotation(
            tenant_id=source.tenant_id,
            inquiry_id=source.inquiry_id,
            version_number=new_version,
            status=Quotation.Status.DRAFT,
            is_locked=False,
            menu_dishes=source.menu_dishes,
            menu_services=source.menu_services,
            costing_data=source.costing_data,
            grocery_data=source.grocery_data,
            pricing_data=source.pricing_data,
            line_items=source.line_items,
            manual_costs=source.manual_costs,
            notes=source.notes,
            template_id=source.template_id,
            template_snapshot=source.template_snapshot,
            advance_amount=source.advance_amount,
            final_selling_price=source.final_selling_price,
            internal_cost=source.internal_cost,
            total_amount=source.total_amount,
            margin=source.margin,
            subtotal=source.subtotal,
            service_charge=source.service_charge,
        )
        new_quotation.quote_number = next_quote_number(source.tenant_id)
        new_quotation.save()

        serializer = QuotationDetailSerializer(new_quotation, context={'request': request})
        return Response(
            {**serializer.data, 'version_number': new_version},
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=['get'], url_path='export-pdf')
    def export_pdf(self, request, pk=None, **kwargs):
        quotation = self.get_object()
        context = build_quotation_context(quotation)
        html = render_to_string('quotation/quotation.html', context)
        base_url = request.build_absolute_uri('/')
        pdf_bytes = html_to_pdf_bytes(html, base_url=base_url)
        tenant_name = getattr(quotation.tenant, 'name', '') or ''
        fname = safe_quotation_pdf_filename(tenant_name, quotation.quote_number or str(quotation.pk))
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="{fname}"'
        return response

    @action(detail=True, methods=['post'], url_path='send-quote')
    def send_quote(self, request, pk=None, **kwargs):
        # TODO: email integration — send quote link / PDF to client, log delivery.
        return Response({'status': 'queued'}, status=status.HTTP_202_ACCEPTED)
