"""
Operations dashboard context for Django Admin index.

Patches AdminSite.index. Metrics assume:
- Revenue (today / MTD): sum of confirmed+ event ``total_amount`` by ``event_date``,
  plus approved standalone quotations in-window (reports.selectors semantics).
- Pending aging: overdue receivables by ``event_date`` vs today (fallback: omit null dates
  or use created date in a separate line); buckets are days since event when balance > 0.
- Follow-up / contact: no ``contacted_at`` on Inquiry — use stale ``updated_at`` on PLANNING.
"""
from __future__ import annotations

from datetime import timedelta
from decimal import Decimal
from typing import Any

from django.apps import apps
from django.contrib.admin.sites import AdminSite
from django.contrib.auth import get_permission_codename
from django.db.models import Count, DecimalField, Exists, F, OuterRef, Sum, Value
from django.db.models.functions import Coalesce
from django.urls import reverse
from django.utils import timezone

from apps.events.models import Event
from apps.inquiries.models import Inquiry
from apps.quotations.models import Quotation
from apps.reports.selectors import (
    APPROVED_QUOTATION_STATUSES,
    _quote_total,
    _standalone_quotation_qs,
)

_money_field = DecimalField(max_digits=18, decimal_places=2)

_FUNNEL_WINDOW_DAYS = 90


def patch_admin_index(site: AdminSite) -> None:
    _orig = site.index

    def index(request, extra_context=None):
        extra_context = extra_context or {}
        extra_context.update(get_operations_dashboard_context(request))
        return _orig(request, extra_context)

    site.index = index  # type: ignore[method-assign]


def _tenant_id_for_request(user) -> Any | None:
    if user.is_superuser:
        return None
    return getattr(user, 'tenant_id', None)


def _events_queryset(user):
    qs = Event.objects.all()
    tid = _tenant_id_for_request(user)
    if tid is None:
        return qs if user.is_superuser else Event.objects.none()
    return qs.filter(tenant_id=tid)


def _inquiries_queryset(user):
    qs = Inquiry.objects.all()
    tid = _tenant_id_for_request(user)
    if tid is None:
        return qs if user.is_superuser else Inquiry.objects.none()
    return qs.filter(tenant_id=tid)


def _quotations_queryset(user):
    qs = Quotation.objects.all()
    tid = _tenant_id_for_request(user)
    if tid is None:
        return qs if user.is_superuser else Quotation.objects.none()
    return qs.filter(tenant_id=tid)


def _revenue_events_qs(user):
    """Events that count toward booked / recognized revenue (not draft / cancelled)."""
    return _events_queryset(user).filter(
        status__in=[Event.Status.CONFIRMED, Event.Status.IN_PROGRESS, Event.Status.COMPLETED],
    )


def _total_revenue(*, user) -> Decimal:
    event_qs = _events_queryset(user).exclude(status=Event.Status.CANCELLED)
    event_part = event_qs.aggregate(v=Coalesce(Sum('total_amount'), Value(Decimal('0'))))['v'] or Decimal('0')

    tid = _tenant_id_for_request(user)
    if tid is not None:
        q_part = (
            _standalone_quotation_qs(tid)
            .filter(status__in=APPROVED_QUOTATION_STATUSES)
            .annotate(quote_total=_quote_total)
            .aggregate(v=Coalesce(Sum('quote_total'), Value(Decimal('0'))))['v']
        ) or Decimal('0')
        return event_part + q_part

    if not user.is_superuser:
        return Decimal('0')

    linked = Event.objects.filter(quotation_id__isnull=False).values_list('quotation_id', flat=True)
    q_part = (
        Quotation.objects.exclude(id__in=linked)
        .filter(status__in=APPROVED_QUOTATION_STATUSES)
        .annotate(quote_total=_quote_total)
        .aggregate(v=Coalesce(Sum('quote_total'), Value(Decimal('0'))))['v']
    ) or Decimal('0')
    return event_part + q_part


