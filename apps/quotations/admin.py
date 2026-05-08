from urllib.parse import unquote

from django import forms
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect
from django.urls import path, reverse
from django.utils import timezone
from django.utils.translation import gettext_lazy as _

from apps.quotations.models import Quotation, QuotationTemplate


@admin.register(QuotationTemplate)
class QuotationTemplateAdmin(admin.ModelAdmin):
    change_form_template = 'admin/quotations/quotationtemplate/change_form.html'
    fieldsets = (
        (
            _('Identity'),
            {
                'fields': (
                    'tenant',
                    'name',
                    'template_type',
                    'is_active',
                    'is_default',
                    'configured_by',
                    'created_by',
                )
            },
        ),
        (
            _('Branding'),
            {
                'fields': (
                    'business_name',
                    'tagline',
                    'company_tagline',
                    'logo_url',
                    'phone',
                    'offices',
                    'primary_color',
                    'accent_color',
                    'background_color',
                    'font_family',
                    'font_heading',
                    'font_body',
                    'footer_text',
                    'cover_image_url',
                    'hero_image',
                    'since_year',
                    'about_text',
                    'why_choose_us',
                    'gallery_images',
                    'cover_elements',
                    'payment_terms',
                    'sections_config',
                    'template_schema',
                )
            },
        ),
        (
            _('Pricing defaults'),
            {
                'fields': (
                    'pricing_style',
                    'tax_percent',
                    'advance_percent',
                    'special_notes',
                    'terms_clauses',
                    'setup_fee_paid',
                )
            },
        ),
        (
            _('Timestamps'),
            {'fields': ('activated_at', 'created_at', 'updated_at'), 'classes': ('collapse',)},
        ),
    )
    list_display = ['name', 'business_name', 'tenant', 'template_type', 'is_active', 'updated_at']
    list_filter = ['template_type', 'is_active', 'tenant']
    search_fields = ['name', 'business_name', 'tenant__name']
    readonly_fields = ['created_at', 'updated_at']
    raw_id_fields = ['tenant', 'configured_by', 'created_by']

    def get_urls(self):
        return [
            path(
                '<path:object_id>/activate-builder/',
                self.admin_site.admin_view(self.activate_template_tier_view),
                name='quotation-template-activate-level',
            ),
        ] + super().get_urls()

    def change_view(self, request, object_id, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['is_activate_builder_url'] = (
            reverse('admin:quotation-template-activate-level', args=[unquote(object_id)])
            if object_id
            else None
        )
        return super().change_view(request, object_id, form_url, extra_context=extra_context)

    def add_view(self, request, form_url='', extra_context=None):
        extra_context = extra_context or {}
        extra_context['is_activate_builder_url'] = None
        return super().add_view(request, form_url, extra_context=extra_context)

    def activate_template_tier_view(self, request, object_id):
        obj = get_object_or_404(self.model.all_objects.filter(is_deleted=False), pk=object_id)
        if not self.has_change_permission(request, obj):
            raise PermissionDenied
        if not request.user.is_superuser:
            user_tid = getattr(request.user, 'tenant_id', None)
            if user_tid is None or str(obj.tenant_id) != str(user_tid):
                raise PermissionDenied(_('You may only activate templates for your tenant.'))
        with transaction.atomic():
            others = (
                self.model.all_objects.filter(
                    tenant_id=obj.tenant_id,
                    template_type=obj.template_type,
                    is_deleted=False,
                )
                .exclude(pk=obj.pk)
            )
            others.update(is_active=False)
            obj.is_active = True
            obj.activated_at = timezone.now()
            obj.save(update_fields=['is_active', 'activated_at', 'updated_at'])
        self.message_user(
            request,
            _('This template is now active for %(tier)s.') % {'tier': obj.get_template_type_display()},
            messages.SUCCESS,
        )
        return redirect(reverse('admin:quotations_quotationtemplate_change', args=[object_id]))


@admin.register(Quotation)
class MainQuotationAdmin(admin.ModelAdmin):
    list_display = ['quote_number', 'tenant', 'status', 'inquiry_id', 'created_at']
    list_filter = ['status', 'tenant']
    search_fields = ['quote_number', 'notes']
    raw_id_fields = ['tenant', 'inquiry', 'template', 'quoted_by']
