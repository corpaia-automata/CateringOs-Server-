"""PostgreSQL RLS session helpers (``app.current_tenant_id``)."""

from __future__ import annotations

import uuid
from contextlib import contextmanager
from typing import Iterator, Union

from django.db import connection

TenantId = Union[str, uuid.UUID]


def set_tenant_rls(tenant_id: TenantId) -> None:
    """Activate tenant row-level security for the current DB transaction."""
    with connection.cursor() as cursor:
        cursor.execute(
            'SET LOCAL app.current_tenant_id = %s',
            [str(tenant_id)],
        )


@contextmanager
def with_tenant_rls(tenant_id: TenantId) -> Iterator[None]:
    """Context manager that sets RLS for tenant-scoped writes (onboarding, jobs)."""
    set_tenant_rls(tenant_id)
    yield
