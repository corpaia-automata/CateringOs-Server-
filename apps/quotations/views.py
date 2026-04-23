from django.db import models
from decimal import Decimal, InvalidOperation
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.views import APIView
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from apps.inquiries.models import Inquiry
from shared.permissions import IsTenantScopedJWT

from .models import Quotation
from .serializers import QuotationSerializer
from .services import (
    generate_quotation_pdf,
    export_grocery_sheet_excel,
    export_grocery_sheet_pdf,
    generate_grocery_sheet,
)


# ─── ViewSet ─────────────────────────────────────────────────────────────────

class QuotationViewSet(viewsets.ModelViewSet):
    serializer_class = QuotationSerializer
    permission_classes = [IsAuthenticated, IsTenantScopedJWT]

    def get_queryset(self):
        qs = (
            Quotation.objects
            .filter(tenant_id=self.request.tenant_id)
            .select_related('inquiry')
        )

        inquiry_id = self.request.query_params.get('inquiry', '').strip()
        if inquiry_id:
            qs = qs.filter(inquiry_id=inquiry_id).order_by('-version_number', '-created_at')

        search = self.request.query_params.get('search', '').strip()
        if search:
            qs = qs.filter(
                models.Q(inquiry__customer_name__icontains=search) |
                models.Q(quote_number__icontains=search)
            )

        status_filter = self.request.query_params.get('status', '').strip()
        if status_filter:
            qs = qs.filter(status=status_filter)

        return qs

    def perform_create(self, serializer):
        inquiry_id = self.request.data.get('inquiry')
        inquiry = None
        if inquiry_id:
            inquiry = get_object_or_404(Inquiry, id=inquiry_id)

        last = (
            Quotation.objects
            .filter(inquiry_id=inquiry_id, tenant_id=self.request.tenant_id)
            .order_by('-version_number')
            .first()
        ) if inquiry_id else None
        version = (last.version_number + 1) if last else 1

        serializer.save(
            inquiry=inquiry,
            tenant_id=self.request.tenant_id,
            version_number=version,
            status=Quotation.Status.DRAFT,
            is_locked=False,
        )

    def perform_update(self, serializer):
        instance = self.get_object()
        if instance.is_locked:
            raise ValidationError({'detail': 'This quotation is locked. Create a revision to edit.'})
        serializer.save()

    @action(detail=True, methods=['post'], url_path='finalize')
    def finalize(self, request, pk=None, *args, **kwargs):
        quotation = self.get_object()

        if quotation.is_locked:
            return Response({'detail': 'Quotation is already finalized and locked.'}, status=status.HTTP_400_BAD_REQUEST)

        def _to_decimal(value, default='0'):
            if value is None or value == '':
                return Decimal(default)
            try:
                return Decimal(str(value))
            except (InvalidOperation, TypeError):
                raise ValidationError({'detail': f'Invalid numeric value: {value}'})

        final_selling_price = _to_decimal(request.data.get('final_selling_price'))
        internal_cost = _to_decimal(request.data.get('internal_cost'))
        advance_amount = _to_decimal(request.data.get('advance_amount'))
        payment_terms = (request.data.get('payment_terms') or '').strip()

        if final_selling_price <= 0:
            raise ValidationError({'final_selling_price': 'Must be greater than 0.'})
        if internal_cost < 0:
            raise ValidationError({'internal_cost': 'Cannot be negative.'})
        if advance_amount < 0:
            raise ValidationError({'advance_amount': 'Cannot be negative.'})

        margin = ((final_selling_price - internal_cost) / final_selling_price) * Decimal('100')

        quotation.final_selling_price = final_selling_price
        quotation.internal_cost = internal_cost
        quotation.margin = margin
        quotation.advance_amount = advance_amount
        quotation.payment_terms = payment_terms
        quotation.is_locked = True
        quotation.status = Quotation.Status.SENT
        quotation.save(update_fields=[
            'final_selling_price', 'internal_cost', 'margin',
            'advance_amount', 'payment_terms', 'is_locked', 'status', 'updated_at',
        ])

        if quotation.inquiry_id:
            quotation.inquiry.status = 'QUOTED'
            quotation.inquiry.save(update_fields=['status', 'updated_at'])

        return Response(self.get_serializer(quotation).data, status=status.HTTP_200_OK)

    @action(detail=True, methods=['post'], url_path='revise')
    def revise(self, request, pk=None, *args, **kwargs):
        current = self.get_object()
        if not current.inquiry_id:
            raise ValidationError({'detail': 'Only inquiry-linked quotations can be revised.'})

        latest = (
            Quotation.objects
            .filter(tenant_id=request.tenant_id, inquiry_id=current.inquiry_id)
            .order_by('-version_number', '-created_at')
            .first()
        )
        if not latest:
            raise ValidationError({'detail': 'No quotation found to revise.'})

        revised = Quotation.objects.create(
            tenant_id=current.tenant_id,
            inquiry_id=current.inquiry_id,
            version_number=(latest.version_number or 1) + 1,
            status=Quotation.Status.DRAFT,
            line_items=list(latest.line_items or []),
            manual_costs=list(latest.manual_costs or []),
            subtotal=latest.subtotal,
            service_charge=latest.service_charge,
            total_amount=latest.total_amount,
            final_selling_price=latest.final_selling_price,
            internal_cost=latest.internal_cost,
            margin=latest.margin,
            advance_amount=latest.advance_amount,
            payment_terms=latest.payment_terms,
            notes=latest.notes,
            menu_dishes=list(latest.menu_dishes or []),
            menu_services=list(latest.menu_services or []),
            is_locked=False,
        )

        if revised.inquiry_id:
            revised.inquiry.status = 'PLANNING'
            revised.inquiry.save(update_fields=['status', 'updated_at'])

        return Response(self.get_serializer(revised).data, status=status.HTTP_201_CREATED)

    @action(detail=True, methods=['get'], url_path='grocery-sheet')
    def grocery_sheet(self, request, pk=None, *args, **kwargs):
        quotation = self.get_object()
        data = generate_grocery_sheet(quotation)
        return Response(data)

    @action(detail=True, methods=['get'], url_path='grocery-sheet/export-excel')
    def export_grocery_sheet_excel(self, request, pk=None, *args, **kwargs):
        quotation = self.get_object()
        sheet = generate_grocery_sheet(quotation)
        content = export_grocery_sheet_excel(sheet)
        response = HttpResponse(
            content,
            content_type='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        )
        response['Content-Disposition'] = f'attachment; filename="grocery-sheet-{quotation.id}.xlsx"'
        return response

    @action(detail=True, methods=['get'], url_path='grocery-sheet/export-pdf')
    def export_grocery_sheet_pdf(self, request, pk=None, *args, **kwargs):
        quotation = self.get_object()
        sheet = generate_grocery_sheet(quotation)
        pdf_bytes = export_grocery_sheet_pdf(sheet)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        response['Content-Disposition'] = f'attachment; filename="grocery-sheet-{quotation.id}.pdf"'
        return response

    @action(detail=True, methods=['get'], url_path='export-pdf')
    def export_pdf(self, request, pk=None, *args, **kwargs):
        quotation = self.get_object()
        design = (request.query_params.get('design') or 'classic').strip().lower()
        pdf_bytes = generate_quotation_pdf(quotation, design=design)
        response = HttpResponse(pdf_bytes, content_type='application/pdf')
        filename_suffix = '-premium' if design == 'premium' else ''
        response['Content-Disposition'] = (
            f'attachment; filename="{quotation.quote_number or quotation.id}{filename_suffix}.pdf"'
        )
        return response


class QuotationItemView(APIView):
    permission_classes = [IsAuthenticated, IsTenantScopedJWT]

    @staticmethod
    def _get_items(quotation: Quotation, item_type: str):
        if item_type == 'dish':
            return list(quotation.menu_dishes or [])
        if item_type == 'service':
            return list(quotation.menu_services or [])
        raise ValidationError({'item_type': "Must be 'dish' or 'service'."})

    @staticmethod
    def _save_items(quotation: Quotation, item_type: str, items):
        if item_type == 'dish':
            quotation.menu_dishes = items
        else:
            quotation.menu_services = items
        quotation.save(update_fields=['menu_dishes', 'menu_services', 'updated_at'])

    def _get_quotation(self, request):
        quotation_id = request.data.get('quotation') or request.query_params.get('quotation')
        if not quotation_id:
            raise ValidationError({'quotation': 'This field is required.'})
        return get_object_or_404(
            Quotation.objects.filter(tenant_id=request.tenant_id),
            id=quotation_id,
        )

    def post(self, request, *args, **kwargs):
        quotation = self._get_quotation(request)
        item_type = (request.data.get('item_type') or '').strip().lower()
        item = request.data.get('item')
        if not isinstance(item, dict):
            raise ValidationError({'item': 'Must be an object.'})
        item_id = str(item.get('id') or '').strip()
        if not item_id:
            raise ValidationError({'item.id': 'This field is required.'})

        items = self._get_items(quotation, item_type)
        if any(str(existing.get('id')) == item_id for existing in items):
            raise ValidationError({'item.id': 'Item with this id already exists.'})

        items.append(item)
        self._save_items(quotation, item_type, items)
        return Response(item, status=status.HTTP_201_CREATED)

    def patch(self, request, item_id: str, *args, **kwargs):
        quotation = self._get_quotation(request)
        item_type = (request.data.get('item_type') or '').strip().lower()
        item = request.data.get('item')
        if not isinstance(item, dict):
            raise ValidationError({'item': 'Must be an object.'})
        item['id'] = item_id

        items = self._get_items(quotation, item_type)
        next_items = []
        found = False
        for existing in items:
            if str(existing.get('id')) == item_id:
                next_items.append(item)
                found = True
            else:
                next_items.append(existing)

        if not found:
            raise ValidationError({'id': 'Item not found in this quotation.'})

        self._save_items(quotation, item_type, next_items)
        return Response(item, status=status.HTTP_200_OK)

    def delete(self, request, item_id: str, *args, **kwargs):
        quotation = self._get_quotation(request)
        item_type = (request.query_params.get('item_type') or '').strip().lower()
        items = self._get_items(quotation, item_type)
        next_items = [item for item in items if str(item.get('id')) != item_id]

        if len(next_items) == len(items):
            raise ValidationError({'id': 'Item not found in this quotation.'})

        self._save_items(quotation, item_type, next_items)
        return Response(status=status.HTTP_204_NO_CONTENT)
