from django.core.exceptions import ValidationError
from django.db import Error as DBError
from django.http import HttpResponse
from django_filters.rest_framework import DjangoFilterBackend
from rest_framework import filters, status, viewsets
from rest_framework.decorators import action
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.events.serializers import EventSerializer
from shared.exports.excel_service import create_workbook, workbook_to_bytes
from shared.permissions import IsTenantScopedJWT

from .filters import InquiryFilter
from .models import Inquiry
from .serializers import InquirySerializer
from .services import InquiryService


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

    @action(detail=True, methods=['post'], url_path='convert')
    def convert(self, request, pk=None):
        """
        POST /api/app/<slug>/inquiries/{id}/convert/
        Creates an Event from this inquiry and marks it CONVERTED.
        Returns the created Event object.
        """
        inquiry = self.get_object()  # ownership check — 404 if not this tenant's inquiry
        try:
            event = InquiryService.convert_to_event(inquiry)
        except ValidationError as exc:
            msg = exc.message if hasattr(exc, 'message') and isinstance(exc.message, str) else str(exc)
            return Response({'detail': msg}, status=status.HTTP_400_BAD_REQUEST)
        except DBError:
            return Response({'detail': 'Event creation failed due to a database error.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        except Exception as exc:
            import logging
            logging.getLogger(__name__).exception('Unexpected error during lead conversion for pk=%s', pk)
            return Response({'detail': 'An unexpected error occurred during lead conversion.'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(EventSerializer(event).data, status=status.HTTP_201_CREATED)
