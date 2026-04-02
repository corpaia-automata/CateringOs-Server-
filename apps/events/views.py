from decimal import Decimal

from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.response import Response

from shared.exports.excel_service import create_workbook, workbook_to_bytes

from .filters import EventFilter
from .models import Event
from .serializers import EventSerializer, EventTransitionSerializer
from .services import EventService


class EventViewSet(viewsets.ModelViewSet):
    queryset = Event.objects.all()
    serializer_class = EventSerializer
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = EventFilter
    search_fields = ['event_code', 'customer_name', 'event_type', 'venue']
    ordering_fields = ['event_date', 'event_time', 'status', 'created_at']

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], url_path='generate-grocery')
    def generate_grocery(self, request, pk=None):
        from apps.engine.calculation import CalculationEngine
        event = self.get_object()
        count = CalculationEngine.run(event.id)
        return Response({'detail': f'Grocery list generated with {count} ingredients.', 'count': count})

    @action(detail=True, methods=['post'], url_path='transition')
    def transition(self, request, pk=None):
        serializer = EventTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            event = EventService.transition_status(pk, serializer.validated_data['status'])
        except ValidationError as exc:
            return Response({'detail': exc.message}, status=status.HTTP_409_CONFLICT)

        return Response(EventSerializer(event).data)

    @action(detail=False, methods=['get'], url_path='export')
    def export(self, request):
        queryset = self.filter_queryset(self.get_queryset())
        wb = create_workbook()
        ws = wb.active
        ws.title = 'Events'
        headers = [
            'Event Code', 'Client Name', 'Contact', 'Event Type',
            'Event Date', 'Event Time', 'Venue', 'Guests',
            'Service Type', 'Status', 'Payment Status',
            'Total Amount', 'Paid Amount', 'Pending Amount', 'Notes', 'Created At',
        ]
        ws.append(headers)
        for ev in queryset:
            total = ev.total_amount or Decimal('0')
            paid = ev.advance_amount or Decimal('0')
            pending = total - paid
            ws.append([
                ev.event_code,
                ev.customer_name,
                ev.contact_number or '',
                ev.event_type or '',
                str(ev.event_date) if ev.event_date else '',
                str(ev.event_time) if ev.event_time else '',
                ev.venue or '',
                ev.guest_count,
                ev.get_service_type_display(),
                ev.get_status_display(),
                ev.get_payment_status_display() if ev.payment_status else '',
                float(ev.total_amount) if ev.total_amount else '',
                float(paid) if ev.advance_amount else '',
                float(pending) if ev.total_amount else '',
                ev.notes or '',
                ev.created_at.strftime('%Y-%m-%d %H:%M') if ev.created_at else '',
            ])
        content = workbook_to_bytes(wb)
        response = HttpResponse(
            content,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = 'attachment; filename="events.xlsx"'
        return response

    @action(detail=False, methods=['get'], url_path='export-pdf')
    def export_pdf(self, request):
        queryset = self.filter_queryset(self.get_queryset())

        # Annotate pending_amount for template
        events_data = []
        for ev in queryset:
            total = ev.total_amount or Decimal('0')
            paid = ev.advance_amount or Decimal('0')
            ev.pending_amount = (total - paid) if ev.total_amount else None
            events_data.append(ev)

        from shared.exports.pdf_service import generate_pdf  # lazy: WeasyPrint needs GTK (Docker only)
        filters_applied = bool(request.query_params)
        pdf_bytes = generate_pdf('events_list_pdf.html', {
            'events': events_data,
            'filters_applied': filters_applied,
            'generated_at': timezone.now().strftime('%d %b %Y, %I:%M %p'),
        })
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="events.pdf"'
        return response