def _event_revenue_sum(event_qs) -> Decimal:
    return event_qs.aggregate(v=Coalesce(Sum('total_amount'), Value(Decimal('0'))))['v'] or Decimal('0')


def _standalone_quote_revenue_sum(*, user, start_d, end_d_inclusive) -> Decimal:
    """Approved standalone quotations with created_at date in [start_d, end_d_inclusive]."""
    tid = _tenant_id_for_request(user)
    if tid is not None:
        base = _standalone_quotation_qs(tid).filter(
            status__in=APPROVED_QUOTATION_STATUSES,
            created_at__date__gte=start_d,
            created_at__date__lte=end_d_inclusive,
        )
    elif user.is_superuser:
        linked = Event.objects.filter(quotation_id__isnull=False).values_list('quotation_id', flat=True)
        base = (
            Quotation.objects.exclude(id__in=linked)
            .filter(
                status__in=APPROVED_QUOTATION_STATUSES,
                created_at__date__gte=start_d,
                created_at__date__lte=end_d_inclusive,
            )
        )
    else:
        return Decimal('0')
    return (
        base.annotate(quote_total=_quote_total).aggregate(v=Coalesce(Sum('quote_total'), Value(Decimal('0'))))['v']
        or Decimal('0')
    )


def _pending_balance_sum(event_qs) -> Decimal:
    return (
        event_qs.exclude(status=Event.Status.CANCELLED)
        .annotate(total=Coalesce(F('total_amount'), Value(Decimal('0')), output_field=_money_field))
        .annotate(
            credited=Coalesce(
                F('credited_amount'),
                Coalesce(F('advance_amount'), Value(Decimal('0'))),
                output_field=_money_field,
            ),
        )
        .annotate(pending=F('total') - F('credited'))
        .filter(pending__gt=0)
        .aggregate(v=Coalesce(Sum('pending'), Value(Decimal('0')), output_field=_money_field))['v']
    ) or Decimal('0')


def _pending_collections_amount(event_qs) -> Decimal:
    return _pending_balance_sum(event_qs)


def _month_bounds_local():
    now = timezone.localdate()
    start = now.replace(day=1)
    if start.month == 12:
        next_m = start.replace(year=start.year + 1, month=1)
    else:
        next_m = start.replace(month=start.month + 1)
    return start, next_m


def _fmt_money(v: Decimal) -> str:
    return f'{v.quantize(Decimal("0.01")):,.2f}'


def _safe_pct(part: int, whole: int) -> float:
    if not whole:
        return 0.0
    return round(100.0 * part / whole, 1)


def _funnel_metrics(leads_window) -> dict[str, Any]:
    """Cohort-style funnel on Inquiry rows in rolling window."""

    quot_any = Quotation.objects.filter(inquiry_id=OuterRef('pk'))

    L = leads_window.count()
    Q_leads = leads_window.annotate(has_q=Exists(quot_any)).filter(has_q=True)
    Q_cnt = Q_leads.count()
    E_cnt = leads_window.filter(converted_event__isnull=False).count()
    E_from_Q_cnt = Q_leads.filter(converted_event__isnull=False).count()
    P_cnt = leads_window.filter(
        converted_event__payment_status=Event.PaymentStatus.FULLY_PAID,
    ).count()

    return {
        'window_days': _FUNNEL_WINDOW_DAYS,
        'leads': L,
        'with_quotation': Q_cnt,
        'with_event': E_cnt,
        'events_from_quoted_leads': E_from_Q_cnt,
        'fully_paid': P_cnt,
        'pct_lead_to_quote': _safe_pct(Q_cnt, L),
        'pct_quote_to_event': _safe_pct(E_from_Q_cnt, Q_cnt),
        'pct_event_to_paid': _safe_pct(P_cnt, E_cnt),
        'note': 'Paid uses payment_status=Fully Paid. Prefer balance==0 when credits are reliable.',
    }


def _admin_row_event(e: Event, *, meta_lines: list[str] | None = None) -> dict[str, Any]:
    return {
        'label': f'{e.event_code} · {e.customer_name}',
        'meta': ' · '.join(meta_lines) if meta_lines else '',
        'url': reverse('admin:events_event_change', args=[e.pk]),
    }


