from django.db import transaction
from django.http import Http404, HttpResponse
from django.utils import timezone
import logging
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.events.models import Event
from apps.quotations.models import Quotation
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
from .services import (
    PreEstimateService,
    apply_quotation_pricing_to_event,
    export_pre_estimate_json,
    merge_quotation_snapshots_into_event_after_convert,
    seed_event_execution_from_quotation,
)

logger = logging.getLogger(__name__)


class InquiryViewSet(viewsets.ModelViewSet):
    serializer_class = InquirySerializer
    permission_classes = [IsAuthenticated, IsTenantScopedJWT]
    filter_backends  = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_class  = InquiryFilter
    search_fields    = ['customer_name', 'contact_number', 'venue']
    ordering_fields  = ['created_at', 'tentative_date']
    ordering         = ['-created_at']

    def get_queryset(self):
        return (
            Inquiry.objects
            .filter(tenant_id=self.request.tenant_id)
            .select_related('converted_event')
        )

    def perform_create(self, serializer):
        serializer.save(tenant_id=self.request.tenant_id)

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.soft_delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'], url_path='convert')
    def convert(self, request, pk=None, *args, **kwargs):
        inquiry = self.get_object()

        if inquiry.status == Inquiry.Status.LOST:
            return Response(
                {'detail': 'Cannot convert a lost lead.'},
                status=status.HTTP_400_BAD_REQUEST,
            )

        with transaction.atomic():
            # Lock inquiry row only. select_related(converted_event) + select_for_update
            # produces an outer join; PostgreSQL rejects FOR UPDATE on the nullable side.
            locked = Inquiry.objects.select_for_update(of=('self',)).get(
                pk=inquiry.pk,
                tenant_id=request.tenant_id,
            )

            if locked.converted_event_id:
                eid = str(locked.converted_event_id)
                return Response({'id': eid, 'event_id': eid}, status=status.HTTP_200_OK)

            event = Event(
                tenant_id=request.tenant_id,
                inquiry=locked,
                customer_name=locked.customer_name,
                contact_number=locked.contact_number or '',
                event_type=locked.event_type or '',
                event_date=locked.tentative_date,
                venue=locked.venue or '',
                guest_count=max(1, locked.guest_count or 1),
                service_type=Event.ServiceType.OTHER,
                status=Event.Status.CONFIRMED,
                total_amount=locked.estimated_budget,
                notes=locked.notes or '',
            )
            event.save()

            latest_q = (
                Quotation.objects.filter(
                    inquiry_id=locked.pk,
                    tenant_id=request.tenant_id,
                )
                .order_by('-version_number', '-created_at')
                .first()
            )
            if latest_q and not Event.all_objects.filter(quotation_id=latest_q.pk).exists():
                event.quotation = latest_q
                event.save(update_fields=['quotation', 'updated_at'])
                # Snapshot line-items from quotation JSON; reconcile totals afterward.
                seed_user = getattr(request, 'user', None)
                seed_actor = seed_user if getattr(seed_user, 'is_authenticated', False) else None
                event = seed_event_execution_from_quotation(event, latest_q, seed_actor)
                event = apply_quotation_pricing_to_event(event, latest_q, seed_actor)
                event = merge_quotation_snapshots_into_event_after_convert(event, latest_q, seed_actor)

            now = timezone.now()
            locked.converted_event = event
            locked.converted_at = now
            if locked.status != Inquiry.Status.SUCCESS:
                locked.status = Inquiry.Status.SUCCESS
            locked.save(update_fields=['converted_event', 'converted_at', 'status', 'updated_at'])

        eid = str(event.id)
        return Response({'id': eid, 'event_id': eid}, status=status.HTTP_201_CREATED)

    @action(detail=False, methods=['get'], url_path='export')
    def export(self, request):
        """GET /api/app/<slug>/inquiries/export/ — download filtered leads as Excel."""
        queryset = self.filter_queryset(self.get_queryset())

        wb = create_workbook()
        ws = wb.active
        ws.title = 'Leads'

        headers = [
            'Customer Name', 'Contact Number', 'Source Channel',
            'Event Type', 'Tentative Date', 'Venue', 'Guests',
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
                inquiry.venue or '',
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
