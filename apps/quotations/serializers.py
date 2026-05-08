import os
import re
import uuid

from django.conf import settings
from django.core.files.storage import default_storage
from rest_framework import serializers

from apps.inquiries.models import Inquiry

from .models import Quotation, QuotationTemplate, TemplateType


class AbsoluteURLCharField(serializers.CharField):
    """Char field that turns relative URL paths into absolute URLs using ``request`` from context."""

    def to_representation(self, value):
        text = '' if value is None else str(value).strip()
        if not text:
            return ''
        if text.startswith('http://') or text.startswith('https://'):
            return text
        request = self.context.get('request')
        if request and text.startswith('/'):
            return request.build_absolute_uri(text)
        return text


class BrandingSerializer(serializers.ModelSerializer):
    """Read-only branding slice of a ``QuotationTemplate`` for public or embedded quote views."""

    logo = AbsoluteURLCharField(source='logo_url', read_only=True)
    hero_image = serializers.ImageField(read_only=True)

    class Meta:
        model = QuotationTemplate
        fields = [
            'logo',
            'hero_image',
            'primary_color',
            'accent_color',
            'font_heading',
            'font_body',
            'company_tagline',
            'about_text',
            'why_choose_us',
        ]
        read_only_fields = fields


class TemplateConfigSerializer(serializers.ModelSerializer):
    """Read-only template layout config: tier, section order, and schema flags."""

    class Meta:
        model = QuotationTemplate
        fields = ['template_type', 'sections_config', 'template_schema']
        read_only_fields = fields


class MenuDishSerializer(serializers.Serializer):
    """Normalized menu line from ``Quotation.menu_dishes`` JSON (dict rows)."""

    def to_representation(self, instance):
        if not isinstance(instance, dict):
            return {
                'id': '',
                'name': '',
                'category': '',
                'quantity': '',
                'unit': '',
                'is_complimentary': False,
            }
        d = instance
        raw_qty = d.get('quantity')
        if raw_qty is None:
            raw_qty = d.get('qty')
        qty_str = '' if raw_qty is None else str(raw_qty)
        complimentary = d.get('is_complimentary')
        if complimentary is None:
            complimentary = d.get('is_compliment', False)

        # qty as a number — frontend normalizeDish reads 'qty' (numeric), not 'quantity' (string)
        try:
            qty_num = float(raw_qty) if raw_qty not in (None, '') else 0.0
        except (TypeError, ValueError):
            qty_num = 0.0

        # rate / subtotal are stored in the JSONField by the frontend but were being stripped here
        try:
            rate = float(d.get('rate') or 0)
        except (TypeError, ValueError):
            rate = 0.0

        try:
            subtotal = float(d.get('subtotal') or 0)
        except (TypeError, ValueError):
            subtotal = 0.0

        return {
            'id': str(d.get('id') or ''),
            'name': str(d.get('name') or d.get('dish_name') or ''),
            'category': str(d.get('category') or ''),
            'quantity': qty_str,          # kept for any existing consumers
            'qty': qty_num,               # numeric form normalizeDish reads
            'unit': str(d.get('unit') or ''),
            'is_complimentary': bool(complimentary),
            'rate': rate,
            'subtotal': subtotal,
            'pricingType': d.get('pricingType', 'per plate'),
            'statusBadge': d.get('statusBadge', 'LIVE'),
            'batch_size': d.get('batch_size'),
            'base_recipe_qty': d.get('base_recipe_qty'),
        }


class MenuServiceSerializer(serializers.Serializer):
    """Normalized service line from ``Quotation.menu_services`` JSON (dict rows)."""

    def to_representation(self, instance):
        if not isinstance(instance, dict):
            return {
                'id': '',
                'name': '',
                'staff_count': 0,
                'counter_count': 0,
                'equipment_list': [],
            }
        d = instance
        eq = d.get('equipment_list')
        if eq is None:
            eq = []
        elif not isinstance(eq, list):
            eq = [eq]
        staff = d.get('staff_count')
        if staff is None and d.get('staff') is not None:
            staff = d.get('staff')
        counters = d.get('counter_count')
        if counters is None and d.get('counters') is not None:
            counters = d.get('counters')
        try:
            staff_count = int(staff) if staff is not None else 0
        except (TypeError, ValueError):
            staff_count = 0
        try:
            counter_count = int(counters) if counters is not None else 0
        except (TypeError, ValueError):
            counter_count = 0
        try:
            rate = float(d.get('rate') or 0)
        except (TypeError, ValueError):
            rate = 0.0
        try:
            qty = float(d.get('qty') or 1)
        except (TypeError, ValueError):
            qty = 1.0
        try:
            subtotal = float(d.get('subtotal') or 0)
        except (TypeError, ValueError):
            subtotal = 0.0
        return {
            'id': str(d.get('id') or ''),
            'name': str(d.get('name') or d.get('service_name') or ''),
            'rate': rate,
            'qty': qty,
            'subtotal': subtotal,
            'staff_count': staff_count,
            'counter_count': counter_count,
            'equipment_list': eq,
        }


class EventDetailsSerializer(serializers.ModelSerializer):
    """Read-only inquiry fields exposed as event details on a quotation."""

    client_name = serializers.CharField(source='customer_name', read_only=True)
    pax = serializers.IntegerField(source='guest_count', read_only=True)
    event_date = serializers.DateField(source='tentative_date', read_only=True)

    class Meta:
        model = Inquiry
        fields = ['client_name', 'event_type', 'pax', 'venue', 'event_date']
        read_only_fields = fields