def _admin_row_inquiry(i: Inquiry) -> dict[str, Any]:
    return {
        'label': f'{i.customer_name} · {i.tentative_date}',
        'meta': str(i.get_status_display()),
        'url': reverse('admin:inquiries_inquiry_change', args=[i.pk]),
    }


def _changelist(model, **params) -> str:
    """Build admin changelist URL with query string."""
    from urllib.parse import urlencode

    key = f'admin:{model._meta.app_label}_{model._meta.model_name}_changelist'
    base = reverse(key)
    if not params:
        return base
    return f'{base}?{urlencode(params)}'


def _action_links(request) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """Create links + curated changelist URLs for ops triage."""

    creates: list[dict[str, Any]] = []
    fixes: list[dict[str, Any]] = []

    for app_label, model_name, label in (
        ('inquiries', 'Inquiry', 'Create lead'),
        ('quotations', 'Quotation', 'Create quotation'),
        ('events', 'Event', 'Create event'),
    ):
        try:
            model = apps.get_model(app_label, model_name)
        except LookupError:
            continue
        codename = get_permission_codename('add', model._meta)
        if request.user.has_perm(f'{model._meta.app_label}.{codename}'):
            mn = model._meta.model_name
            al = model._meta.app_label
            creates.append({'label': label, 'url': reverse(f'admin:{al}_{mn}_add')})

    inquiry_model = apps.get_model('inquiries', 'Inquiry')
    quot_model = apps.get_model('quotations', 'Quotation')
    event_model = apps.get_model('events', 'Event')

    if request.user.has_perm('inquiries.view_inquiry'):
        fixes.append(
            {
                'label': 'Planning leads · sort newest',
                'url': _changelist(inquiry_model, status__exact=Inquiry.Status.PLANNING, o='-1'),
            }
        )
        fixes.append(
            {
                'label': 'Lost inquiries',
                'url': _changelist(inquiry_model, status__exact=Inquiry.Status.LOST, o='-7'),
            }
        )
    if request.user.has_perm('quotations.view_quotation'):
        fixes.append(
            {
                'label': 'Quotes awaiting reply (sent)',
                'url': _changelist(quot_model, status__exact=Quotation.Status.SENT, o='-5'),
            }
        )
        fixes.append(
            {
                'label': 'Draft quotations',
                'url': _changelist(quot_model, status__exact=Quotation.Status.DRAFT, o='-5'),
            }
        )
    if request.user.has_perm('events.view_event'):
        fixes.append(
            {
                'label': 'Events marked payment pending',
                'url': _changelist(event_model, payment_status__exact=Event.PaymentStatus.PENDING, o='3'),
            }
        )
        fixes.append(
            {
                'label': 'Events with no quotation link (filter · eyeball stage)',
                'url': _changelist(event_model, quotation__isnull=True),
            }
        )

    return creates, fixes


