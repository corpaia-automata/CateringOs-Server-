"""Introspect live DB columns so ORM code survives partial migrations."""

from __future__ import annotations

from functools import lru_cache

from django.db import connection
from django.db.models import Model


@lru_cache(maxsize=64)
def db_table_columns(table_name: str) -> frozenset[str]:
    with connection.cursor() as cursor:
        cursor.execute(
            """
            SELECT column_name
            FROM information_schema.columns
            WHERE table_schema = 'public' AND table_name = %s
            """,
            [table_name],
        )
        return frozenset(row[0] for row in cursor.fetchall())


def model_db_columns(model: type[Model]) -> frozenset[str]:
    return db_table_columns(model._meta.db_table)


def model_field_names_on_db(model: type[Model]) -> list[str]:
    cols = model_db_columns(model)
    return [
        f.name
        for f in model._meta.local_concrete_fields
        if f.column in cols
    ]


def column_on_db(model: type[Model], field_name: str) -> bool:
    try:
        field = model._meta.get_field(field_name)
    except Exception:
        return False
    return field.column in model_db_columns(model)


def filter_kwargs_for_model(model: type[Model], kwargs: dict) -> dict:
    cols = model_db_columns(model)
    filtered: dict = {}
    for key, value in kwargs.items():
        try:
            field = model._meta.get_field(key)
        except Exception:
            continue
        if getattr(field, 'column', None) in cols:
            filtered[key] = value
    return filtered


def queryset_for_db(model: type[Model], manager=None):
    """QuerySet that SELECTs only columns present in the database."""
    mgr = manager if manager is not None else model.objects
    names = model_field_names_on_db(model)
    if not names:
        return mgr.all()
    return mgr.only(*names)
