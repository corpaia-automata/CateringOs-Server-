from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal

from django.db.models import DecimalField, F, Sum, Value
from django.db.models.functions import Coalesce
from django.utils import timezone

from apps.events.models import Event
from apps.quotations.models import Quotation


_quote_total = Coalesce(
    F('final_selling_price'),
    F('total_amount'),
    Value(Decimal('0')),
    output_field=DecimalField(max_digits=18, decimal_places=2),
)

APPROVED_QUOTATION_STATUSES = [
    Quotation.Status.SENT,
    Quotation.Status.ACCEPTED,
]


def _standalone_quotation_qs(tenant_id):
    """Quotations not already attached to an event (avoid double-counting revenue)."""
    linked = Event.objects.filter(tenant_id=tenant_id).exclude(quotation_id__isnull=True).values_list(
        'quotation_id', flat=True
    )
    return Quotation.objects.filter(tenant_id=tenant_id).exclude(id__in=linked)


def _quotation_line_sum_expr():
    return _quote_total


def _month_bounds():
    now = timezone.localdate()
    start = now.replace(day=1)
    if start.month == 12:
        next_month = start.replace(year=start.year + 1, month=1)
    else:
        next_month = start.replace(month=start.month + 1)
    return start, next_month


def monthly_revenue_components(tenant_id) -> tuple[Decimal, Decimal]:
    start, end = _month_bounds()
    event_revenue = (
        Event.objects.filter(tenant_id=tenant_id, event_date__gte=start, event_date__lt=end)
        .aggregate(v=Coalesce(Sum('total_amount'), Value(Decimal('0'))))['v']
    ) or Decimal('0')
    quotation_revenue = (
        _standalone_quotation_qs(tenant_id)
        .filter(
            status__in=APPROVED_QUOTATION_STATUSES,
            created_at__date__gte=start,
            created_at__date__lt=end,
        )
        .annotate(quote_total=_quotation_line_sum_expr())
        .aggregate(v=Coalesce(Sum('quote_total'), Value(Decimal('0'))))['v']
    ) or Decimal('0')
    return event_revenue, quotation_revenue


def pending_components(tenant_id) -> tuple[Decimal, Decimal]:
    event_pending = (
        Event.objects.filter(tenant_id=tenant_id)
        .annotate(total=Coalesce(F('total_amount'), Value(Decimal('0'))))
        .annotate(credited=Coalesce(F('credited_amount'), Coalesce(F('advance_amount'), Value(Decimal('0')))))
        .annotate(pending=F('total') - F('credited'))
        .filter(pending__gt=0)
        .aggregate(v=Coalesce(Sum('pending'), Value(Decimal('0'))))['v']
    ) or Decimal('0')

    # New quotation model has no payment fields — treat quotation pending as 0 until wired.
    quotation_pending = Decimal('0')

    return event_pending, quotation_pending


def events_per_day_last_7_days(tenant_id) -> list[dict]:
    today = timezone.localdate()
    start = today - timedelta(days=6)
    qs = (
        Event.objects.filter(tenant_id=tenant_id, event_date__gte=start, event_date__lte=today)
        .values('event_date')
        .order_by('event_date')
    )
    counts = {}
    for row in qs:
        key = row['event_date']
        counts[key] = counts.get(key, 0) + 1
    points = []
    for i in range(7):
        d = start + timedelta(days=i)
        points.append({'label': d.strftime('%a'), 'count': counts.get(d, 0)})
    return points


def revenue_trend(tenant_id, range_key: str) -> list[dict]:
    range_key = (range_key or 'weekly').lower()
    today = timezone.localdate()
    if range_key in {'daily', 'weekly'}:
        start = today - timedelta(days=6)
        event_qs = Event.objects.filter(tenant_id=tenant_id, event_date__gte=start, event_date__lte=today)
        quotation_qs = (
            _standalone_quotation_qs(tenant_id)
            .filter(
                status__in=APPROVED_QUOTATION_STATUSES,
                created_at__date__gte=start,
                created_at__date__lte=today,
            )
            .annotate(quote_total=_quotation_line_sum_expr())
        )
        bucket = {start + timedelta(days=i): Decimal('0') for i in range(7)}
        for event in event_qs.only('event_date', 'total_amount'):
            if event.event_date in bucket:
                bucket[event.event_date] += event.total_amount or Decimal('0')
        for quotation in quotation_qs:
            d = quotation.created_at.date()
            if d in bucket:
                bucket[d] += quotation.quote_total or Decimal('0')
        return [{'label': day.strftime('%a'), 'revenue': float(amount)} for day, amount in bucket.items()]

    start = today.replace(month=1, day=1)
    month_buckets = {m: Decimal('0') for m in range(1, today.month + 1)}
    for event in Event.objects.filter(tenant_id=tenant_id, event_date__gte=start, event_date__lte=today).only(
        'event_date', 'total_amount'
    ):
        if event.event_date:
            month_buckets[event.event_date.month] += event.total_amount or Decimal('0')
    for quotation in (
        _standalone_quotation_qs(tenant_id)
        .filter(
            status__in=APPROVED_QUOTATION_STATUSES,
            created_at__date__gte=start,
            created_at__date__lte=today,
        )
        .annotate(quote_total=_quotation_line_sum_expr())
    ):
        month_buckets[quotation.created_at.month] += quotation.quote_total or Decimal('0')
    return [
        {'label': datetime(2000, month, 1).strftime('%b'), 'revenue': float(amount)}
        for month, amount in month_buckets.items()
    ]