class QuotationDetailSerializer(serializers.ModelSerializer):
    """Read-only quotation payload with nested event, menu snapshots, and pricing identifiers."""

    event = EventDetailsSerializer(source='inquiry', read_only=True, allow_null=True)
    menu_dishes = MenuDishSerializer(many=True, read_only=True)
    menu_services = MenuServiceSerializer(many=True, read_only=True)
    costing = serializers.JSONField(source='costing_data', read_only=True)
    total = serializers.DecimalField(
        max_digits=12,
        decimal_places=2,
        source='total_amount',
        read_only=True,
    )
    public_token = serializers.CharField(read_only=True)

    class Meta:
        model = Quotation
        fields = [
            'id',
            'version_number',
            'status',
            'is_locked',
            'event',
            'menu_dishes',
            'menu_services',
            'subtotal',
            'total',
            'costing',
            'final_selling_price',
            'internal_cost',
            'advance_amount',
            'payment_terms',
            'public_token',
            'pdf_url',
            'created_at',
        ]
        read_only_fields = fields

    def to_representation(self, instance):
        data = super().to_representation(instance)
        dishes = instance.menu_dishes if isinstance(instance.menu_dishes, list) else []
        services = instance.menu_services if isinstance(instance.menu_services, list) else []
        data['menu_dishes'] = MenuDishSerializer(dishes, many=True, context=self.context).data
        data['menu_services'] = MenuServiceSerializer(services, many=True, context=self.context).data
        token = data.get('public_token')
        if token is not None:
            data['public_token'] = str(token)
        return data


class PublicQuotationSerializer(serializers.Serializer):
    """
    Single merged public response: template bundle (type, branding, config) plus quotation detail.

    Pass ``instance`` as ``(quotation, template)`` or an object with ``quotation`` and
    ``template`` attributes. ``template`` may be ``None`` (empty template shell).
    ``context`` must include ``request`` when absolute media URLs are required.
    """

    def to_representation(self, instance):
        quotation, template = self._unpack(instance)
        ctx = self.context
        if template is None:
            template_payload = {
                'type': TemplateType.CLASSIC,
                'branding': {
                    'logo': '',
                    'hero_image': None,
                    'primary_color': '#1A1A1A',
                    'accent_color': '#C9A84C',
                    'font_heading': 'Playfair Display',
                    'font_body': 'Inter',
                    'company_tagline': '',
                    'about_text': '',
                    'why_choose_us': '',
                },
                'sections_config': {},
                'schema': {},
            }
        else:
            cfg = TemplateConfigSerializer(template, context=ctx).data
            template_payload = {
                'type': cfg['template_type'],
                'branding': BrandingSerializer(template, context=ctx).data,
                'sections_config': cfg['sections_config'],
                'schema': cfg['template_schema'],
            }
        return {
            'template': template_payload,
            'quotation': QuotationDetailSerializer(quotation, context=ctx).data,
        }

    def _unpack(self, instance):
        if isinstance(instance, (list, tuple)) and len(instance) == 2:
            return instance[0], instance[1]
        q = getattr(instance, 'quotation', None)
        t = getattr(instance, 'template', None)
        if q is not None:
            return q, t
        return instance, getattr(instance, 'template', None)


_HEX_COLOR = re.compile(r'^#[0-9A-Fa-f]{6}$')


class QuotationTemplateReadSerializer(serializers.ModelSerializer):
    """Tenant quotation template for list/retrieve: identity fields plus nested ``BrandingSerializer``."""

    branding = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = QuotationTemplate
        fields = [
            'id',
            'name',
            'template_type',
            'tenant',
            'is_active',
            'is_default',
            'branding',
            'sections_config',
            'template_schema',
            'created_at',
            'updated_at',
        ]
        read_only_fields = fields

    def get_branding(self, obj):
        return BrandingSerializer(obj, context=self.context).data


class QuotationTemplateWriteSerializer(serializers.ModelSerializer):
    """Partial/full update payload for template branding images, colors, copy, and layout JSON."""

    logo = serializers.ImageField(write_only=True, required=False, allow_null=True)

    class Meta:
        model = QuotationTemplate
        fields = [
            'logo',
            'hero_image',
            'primary_color',
            'accent_color',
            'font_heading',
            'font_body',
            'company_tagline',
            'about_text',
            'why_choose_us',
            'sections_config',
            'template_schema',
            'is_default',
        ]

    def validate_primary_color(self, value):
        if value in (None, ''):
            return value
        text = str(value).strip()
        if not _HEX_COLOR.match(text):
            raise serializers.ValidationError('Must be a valid hex color in #RRGGBB form.')
        return text

    def validate_accent_color(self, value):
        if value in (None, ''):
            return value
        text = str(value).strip()
        if not _HEX_COLOR.match(text):
            raise serializers.ValidationError('Must be a valid hex color in #RRGGBB form.')
        return text

    def validate_sections_config(self, value):
        if not isinstance(value, dict):
            raise serializers.ValidationError('Must be an object.')
        if 'sections' not in value or not isinstance(value['sections'], list):
            raise serializers.ValidationError('Must contain a "sections" key mapping to a list.')
        return value

    def update(self, instance, validated_data):
        logo_file = validated_data.pop('logo', serializers.empty)
        instance = super().update(instance, validated_data)
        if logo_file is not serializers.empty and logo_file is not None:
            _root, ext = os.path.splitext(getattr(logo_file, 'name', '') or '')
            ext = ext if ext else '.bin'
            key = f'quotation-templates/logos/{instance.pk}/{uuid.uuid4().hex}{ext}'
            saved_path = default_storage.save(key, logo_file)
            media_prefix = settings.MEDIA_URL.rstrip('/')
            rel = f'{media_prefix}/{saved_path.lstrip("/")}'
            request = self.context.get('request')
            instance.logo_url = request.build_absolute_uri(rel) if request else rel
            instance.save(update_fields=['logo_url', 'updated_at'])
        return instance
