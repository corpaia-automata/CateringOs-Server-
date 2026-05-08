"""Seed ``QuotationTemplate`` rows per ``template_type`` (premium / classic / minimal)."""

from django.apps import apps
from django.core.management.base import BaseCommand

from apps.quotations.template_defaults import sync_default_quotation_templates_for_tenant


class Command(BaseCommand):
    help = (
        'Create default quotation templates (premium / classic / minimal). '
        'Does not activate templates unless none exists for that type (then activates first seed row only).'
    )

    def add_arguments(self, parser):
        parser.add_argument(
            '--tenant',
            dest='tenant_slug',
            default=None,
            help='Limit to this tenant slug (default: all tenants).',
        )
        parser.add_argument(
            '--dry-run',
            action='store_true',
            help='Print actions without writing to the database.',
        )

    def handle(self, *args, **options):
        Tenant = apps.get_model('tenants', 'Tenant')
        qs = Tenant.objects.all().order_by('slug')
        slug = options.get('tenant_slug')
        if slug:
            qs = qs.filter(slug=slug)
        if not qs.exists():
            self.stderr.write(self.style.WARNING('No tenants matched.'))
            return

        dry = options['dry_run']

        for tenant in qs:
            self.stdout.write(f'Tenant {tenant.slug} ({tenant.pk})')
            if dry:
                from apps.quotations.models import TemplateType
                from apps.quotations.template_defaults import DEFAULT_TEMPLATE_NAMES

                for tt in TemplateType:
                    self.stdout.write(f'  [{tt}] {DEFAULT_TEMPLATE_NAMES[tt]}')
            else:
                sync_default_quotation_templates_for_tenant(tenant)
                self.stdout.write(self.style.SUCCESS('  synced default templates'))

        if dry:
            self.stdout.write(self.style.WARNING('Dry run - no database changes.'))
