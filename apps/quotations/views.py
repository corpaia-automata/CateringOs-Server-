from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from apps.events.models import Event
from apps.menu.models import EventMenuItem

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


def _get_or_create_quotation(event_id: str) -> Quotation:
    """Return the latest quotation for the event, creating v1 if none exists."""
    quotation = (
        Quotation.objects
        .filter(event_id=event_id)
        .order_by('-version_number')
        .first()
    )
    if quotation is None:
        event = get_object_or_404(Event, id=event_id)
        quotation = Quotation.objects.create(
            event=event,
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

    def get_queryset(self):
        # Support both nested URL (event_pk) and flat URL (?event=)
        event_id = self.kwargs.get('event_pk') or self.request.query_params.get('event')
        qs = Quotation.objects.all()
        if event_id:
            qs = qs.filter(event_id=event_id)
        return qs

    def perform_create(self, serializer):
        event_id = self.kwargs.get('event_pk') or self.request.data.get('event')
        event = get_object_or_404(Event, id=event_id)

        last = (
            Quotation.objects
            .filter(event_id=event_id)
            .order_by('-version_number')
            .first()
        )
        version = (last.version_number + 1) if last else 1

        serializer.save(
            event=event,
            version_number=version,
            line_items=_build_line_items(event_id),
        )

    # GET /api/events/{event_pk}/quotations/{pk}/pdf/
    # GET /api/quotations/{pk}/pdf/
    @action(detail=True, methods=['get'], url_path='pdf')
    def pdf(self, request, pk=None, event_pk=None):
        quotation = get_object_or_404(Quotation, id=pk)
        eid = str(event_pk or quotation.event_id)
        return _refresh_and_render(quotation, eid)

    # GET /api/events/{event_pk}/quotations/latest/pdf/
    @action(detail=False, methods=['get'], url_path='latest/pdf')
    def latest_pdf(self, request, event_pk=None):
        eid = event_pk or request.query_params.get('event')
        if not eid:
            return Response(
                {'detail': 'event_pk is required'},
                status=status.HTTP_400_BAD_REQUEST,
            )
        quotation = _get_or_create_quotation(eid)
        return _refresh_and_render(quotation, eid)
