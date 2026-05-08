"""Production-hardening tests for default quotation templates and tenant onboarding."""

import uuid

from django.test import TestCase
from rest_framework.test import APIClient

from apps.authentication.models import User
from apps.quotations.models import QuotationTemplate, TemplateType
from apps.quotations.template_defaults import (
    DEFAULT_TEMPLATE_NAMES,
    ensure_tenant_default_quotation_template_fk,
    get_or_create_default_template,
)
from apps.quotations.writable_serializers import QuotationSerializer
from apps.tenants.models import Tenant


class DefaultQuotationTemplateAuditTests(TestCase):
    def test_onboard_without_default_template_sets_classic_and_fk(self):
        client = APIClient()
        email = f'onboard-{uuid.uuid4().hex[:8]}@example.com'
        resp = client.post(
            '/api/onboard/',
            {
                'companyName': 'Audit Catering Co',
                'email': email,
                'password': 'longsecurepass1',
                'country': 'IN',
            },
            format='json',
        )
        self.assertEqual(resp.status_code, 201, resp.content)
        slug = resp.json()['slug']
        tenant = Tenant.objects.get(slug=slug)
        self.assertEqual(tenant.default_template, 'classic')
        self.assertIsNotNone(tenant.default_quotation_template_id)
        self.assertEqual(tenant.default_quotation_template.template_type, TemplateType.CLASSIC)
        self.assertTrue(tenant.default_quotation_template.is_default)

    def test_quotation_create_without_template_uses_tenant_default(self):
        tenant = Tenant.objects.create(slug=f'qt-{uuid.uuid4().hex[:8]}', name='Quote Tenant')
        ensure_tenant_default_quotation_template_fk(tenant)
        user = User.objects.create_user(
            email=f'u-{uuid.uuid4().hex[:8]}@example.com',
            password='pw',
            tenant=tenant,
            first_name='A',
            last_name='B',
            role=User.Role.ADMIN,
        )
        class R:
            user = user

        ser = QuotationSerializer(data={}, context={'request': R()})
        ser.is_valid(raise_exception=True)
        q = ser.save()
        self.assertIsNotNone(q.template_id)
        self.assertEqual(q.template.template_type, tenant.default_template)

    def test_quotation_after_deleting_all_templates_recreates_classic(self):
        tenant = Tenant.objects.create(slug=f'del-{uuid.uuid4().hex[:8]}', name='Delete Templates Co')
        ensure_tenant_default_quotation_template_fk(tenant)
        QuotationTemplate.all_objects.filter(tenant_id=tenant.pk).delete()
        tenant.refresh_from_db()
        self.assertIsNone(tenant.default_quotation_template_id)

        user = User.objects.create_user(
            email=f'u2-{uuid.uuid4().hex[:8]}@example.com',
            password='pw',
            tenant=tenant,
            first_name='C',
            last_name='D',
            role=User.Role.ADMIN,
        )

        class R:
            user = user

        ser = QuotationSerializer(data={}, context={'request': R()})
        ser.is_valid(raise_exception=True)
        q = ser.save()
        self.assertIsNotNone(q.template_id)
        self.assertEqual(q.template.template_type, TemplateType.CLASSIC)
        self.assertFalse(q.template.is_deleted)

    def test_mismatch_default_template_char_vs_fk_is_auto_fixed(self):
        tenant = Tenant.objects.create(
            slug=f'mm-{uuid.uuid4().hex[:8]}',
            name='Mismatch Co',
            default_template=TemplateType.CLASSIC,
        )
        premium_tpl = get_or_create_default_template(tenant, TemplateType.PREMIUM)
        classic_tpl = get_or_create_default_template(tenant, TemplateType.CLASSIC)
        self.assertNotEqual(premium_tpl.pk, classic_tpl.pk)

        Tenant.objects.filter(pk=tenant.pk).update(
            default_template=TemplateType.CLASSIC,
            default_quotation_template_id=premium_tpl.pk,
        )
        tenant.refresh_from_db()
        self.assertEqual(tenant.default_quotation_template_id, premium_tpl.pk)

        ensure_tenant_default_quotation_template_fk(tenant)
        tenant.refresh_from_db()
        self.assertEqual(tenant.default_quotation_template_id, classic_tpl.pk)
        self.assertEqual(tenant.default_quotation_template.template_type, TemplateType.CLASSIC)
        self.assertEqual(
            tenant.default_quotation_template.name,
            DEFAULT_TEMPLATE_NAMES[TemplateType.CLASSIC],
        )
