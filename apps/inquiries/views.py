from django.http import Http404, HttpResponse
from django.db import transaction
from django.utils import timezone
import logging
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from shared.exports.excel_service import create_workbook, workbook_to_bytes
from shared.permissions import IsTenantScopedJWT

from .filters import InquiryFilter
from .models import Inquiry, PreEstimate, PreEstimateCategory, PreEstimateItem
from .serializers import (
    InquirySerializer,
    PreEstimateCreateSerializer,
    PreEstimateDetailSerializer,
    PreEstimateItemCreateSerializer,
)
from .services import PreEstimateService, export_pre_estimate_json

logger = logging.getLogger(__name__)


class InquiryViewSet(viewsets.ModelViewSet):
    serializer_class = InquirySerializer
    permission_classes = [IsAuthenticated, IsTenantScopedJWT]
    filter_backends  = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class  = InquiryFilter
    search_fields    = ['customer_name', 'contact_number']
    ordering_fields  = ['created_at', 'tentative_date']
    ordering         = ['-created_at']

    def get_queryset(self):
        return Inquiry.objects.filter(tenant_id=self.request.tenant_id)

    def perform_create(self, serializer):
        serializer.save(tenant_id=self.request.tenant_id)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], url_path='convert')
    def convert(self, request, pk=None, *args, **kwargs):
        from apps.events.models import Event
        from apps.quotations.models import Quotation

        inquiry = self.get_object()
        request_payload = request.data if isinstance(request.data, dict) else {}
        logger.info(
            'convert_inquiry called: inquiry_id=%s tenant_id=%s user_id=%s payload=%s',
            inquiry.id, inquiry.tenant_id, getattr(request.user, 'id', None), request_payload,
        )

        try:
            latest_quotation = (
                Quotation.objects
                .filter(tenant_id=request.tenant_id, inquiry_id=inquiry.id)
                .order_by('-version_number', '-created_at')
                .first()
            )
            logger.info(
                'convert_inquiry related objects: inquiry_status=%s converted_event_id=%s quotation_id=%s quotation_locked=%s quotation_status=%s',
                inquiry.status,
                inquiry.converted_event_id,
                getattr(latest_quotation, 'id', None),
                getattr(latest_quotation, 'is_locked', None),
                getattr(latest_quotation, 'status', None),
            )

            # Idempotent behavior: if this inquiry is already converted, return existing event.
            if inquiry.converted_event_id:
                return Response(
                    {'event_id': str(inquiry.converted_event_id), 'success': True, 'already_converted': True},
                    status=status.HTTP_200_OK,
                )

            if not latest_quotation:
                return Response({'error': 'Quotation not found'}, status=status.HTTP_400_BAD_REQUEST)
            if not latest_quotation.is_locked:
                return Response({'error': 'Quotation not finalized'}, status=status.HTTP_400_BAD_REQUEST)

            if not inquiry.customer_name:
                return Response({'error': 'Customer name is required for conversion'}, status=status.HTTP_400_BAD_REQUEST)
            if not inquiry.event_type:
                return Response({'error': 'Event type is required for conversion'}, status=status.HTTP_400_BAD_REQUEST)

            guest_count = int(inquiry.guest_count or 0)
            if guest_count <= 0:
                return Response({'error': 'Guest count must be greater than 0'}, status=status.HTTP_400_BAD_REQUEST)

            # Resolve service type from quotation menu_services if possible.
            raw_service_name = ''
            if isinstance(latest_quotation.menu_services, list) and latest_quotation.menu_services:
                raw_service_name = str((latest_quotation.menu_services[0] or {}).get('name') or '').strip().upper().replace(' ', '_')
            service_type = raw_service_name if raw_service_name in Event.ServiceType.values else Event.ServiceType.OTHER

            # Keep event creation inside a transaction (event code generation uses DB locking).
            with transaction.atomic():
                event = Event.objects.create(
                    tenant_id=inquiry.tenant_id,
                    inquiry=inquiry,
                    quotation=latest_quotation,
                    customer_name=inquiry.customer_name,
                    contact_number=inquiry.contact_number or '',
                    event_type=inquiry.event_type,
                    event_date=inquiry.tentative_date,
                    venue=inquiry.notes or '',
                    guest_count=guest_count,
                    service_type=service_type,
                    total_amount=latest_quotation.final_selling_price,
                    advance_amount=latest_quotation.advance_amount,
                    notes=latest_quotation.payment_terms or '',
                )

                inquiry.converted_event = event
                inquiry.converted_at = timezone.now()
                inquiry.save(update_fields=['converted_event', 'converted_at', 'updated_at'])

            logger.info(
                'convert_inquiry success: inquiry_id=%s event_id=%s quotation_id=%s',
                inquiry.id, event.id, latest_quotation.id,
            )
            return Response({'event_id': str(event.id), 'success': True}, status=status.HTTP_200_OK)
        except Exception as exc:
            logger.exception(
                'convert_inquiry failed: inquiry_id=%s tenant_id=%s error=%s',
                inquiry.id, inquiry.tenant_id, str(exc),
            )
            return Response({'error': str(exc)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    @action(detail=False, methods=['get'], url_path='export')
    def export(self, request):
        """GET /api/app/<slug>/inquiries/export/ — download filtered leads as Excel."""
        queryset = self.filter_queryset(self.get_queryset())

        wb = create_workbook()
        ws = wb.active
        ws.title = 'Leads'

        headers = [
            'Customer Name', 'Contact Number', 'Source Channel',
            'Event Type', 'Tentative Date', 'Guests',
            'Estimated Budget', 'Status', 'Notes', 'Created At',
        ]
        ws.append(headers)

        for inquiry in queryset:
            ws.append([
                inquiry.customer_name,
                inquiry.contact_number or '',
                inquiry.get_source_channel_display(),
                inquiry.event_type or '',
                str(inquiry.tentative_date) if inquiry.tentative_date else '',
                inquiry.guest_count,
                float(inquiry.estimated_budget) if inquiry.estimated_budget else '',
                inquiry.get_status_display(),
                inquiry.notes or '',
                inquiry.created_at.strftime('%Y-%m-%d %H:%M') if inquiry.created_at else '',
            ])

        content = workbook_to_bytes(wb)
        response = HttpResponse(
            content,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = 'attachment; filename="leads.xlsx"'
        return response

class PreEstimateViewSet(viewsets.GenericViewSet):
    permission_classes = [IsAuthenticated, IsTenantScopedJWT]

    def get_queryset(self):
        return (
            PreEstimate.objects
            .select_related('inquiry')
            .filter(inquiry__tenant_id=self.request.tenant_id)
        )

    def get_object(self):
        try:
            obj = self.get_queryset().get(pk=self.kwargs['pk'])
        except PreEstimate.DoesNotExist:
            raise Http404
        self.check_object_permissions(self.request, obj)
        return obj

    # GET /preestimates/?inquiry=<id>
    def list(self, request):
        inquiry_id = request.query_params.get('inquiry')
        qs = self.get_queryset()
        if inquiry_id:
            qs = qs.filter(inquiry_id=inquiry_id)
        return Response(PreEstimateDetailSerializer(qs, many=True).data)

    # POST /preestimates/
    def create(self, request):
        serializer = PreEstimateCreateSerializer(data=request.data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        pre_estimate = serializer.save()
        return Response(
            PreEstimateDetailSerializer(pre_estimate).data,
            status=status.HTTP_201_CREATED,
        )

    # GET /preestimates/{id}/
    def retrieve(self, request, pk=None):
        pre_estimate = self.get_object()
        return Response(PreEstimateDetailSerializer(pre_estimate).data)

    # POST /preestimates/{id}/add-item/
    @action(detail=True, methods=['post'], url_path='add-item')
    def add_item(self, request, pk=None):
        pre_estimate = self.get_object()
        serializer = PreEstimateItemCreateSerializer(
            data=request.data,
            context={'pre_estimate': pre_estimate},
        )
        serializer.is_valid(raise_exception=True)
        item = serializer.save()
        return Response(PreEstimateItemCreateSerializer(item).data, status=status.HTTP_201_CREATED)

    # POST /preestimates/{id}/recalculate/
    @action(detail=True, methods=['post'], url_path='recalculate')
    def recalculate(self, request, pk=None):
        self.get_object()  # ownership check
        pre_estimate = PreEstimateService.calculate_totals(pk)
        return Response(PreEstimateDetailSerializer(pre_estimate).data)

    # GET /preestimates/{id}/export/
    @action(detail=True, methods=['get'], url_path='export')
    def export(self, request, pk=None):
        self.get_object()  # ownership check
        data = export_pre_estimate_json(pk)
        return Response(data)