def get_operations_dashboard_context(request) -> dict[str, Any]:
    user = request.user
    today = timezone.localdate()
    now = timezone.now()
    events = _events_queryset(user)
    inquiries = _inquiries_queryset(user)
    quotations = _quotations_queryset(user)
    rev_ev = _revenue_events_qs(user)

    leads_count = inquiries.count()
    events_count = events.count()
    revenue_life = _total_revenue(user=user)
    pending_total = _pending_collections_amount(events)

    start_m, next_m = _month_bounds_local()
    revenue_today_events = _event_revenue_sum(rev_ev.filter(event_date=today))
    revenue_today_quotes = _standalone_quote_revenue_sum(user=user, start_d=today, end_d_inclusive=today)
    revenue_today = revenue_today_events + revenue_today_quotes

    revenue_mtd_events = _event_revenue_sum(rev_ev.filter(event_date__gte=start_m, event_date__lt=next_m))
    revenue_mtd_quotes = _standalone_quote_revenue_sum(user=user, start_d=start_m, end_d_inclusive=today)
    revenue_mtd = revenue_mtd_events + revenue_mtd_quotes

    base_pending = (
        events.exclude(status=Event.Status.CANCELLED)
        .annotate(total=Coalesce(F('total_amount'), Value(Decimal('0')), output_field=_money_field))
        .annotate(
            credited=Coalesce(
                F('credited_amount'),
                Coalesce(F('advance_amount'), Value(Decimal('0'))),
                output_field=_money_field,
            ),
        )
        .annotate(pending=F('total') - F('credited'))
        .filter(pending__gt=0)
    )

    d7 = today - timedelta(days=7)
    d30 = today - timedelta(days=30)

    overdue_7 = _pending_balance_sum(
        base_pending.filter(event_date__lt=today, event_date__gte=d7),
    )
    overdue_8_30 = _pending_balance_sum(
        base_pending.filter(event_date__lt=d7, event_date__gte=d30),
    )
    overdue_31 = _pending_balance_sum(base_pending.filter(event_date__lt=d30))
    ambiguous_date_pending = _pending_balance_sum(base_pending.filter(event_date__isnull=True))

    funnel_cutoff = now - timedelta(days=_FUNNEL_WINDOW_DAYS)
    funnel = _funnel_metrics(inquiries.filter(created_at__gte=funnel_cutoff))

    leads_today = inquiries.filter(created_at__date=today).count()
    stale_hours_48 = now - timedelta(hours=48)
    stale_planning = inquiries.filter(status=Inquiry.Status.PLANNING, updated_at__lte=stale_hours_48).count()
    quotations_awaiting = quotations.filter(status=Quotation.Status.SENT).count()
    lost_window = inquiries.filter(status=Inquiry.Status.LOST, updated_at__gte=now - timedelta(days=30)).count()

    tom = today + timedelta(days=1)
    week_end = today + timedelta(days=6)

    load_today = events.filter(event_date=today).exclude(status=Event.Status.CANCELLED).count()
    load_tomorrow = events.filter(event_date=tom).exclude(status=Event.Status.CANCELLED).count()
    load_week = (
        events.filter(event_date__gte=today, event_date__lte=week_end)
        .exclude(status=Event.Status.CANCELLED)
        .count()
    )

    busy_dates = (
        events.filter(event_date__gte=today, event_date__lte=week_end)
        .exclude(status=Event.Status.CANCELLED)
        .values('event_date')
        .annotate(n=Count('id'))
        .filter(n__gt=1)
        .order_by('event_date')[:12]
    )
    busy_dates_list = [{'date': row['event_date'], 'count': row['n']} for row in busy_dates]

    alerts: list[dict[str, Any]] = []

    overdue_full = base_pending.filter(event_date__lt=today).exclude(event_date__isnull=True)
    overdue_cnt = overdue_full.count()
    if overdue_cnt:
        overdue_rows = list(overdue_full.select_related('tenant').order_by('event_date')[:6])
        alerts.append(
            {
                'level': 'danger',
                'title': 'Overdue balances (past event date, money still owed)',
                'count': overdue_cnt,
                'rows': [
                    _admin_row_event(
                        e,
                        meta_lines=[
                            f'past event · {e.event_date}',
                            e.get_payment_status_display() or 'Payment unset',
                        ],
                    )
                    for e in overdue_rows
                ],
                'more_url': _changelist(apps.get_model('events', 'Event'), payment_status__exact='PENDING', o='3')
                if user.has_perm('events.view_event')
                else '',
            }
        )

    no_quote_full = (
        events.filter(
            quotation__isnull=True,
            status__in=[
                Event.Status.CONFIRMED,
                Event.Status.IN_PROGRESS,
                Event.Status.COMPLETED,
            ],
        ).order_by('event_date')
    )
    no_quote_cnt = no_quote_full.count()
    if no_quote_cnt:
        no_quote_slice = list(no_quote_full.select_related('tenant')[:6])
        alerts.append(
            {
                'level': 'warning',
                'title': 'Events without linked quotation',
                'count': no_quote_cnt,
                'rows': [
                    _admin_row_event(e, meta_lines=[e.get_status_display(), str(e.event_date or '—')])
                    for e in no_quote_slice
                ],
                'more_url': _changelist(apps.get_model('events', 'Event'), quotation__isnull=True)
                if user.has_perm('events.view_event')
                else '',
            }
        )

    if stale_planning:
        stale_rows = list(
            inquiries.filter(status=Inquiry.Status.PLANNING, updated_at__lte=stale_hours_48).order_by('updated_at')[
                :6
            ]
        )
        alerts.append(
            {
                'level': 'warning',
                'title': 'Leads needing follow-up (planning · inactive 48h+)',
                'count': stale_planning,
                'rows': [_admin_row_inquiry(i) for i in stale_rows],
                'more_url': _changelist(apps.get_model('inquiries', 'Inquiry'), status__exact=Inquiry.Status.PLANNING, o='-7')
                if user.has_perm('inquiries.view_inquiry')
                else '',
            }
        )

    recent_qs = quotations.select_related('tenant', 'inquiry', 'quoted_by').order_by('-created_at')[:5]
    recent_quotations = [
        {
            'label': (q.quote_number or str(q.pk))[:80],
            'status': q.get_status_display(),
            'total': q.total_amount,
            'updated': q.updated_at,
            'change_url': reverse('admin:quotations_quotation_change', args=[q.pk]),
        }
        for q in recent_qs
    ]

    upcoming_qs = (
        events.filter(event_date__gte=today)
        .exclude(status=Event.Status.CANCELLED)
        .select_related('tenant')
        .order_by('event_date', 'event_time')[:5]
    )
    upcoming_events = [
        {
            'code': e.event_code,
            'customer': e.customer_name,
            'when': e.event_date,
            'venue': (e.venue or '')[:60],
            'change_url': reverse('admin:events_event_change', args=[e.pk]),
        }
        for e in upcoming_qs
    ]

    scope = 'All tenants' if user.is_superuser else 'This tenant'
    kpis = [
        {'key': 'leads', 'label': 'Total leads', 'value': f'{leads_count:,}', 'hint': 'Inquiries'},
        {'key': 'events', 'label': 'Total events', 'value': f'{events_count:,}', 'hint': 'All events'},
        {'key': 'revenue', 'label': 'Lifetime revenue', 'value': _fmt_money(revenue_life), 'hint': 'Events + approved quotes'},
        {'key': 'pending', 'label': 'Pending collections', 'value': _fmt_money(pending_total), 'hint': 'Receivable balance'},
    ]

    creates, fixes = _action_links(request)

    return {
        'ops_scope_label': scope,
        'ops_kpis': kpis,
        'ops_revenue': {
            'today': _fmt_money(revenue_today),
            'month': _fmt_money(revenue_mtd),
            'aging': [
                {'key': 'b1', 'label': '0–7 days past event', 'value': _fmt_money(overdue_7)},
                {'key': 'b2', 'label': '8–30 days past event', 'value': _fmt_money(overdue_8_30)},
                {'key': 'b3', 'label': '31+ days past event', 'value': _fmt_money(overdue_31)},
            ],
            'aging_note': f'Unset event date pending: {_fmt_money(ambiguous_date_pending)} '
            '(buckets exclude null dates; fix dates to age properly.)',
            'basis': 'Today/MTD: event totals by scheduled date plus standalone quotes booked in-period.',
        },
        'ops_funnel': funnel,
        'ops_pipeline': {
            'leads_today': leads_today,
            'stale_leads_48h': stale_planning,
            'quotations_pending': quotations_awaiting,
            'lost_last_30d': lost_window,
        },
        'ops_alerts': alerts,
        'ops_load': {
            'today': load_today,
            'tomorrow': load_tomorrow,
            'week': load_week,
            'busy': busy_dates_list,
            'week_note': 'Week = next 7 days including today.',
        },
        'ops_quick_actions': creates,
        'ops_fix_actions': fixes,
        'ops_recent_quotations': recent_quotations,
        'ops_upcoming_events': upcoming_events,
    }
