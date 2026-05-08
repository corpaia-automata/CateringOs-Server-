from __future__ import annotations


EVENT_STATUS_ALIASES = {
    'DRAFT': 'DRAFT',
    'CONFIRMED': 'CONFIRMED',
    'IN_PROGRESS': 'IN_PROGRESS',
    'INPROGRESS': 'IN_PROGRESS',
    'COMPLETED': 'COMPLETED',
    'SUCCESS': 'COMPLETED',
    'CANCELLED': 'CANCELLED',
    'CANCELED': 'CANCELLED',
}


def normalize_event_status(raw_status: str | None) -> str | None:
    if raw_status is None:
        return None
    cleaned = str(raw_status).strip().upper().replace(' ', '_')
    return EVENT_STATUS_ALIASES.get(cleaned, cleaned)
