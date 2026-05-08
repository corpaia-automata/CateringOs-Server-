"""Tests snapshot hydration when linking a quotation to an event from lead convert."""
import uuid
from datetime import date
from decimal import Decimal

from django.test import TestCase

from apps.events.models import Event
from apps.inquiries.models import Inquiry
from apps.inquiries.services import (
    apply_quotation_pricing_to_event,
    filter_quotation_dishes_for_convert,
    filter_quotation_services_for_convert,
    seed_event_execution_from_quotation,
)
from apps.quotations.models import Quotation
from apps.tenants.models import Tenant


class ConvertSnapshotTests(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(slug='convert-snaps', name='Convert Snaps Co')
        self.inquiry = Inquiry.objects.create(
            tenant=self.tenant,
            customer_name='Taylor Client',
            source_channel=Inquiry.SourceChannel.PHONE_CALL,
            event_type='Reception',
            tentative_date=date.today(),
            guest_count=120,
            status=Inquiry.Status.PLANNING,
        )

    def test_filters_drop_invalid_duplicate_dishes(self):
        raw = [
            {'name': 'Valid', 'qty': 10, 'rate': '100'},  # good
            {'name': '', 'quantity': 1},                   # missing name
            {'name': 'Zero', 'quantity': 0},               # bad qty
            {'name': 'Valid', 'quantity': '5'},            # dup name (skipped)
            'not-a-dict',
        ]
        out = filter_quotation_dishes_for_convert(raw)
        self.assertEqual(len(out), 1)
        self.assertEqual(out[0]['name'], 'Valid')

    def test_filters_keep_valid_services(self):
        raw = [
            {'name': 'Stage', 'qty': 1, 'rate': 5000},
            {'service_name': 'Lighting', 'quantity': '2'},  # name fallback
            {'name': 'Bad', 'qty': 0},  # qty 0 -> drop
        ]
        out = filter_quotation_services_for_convert(raw)
        self.assertEqual(len(out), 2)
        labels = sorted(
            str(r.get('name') or r.get('service_name') or '') for r in out
        )
        self.assertEqual(labels, sorted(['Stage', 'Lighting']))

    def test_seed_and_pricing_snapshot_from_quotation(self):
        quotation = Quotation.objects.create(
            tenant=self.tenant,
            quote_number=f'QTN-{uuid.uuid4().hex[:6]}',
            inquiry=self.inquiry,
            menu_dishes=[
                {
                    'name': 'Main Course Tray',
                    'quantity': Decimal('80'),
                    'unit': 'plate',
                    'rate': Decimal('200'),
                },
            ],
            menu_services=[
                {'name': 'Hall Setup', 'qty': Decimal('1'), 'rate': Decimal('2500'), 'unit': 'unit'},
            ],
            advance_amount=Decimal('5000.00'),
            final_selling_price=Decimal('25000.00'),
        )

        event = Event.objects.create(
            tenant=self.tenant,
            inquiry=self.inquiry,
            customer_name=self.inquiry.customer_name,
            event_type=self.inquiry.event_type,
            event_date=self.inquiry.tentative_date,
            guest_count=self.inquiry.guest_count,
            service_type=Event.ServiceType.OTHER,
            status=Event.Status.CONFIRMED,
            quotation=quotation,
            total_amount=Decimal('9000.00'),
            advance_amount=Decimal('0.00'),
        )

        ev = seed_event_execution_from_quotation(event, quotation, user=None)
        ev = apply_quotation_pricing_to_event(ev, quotation, user=None)
        ev.refresh_from_db()

        menu_items = ev.menu_snapshot.get('items')
        self.assertTrue(isinstance(menu_items, list) and len(menu_items) == 1)
        self.assertEqual(menu_items[0]['name'], 'Main Course Tray')

        service_items = ev.services_snapshot.get('items')
        self.assertTrue(isinstance(service_items, list) and len(service_items) == 1)
        self.assertEqual(service_items[0]['name'], 'Hall Setup')

        self.assertIn('items', ev.costing_snapshot)
        self.assertEqual(ev.advance_amount, Decimal('5000.00'))
        self.assertEqual(ev.total_amount, Decimal('25000.00'))
