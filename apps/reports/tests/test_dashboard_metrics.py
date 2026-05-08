import uuid
from datetime import date, datetime, timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from apps.events.models import Event
from apps.inquiries.models import Inquiry
from apps.quotations.models import Quotation
from apps.reports.services import dashboard_payload
from apps.tenants.models import Tenant


class TestDashboardMetrics(TestCase):
    def setUp(self):
        self.tenant = Tenant.objects.create(slug='tenant-a', name='Tenant A')
        self.today = date.today()
        self.inquiry = Inquiry.objects.create(
            tenant=self.tenant,
            customer_name='Client One',
            source_channel='PHONE_CALL',
            event_type='Wedding',
            tentative_date=self.today,
            guest_count=100,
            status='PLANNING',
        )

    def _quotation(self, **overrides):
        base = {
            'tenant': self.tenant,
            'quote_number': f'QTN-{uuid.uuid4().hex[:6]}',
            'status': Quotation.Status.SENT,
            'final_selling_price': Decimal('1200.00'),
            'total_amount': Decimal('1200.00'),
        }
        base.update(overrides)
        return Quotation.objects.create(**base)

    def _event(self, **overrides):
        payload = {
            'tenant': self.tenant,
            'inquiry': self.inquiry,
            'customer_name': 'Client One',
            'event_type': 'Wedding',
            'event_date': self.today,
            'guest_count': 100,
            'service_type': Event.ServiceType.BUFFET,
            'status': Event.Status.CONFIRMED,
            'total_amount': Decimal('2000.00'),
            'credited_amount': Decimal('500.00'),
        }
        payload.update(overrides)
        return Event.objects.create(**payload)

    def test_dashboard_counts_quotation_without_event(self):
        self._quotation(final_selling_price=Decimal('1200.00'), total_amount=Decimal('1200.00'))
        data = dashboard_payload(self.tenant.id)
        self.assertEqual(data['monthly_revenue'], Decimal('1200.00'))
        self.assertEqual(data['pending_payment_amount'], Decimal('0.00'))

    def test_dashboard_counts_event_without_quotation(self):
        self._event(total_amount=Decimal('2500.00'), credited_amount=Decimal('900.00'))
        data = dashboard_payload(self.tenant.id)
        self.assertEqual(data['monthly_revenue'], Decimal('2500.00'))
        self.assertEqual(data['pending_payment_amount'], Decimal('1600.00'))

    def test_dashboard_avoids_double_count_for_converted_quotation(self):
        quotation = self._quotation(final_selling_price=Decimal('1400.00'), total_amount=Decimal('1400.00'))
        self._event(quotation=quotation, total_amount=Decimal('1400.00'), credited_amount=Decimal('300.00'))
        data = dashboard_payload(self.tenant.id)
        self.assertEqual(data['monthly_revenue'], Decimal('1400.00'))
        self.assertEqual(data['pending_payment_amount'], Decimal('1100.00'))

    def test_pending_never_adds_negative_values(self):
        self._quotation(final_selling_price=Decimal('1000.00'))
        self._event(total_amount=Decimal('800.00'), credited_amount=Decimal('900.00'))
        data = dashboard_payload(self.tenant.id)
        self.assertEqual(data['pending_payment_amount'], Decimal('0.00'))

    def test_dashboard_limits_monthly_revenue_to_current_month(self):
        prev_month_date = self.today - timedelta(days=40)
        old_inquiry = Inquiry.objects.create(
            tenant=self.tenant,
            customer_name='Client Old',
            source_channel='PHONE_CALL',
            event_type='Corporate',
            tentative_date=prev_month_date,
            guest_count=50,
            status='PLANNING',
        )
        old_quotation = Quotation.objects.create(
            tenant=self.tenant,
            quote_number=f'QTN-{uuid.uuid4().hex[:6]}',
            status=Quotation.Status.SENT,
            final_selling_price=Decimal('3000.00'),
            total_amount=Decimal('3000.00'),
        )
        old_quotation.created_at = timezone.make_aware(datetime.combine(prev_month_date, datetime.min.time()))
        old_quotation.save(update_fields=['created_at'])
        Event.objects.create(
            tenant=self.tenant,
            inquiry=old_inquiry,
            customer_name='Client Old',
            event_type='Corporate',
            event_date=prev_month_date,
            guest_count=50,
            service_type=Event.ServiceType.BUFFET,
            status=Event.Status.CONFIRMED,
            total_amount=Decimal('2500.00'),
            credited_amount=Decimal('200.00'),
        )
        data = dashboard_payload(self.tenant.id)
        self.assertEqual(data['monthly_revenue'], Decimal('0.00'))
