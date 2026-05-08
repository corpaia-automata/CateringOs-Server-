"""
Canonical URL configuration lives in ``config.urls``.

This module re-exports ``urlpatterns`` for projects that reference ``core.urls``.
"""

from config.urls import urlpatterns

__all__ = ('urlpatterns',)
