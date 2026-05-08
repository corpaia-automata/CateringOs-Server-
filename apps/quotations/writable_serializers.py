"""Writable Model serializers for tenant-scoped quotation APIs."""

from decimal import Decimal

from rest_framework import serializers

from .models import BrandingProfile, Quotation, QuotationTemplate


class BrandingProfileSerializer(serializers.ModelSerializer):
    class Meta:
        model = BrandingProfile
        fields = [
            'id',
            'tenant',
            'business_name',
            'logo',
            'primary_color',
            'accent_color',
            'phone',
            'email',
            'website',
            'footer_text',
            'terms_text',
            'about_text',
            'created_at',
            'updated_at',
        ]
        read_only_fields = ['id', 'tenant', 'created_at', 'updated_at']


class QuotationSerializer(serializers.ModelSerializer):
    class Meta:
        model = Quotation
        fields = [
            'id',
            'tenant',
            'inquiry',
            'version_number',
            'status',
            'line_items',
            'manual_costs',
            'subtotal',
            'service_charge',
            'total_amount',
            'notes',
            'quote_number',
            'accepted_at',
            'quoted_by',
            'sent_at',
            'menu_dishes',
            'menu_services',
            'advance_amount',
            'final_selling_price',
            'internal_cost',
            'is_locked',
            'margin',
            'payment_terms',
            'credited_amount',
            'costing_data',
            'grocery_data',
            'pricing_data',
            'pdf_file',
            'pdf_url',
            'template_snapshot',
            'template',
            'public_token',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'tenant',
            'quote_number',
            'public_token',
            'pdf_url',
            'created_at',
            'updated_at',
        ]

    def validate_inquiry(self, inquiry):
        if inquiry is None:
            return inquiry
        request = self.context.get('request')
        tid = getattr(request.user, 'tenant_id', None) if request else None
        if tid and str(inquiry.tenant_id) != str(tid):
            raise serializers.ValidationError('Inquiry not found.')
        return inquiry

    def validate_template(self, template):
        if template is None:
            return None
        request = self.context.get('request')
        tid = getattr(request.user, 'tenant_id', None) if request else None
        if tid and str(template.tenant_id) != str(tid):
            raise serializers.ValidationError('Template does not belong to this workspace.')
        if template.is_deleted:
            return None
        return template

    def create(self, validated_data):
        from apps.tenants.models import Tenant

        from .services import next_quote_number
        from .template_defaults import ensure_quotation_template_for_new_quote

        request = self.context.get('request')
        tenant_id = request.user.tenant_id
        validated_data['tenant_id'] = tenant_id
        validated_data.setdefault('line_items', [])
        validated_data.setdefault('manual_costs', [])
        validated_data.setdefault('menu_dishes', [])
        validated_data.setdefault('menu_services', [])
        validated_data.setdefault('costing_data', {})
        validated_data.setdefault('grocery_data', {})
        validated_data.setdefault('pricing_data', {})
        validated_data['quote_number'] = next_quote_number(tenant_id)
        tenant = Tenant.objects.get(pk=tenant_id)
        explicit = validated_data.get('template')
        validated_data['template'] = ensure_quotation_template_for_new_quote(tenant, explicit)
        return Quotation.objects.create(**validated_data)

    def update(self, instance, validated_data):
        validated_data.pop('tenant', None)
        validated_data.pop('quote_number', None)
        validated_data.pop('public_token', None)
        return super().update(instance, validated_data)


class QuotationTemplateSerializer(serializers.ModelSerializer):
    tenant_name = serializers.CharField(source='tenant.name', read_only=True)

    class Meta:
        model = QuotationTemplate
        fields = [
            'id',
            'tenant',
            'tenant_name',
            'name',
            'template_type',
            'business_name',
            'tagline',
            'company_tagline',
            'logo_url',
            'phone',
            'offices',
            'primary_color',
            'accent_color',
            'footer_text',
            'pricing_style',
            'tax_percent',
            'advance_percent',
            'special_notes',
            'terms_clauses',
            'setup_fee_paid',
            'is_active',
            'is_default',
            'activated_at',
            'configured_by',
            'created_by',
            'cover_image_url',
            'hero_image',
            'font_family',
            'font_heading',
            'font_body',
            'about_text',
            'why_choose_us',
            'gallery_images',
            'background_color',
            'payment_terms',
            'cover_elements',
            'since_year',
            'sections_config',
            'template_schema',
            'created_at',
            'updated_at',
        ]
        read_only_fields = [
            'id',
            'tenant',
            'tenant_name',
            'activated_at',
            'configured_by',
            'created_by',
            'created_at',
            'updated_at',
        ]
