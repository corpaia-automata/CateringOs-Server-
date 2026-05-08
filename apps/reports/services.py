from __future__ import annotations

from .selectors import (
    events_per_day_last_7_days,
    monthly_revenue_components,
    pending_components,
    revenue_trend,
)


def dashboard_payload(tenant_id) -> dict:
    event_revenue, quotation_revenue = monthly_revenue_components(tenant_id)
    event_pending, quotation_pending = pending_components(tenant_id)
    return {
        'monthly_revenue': event_revenue + quotation_revenue,
        'pending_payment_amount': event_pending + quotation_pending,
        'events_per_day': events_per_day_last_7_days(tenant_id),
    }


def revenue_trend_payload(tenant_id, range_key: str) -> dict:
    return {'results': revenue_trend(tenant_id, range_key)}
