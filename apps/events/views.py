import logging
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.http import HttpResponse
from django.utils import timezone
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from shared.exports.excel_service import create_workbook, workbook_to_bytes
from shared.permissions import IsTenantScopedJWT

from .filters import EventFilter
from .models import Event
from .serializers import EventLogSerializer, EventSerializer, EventTransitionSerializer
from .services import EventExecutionService, EventService, recalculate_event

logger = logging.getLogger(__name__)


class EventViewSet(viewsets.ModelViewSet):
    serializer_class = EventSerializer
    permission_classes = [IsAuthenticated, IsTenantScopedJWT]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class = EventFilter
    search_fields = ['event_code', 'customer_name', 'event_type', 'venue']
    ordering_fields = ['event_date', 'event_time', 'status', 'created_at']

    def get_queryset(self):
        return (
            Event.objects
            .filter(tenant_id=self.request.tenant_id)
            .select_related('inquiry', 'quotation')
        )

    def perform_create(self, serializer):
        serializer.save(tenant_id=self.request.tenant_id)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @staticmethod
    def _validation_response(exc):
        message = getattr(exc, 'message', None) or getattr(exc, 'messages', None) or str(exc)
        if isinstance(message, list):
            message = ', '.join(str(item) for item in message)
        return Response({'detail': message}, status=status.HTTP_400_BAD_REQUEST)

    @action(detail=True, methods=['patch'], url_path='menu')
    def menu(self, request, pk=None, *args, **kwargs):
        event = self.get_object()
        dishes = request.data.get('dishes')
        if not isinstance(dishes, list):
            return Response({'detail': 'dishes must be a list.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            event = EventExecutionService.replace_menu(event, dishes, request.user)
        except ValidationError as exc:
            return self._validation_response(exc)
        except Exception as exc:
            logger.exception('Failed to update event menu: event_id=%s tenant_id=%s', event.id, request.tenant_id)
            return Response({'detail': f'Failed to update menu: {exc}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(self.get_serializer(event).data)

    @action(detail=True, methods=['patch'], url_path='services')
    def services(self, request, pk=None, *args, **kwargs):
        event = self.get_object()
        services = request.data.get('services')
        if not isinstance(services, list):
            return Response({'detail': 'services must be a list.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            event = EventExecutionService.replace_services(event, services, request.user)
        except ValidationError as exc:
            return self._validation_response(exc)
        except Exception as exc:
            logger.exception('Failed to update event services: event_id=%s tenant_id=%s', event.id, request.tenant_id)
            return Response({'detail': f'Failed to update services: {exc}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(self.get_serializer(event).data)

    @action(detail=True, methods=['patch'], url_path='costing')
    def costing(self, request, pk=None, *args, **kwargs):
        event = self.get_object()
        items = request.data.get('items', request.data.get('costing'))
        if not isinstance(items, list):
            return Response({'detail': 'items must be a list.'}, status=status.HTTP_400_BAD_REQUEST)
        try:
            event = EventExecutionService.replace_costing(event, items, request.user)
        except ValidationError as exc:
            return self._validation_response(exc)
        return Response(self.get_serializer(event).data)

    @action(detail=True, methods=['patch'], url_path='pricing')
    def pricing(self, request, pk=None, *args, **kwargs):
        event = self.get_object()
        try:
            event = EventExecutionService.update_pricing(event, request.data, request.user)
        except ValidationError as exc:
            return self._validation_response(exc)
        return Response(self.get_serializer(event).data)

    @action(detail=True, methods=['post'], url_path='extra-charge')
    def extra_charge(self, request, pk=None, *args, **kwargs):
        event = self.get_object()
        try:
            event = EventExecutionService.add_extra_charge(event, request.data, request.user)
        except ValidationError as exc:
            return self._validation_response(exc)
        return Response(self.get_serializer(event).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='activity')
    def activity(self, request, pk=None, *args, **kwargs):
        event = self.get_object()
        logs = event.logs.select_related('user').all()
        return Response(EventLogSerializer(logs, many=True).data)

    @action(detail=True, methods=['post'], url_path='generate-grocery')
    def generate_grocery(self, request, pk=None, *args, **kwargs):
        event = self.get_object()
        event = recalculate_event(event.id)
        count = len(event.grocery_snapshot.get('items', [])) if isinstance(event.grocery_snapshot, dict) else 0
        data = dict(self.get_serializer(event).data)
        data.update({
            'detail': f'Grocery list generated with {count} ingredients.',
            'count': count,
        })
        return Response(data)

    @action(detail=True, methods=['post'], url_path='transition')
    def transition(self, request, pk=None, *args, **kwargs):
        self.get_object()  # ownership check — 404 if not this tenant's event
        serializer = EventTransitionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        try:
            event = EventService.transition_status(pk, serializer.validated_data['status'])
        except ValidationError as exc:
            return Response({'detail': exc.message}, status=status.HTTP_409_CONFLICT)

        return Response(EventSerializer(event).data)

    @action(detail=False, methods=['get'], url_path='export')
    def export(self, request, *args, **kwargs):
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
    def export_pdf(self, request, *args, **kwargs):
        queryset = self.filter_queryset(self.get_queryset())

        # Annotate pending_amount for template
        events_data = []
        for ev in queryset:
            total = ev.total_amount or Decimal('0')
            paid = ev.advance_amount or Decimal('0')
            ev.pending_amount = (total - paid) if ev.total_amount else None
            events_data.append(ev)

        from shared.exports.pdf_service import generate_pdf
        filters_applied = bool(request.query_params)
        pdf_bytes = generate_pdf('events_list_pdf.html', {
            'events': events_data,
            'filters_applied': filters_applied,
            'generated_at': timezone.now().strftime('%d %b %Y, %I:%M %p'),
        })
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = 'attachment; filename="events.pdf"'
        return response
