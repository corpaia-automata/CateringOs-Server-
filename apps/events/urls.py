from django.urls import include, path
from rest_framework_nested import routers

from apps.menu.views import EventMenuItemViewSet
from apps.quotations.views import QuotationViewSet

from .views import EventViewSet

router = routers.DefaultRouter()
router.register(r'', EventViewSet, basename='event')

# Nested: /api/events/{event_pk}/menu-items/
events_router = routers.NestedDefaultRouter(router, r'', lookup='event')
events_router.register(r'menu-items', EventMenuItemViewSet, basename='event-menu-item')

# Nested: /api/events/{event_pk}/quotations/
events_router.register(r'quotations', QuotationViewSet, basename='event-quotation')

urlpatterns = [
    path('', include(router.urls)),
    path('', include(events_router.urls)),
]
