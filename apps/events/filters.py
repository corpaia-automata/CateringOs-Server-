import django_filters

from .models import Event
from .statuses import normalize_event_status


class EventFilter(django_filters.FilterSet):
    event_date_after  = django_filters.DateFilter(field_name='event_date', lookup_expr='gte')
    event_date_before = django_filters.DateFilter(field_name='event_date', lookup_expr='lte')
    status = django_filters.CharFilter(method='filter_status')

    def filter_status(self, queryset, name, value):
        normalized = normalize_event_status(value)
        if not normalized or normalized == 'ALL':
            return queryset
        return queryset.filter(status=normalized)

    class Meta:
        model = Event
        fields = {
            'event_date':     ['exact'],
            'service_type':   ['exact'],
            'event_type':     ['icontains'],
            'payment_status': ['exact'],
        }
