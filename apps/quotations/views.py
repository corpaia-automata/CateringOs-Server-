from django.db import models
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.events.models import Event
from apps.menu.models import EventMenuItem
from shared.permissions import IsTenantScopedJWT

from .models import Quotation
from .serializers import QuotationSerializer
from .services import generate_quotation_pdf


# ─── Helpers ─────────────────────────────────────────────────────────────────

def _build_line_items(event_id: str) -> list:
    menu_items = (
        EventMenuItem.objects
        .filter(event_id=event_id)
        .select_related('dish')
    )
    return [
        {
            'dish_name': item.dish_name_snapshot,
            'quantity':  str(item.quantity),
            'unit':      item.unit_type_snapshot,
            'category':  item.dish.category,
        }
        for item in menu_items
    ]


def _get_or_create_quotation(event_id: str, tenant_id: str) -> Quotation:
    """Return the latest quotation for the event (tenant-scoped), creating v1 if none exists."""
    quotation = (
        Quotation.objects
        .filter(event_id=event_id, tenant_id=tenant_id)
        .order_by('-version_number')
        .first()
    )
    if quotation is None:
        event = get_object_or_404(Event, id=event_id, tenant_id=tenant_id)
        quotation = Quotation.objects.create(
            event=event,
            tenant_id=tenant_id,
            version_number=1,
            status=Quotation.Status.DRAFT,
            line_items=_build_line_items(event_id),
            manual_costs=[],
            subtotal=0,
            service_charge=0,
            total_amount=0,
        )
    return quotation


def _refresh_and_render(quotation: Quotation, event_id: str) -> HttpResponse:
    """Refresh line_items from current menu, regenerate PDF, return response."""
    quotation.line_items = _build_line_items(event_id)
    quotation.save(update_fields=['line_items', 'updated_at'])

    pdf_bytes = generate_quotation_pdf(quotation)
    filename = (
        f'Afsal-Catering-{quotation.event.event_code}'
        f'-V{quotation.version_number}.pdf'
    )
    response = HttpResponse(pdf_bytes, content_type='application/pdf')
    response['Content-Disposition'] = f'inline; filename="{filename}"'
    return response


# ─── ViewSet ─────────────────────────────────────────────────────────────────

class QuotationViewSet(viewsets.ModelViewSet):
    serializer_class = QuotationSerializer
    permission_classes = [IsAuthenticated, IsTenantScopedJWT]

    def get_queryset(self):
        qs = (
            Quotation.objects
            .filter(tenant_id=self.request.tenant_id)
            .select_related('event')
        )
        # Support both nested URL (event_pk) and flat URL (?event=)
        event_id = self.kwargs.get('event_pk') or self.request.query_params.get('event')
        if event_id:
            qs = qs.filter(event_id=event_id)

        # Search by client name / quote number
        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(
                models.Q(event__customer_name__icontains=search) |
                models.Q(quote_number__icontains=search)
            )

        # Status filter
        status_filter = self.request.query_params.get('status', '').strip()
        if status_filter:
            qs = qs.filter(status=status_filter)

        # Date range on event_date
        date_from = self.request.query_params.get('date_from', '').strip()
        date_to   = self.request.query_params.get('date_to',   '').strip()
        if date_from:
            qs = qs.filter(event__event_date__gte=date_from)
        if date_to:
            qs = qs.filter(event__event_date__lte=date_to)

        return qs

    def perform_create(self, serializer):
        event_id = self.kwargs.get('event_pk') or self.request.data.get('event')
        event = get_object_or_404(Event, id=event_id, tenant_id=self.request.tenant_id)

        last = (
            Quotation.objects
            .filter(event_id=event_id, tenant_id=self.request.tenant_id)
            .order_by('-version_number')
            .first()
        )
        version = (last.version_number + 1) if last else 1

        serializer.save(
            event=event,
            tenant_id=self.request.tenant_id,
            version_number=version,
            line_items=_build_line_items(event_id),
        )

    @action(detail=True, methods=['get'], url_path='pdf')
    def pdf(self, request, pk=None, event_pk=None):
        quotation = get_object_or_404(Quotation, id=pk, tenant_id=request.tenant_id)
        eid = str(event_pk or quotation.event_id)
        return _refresh_and_render(quotation, eid)

    @action(detail=False, methods=['get'], url_path='latest/pdf')
    def latest_pdf(self, request, event_pk=None):
        eid = event_pk or request.query_params.get('event')
        if not eid:
            return Response(
                {'detail': 'event_pk is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        quotation = _get_or_create_quotation(eid, request.tenant_id)
        return _refresh_and_render(quotation, eid)
