import uuid

from django.conf import settings
from django.db import models
from django.utils.translation import gettext_lazy as _

from shared.mixins import BaseMixin


class BrandingProfile(models.Model):
    """Legacy branding row (optional). May not exist in all databases."""

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='branding_profiles',
        db_column='tenant_id',
    )
    business_name = models.CharField(max_length=200)
    logo = models.ImageField(upload_to='branding/logos/%Y/%m/', blank=True)
    primary_color = models.CharField(max_length=7, default='#1a1a1a')
    accent_color = models.CharField(max_length=7, default='#4f46e5')
    phone = models.CharField(max_length=30, blank=True)
    email = models.EmailField(blank=True)
    website = models.URLField(blank=True)
    footer_text = models.CharField(max_length=300, blank=True)
    terms_text = models.TextField(blank=True)
    about_text = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    def __str__(self):
        return f'{self.business_name} ({self.tenant_id})'


class TemplateType(models.TextChoices):
    CLASSIC = 'classic', _('Classic')
    PREMIUM = 'premium', _('Premium')
    MINIMAL = 'minimal', _('Minimal')


class QuotationTemplate(BaseMixin):
    """Tenant quotation PDF/HTML skin: branding, ``template_type``, and JSON layout config."""

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.CASCADE,
        related_name='quotation_templates',
        db_column='tenant_id',
    )
    name = models.CharField(max_length=200)
    template_type = models.CharField(
        max_length=20,
        choices=TemplateType.choices,
        default=TemplateType.CLASSIC,
    )

    business_name = models.CharField(max_length=200)
    tagline = models.CharField(blank=True, max_length=200)
    company_tagline = models.CharField(max_length=200, blank=True)
    logo_url = models.URLField(blank=True)
    phone = models.CharField(blank=True, max_length=30)
    offices = models.CharField(blank=True, max_length=300)
    primary_color = models.CharField(max_length=7, default='#1A1A1A')
    accent_color = models.CharField(max_length=7, default='#C9A84C')
    footer_text = models.CharField(blank=True, max_length=300)
    pricing_style = models.CharField(
        max_length=20,
        default='simple_total',
    )
    tax_percent = models.DecimalField(max_digits=4, decimal_places=1, default=5.0)
    advance_percent = models.DecimalField(max_digits=4, decimal_places=1, default=50.0)
    special_notes = models.JSONField(default=list, blank=True)
    terms_clauses = models.JSONField(default=list, blank=True)
    setup_fee_paid = models.BooleanField(default=False)
    is_active = models.BooleanField(default=False)
    is_default = models.BooleanField(default=False)
    activated_at = models.DateTimeField(null=True, blank=True)
    configured_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='configured_quote_templates',
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='quotation_templates_created',
    )
    cover_image_url = models.CharField(blank=True, default='', max_length=500)
    hero_image = models.ImageField(upload_to='heroes/', null=True, blank=True)
    font_family = models.CharField(blank=True, max_length=120)
    font_heading = models.CharField(max_length=50, default='Playfair Display')
    font_body = models.CharField(max_length=50, default='Inter')
    about_text = models.TextField(blank=True)
    why_choose_us = models.TextField(blank=True)
    gallery_images = models.JSONField(default=list, blank=True)
    background_color = models.CharField(blank=True, max_length=7, default='#ffffff')
    payment_terms = models.TextField(blank=True)
    cover_elements = models.JSONField(default=list, blank=True)
    since_year = models.CharField(blank=True, default='2013', max_length=4)
    sections_config = models.JSONField(default=dict, blank=True)
    template_schema = models.JSONField(default=dict, blank=True)

    class Meta:
        db_table = 'quotation_templates'
        ordering = ['tenant_id', 'name']
        unique_together = [['tenant', 'name']]
        verbose_name = _('Quotation template')
        verbose_name_plural = _('Quotation templates')

    def __str__(self):
        return f'{self.name} ({self.tenant_id})'


class Quotation(BaseMixin):
    class Status(models.TextChoices):
        DRAFT = 'draft', _('Draft')
        SENT = 'sent', _('Sent')
        ACCEPTED = 'accepted', _('Accepted')
        REJECTED = 'rejected', _('Rejected')

    tenant = models.ForeignKey(
        'tenants.Tenant',
        on_delete=models.PROTECT,
        related_name='quotations',
        db_column='tenant_id',
    )
    version_number = models.PositiveIntegerField(default=1)
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.DRAFT)
    line_items = models.JSONField(default=list)
    manual_costs = models.JSONField(default=list)
    subtotal = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    service_charge = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    total_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    notes = models.TextField(blank=True)
    quote_number = models.CharField(max_length=50, blank=True, editable=False)
    accepted_at = models.DateTimeField(null=True, blank=True)
    inquiry = models.ForeignKey(
        'inquiries.Inquiry',
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name='quotations',
        db_column='inquiry_id',
    )
    quoted_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='quotations_created',
        db_column='quoted_by_id',
    )
    sent_at = models.DateTimeField(null=True, blank=True)
    menu_dishes = models.JSONField(default=list)
    menu_services = models.JSONField(default=list)
    advance_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    final_selling_price = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    internal_cost = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    is_locked = models.BooleanField(default=False)
    margin = models.DecimalField(max_digits=6, decimal_places=2, default=0)
    payment_terms = models.TextField(blank=True)
    credited_amount = models.DecimalField(max_digits=12, decimal_places=2, default=0)
    costing_data = models.JSONField(default=dict)
    grocery_data = models.JSONField(default=dict)
    pricing_data = models.JSONField(default=dict)
    pdf_file = models.CharField(max_length=500, blank=True, default='')
    pdf_url = models.URLField(max_length=500, null=True, blank=True)
    template_snapshot = models.JSONField(null=True, blank=True)
    template = models.ForeignKey(
        QuotationTemplate,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='quotations',
        db_column='template_id',
    )
    public_token = models.UUIDField(default=uuid.uuid4, editable=False, unique=True)

    class Meta:
        db_table = 'quotations'
        ordering = ['-created_at']
        unique_together = [['tenant', 'quote_number']]

    def __str__(self):
        return f'{self.quote_number or self.id} — tenant {self.tenant_id}'
