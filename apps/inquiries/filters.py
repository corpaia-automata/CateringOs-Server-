import django_filters
from django.db.models import Q

from .models import Inquiry


class InquiryFilter(django_filters.FilterSet):
    status                = django_filters.CharFilter(method='filter_status')
    tentative_date_after  = django_filters.DateFilter(field_name='tentative_date', lookup_expr='gte')
    tentative_date_before = django_filters.DateFilter(field_name='tentative_date', lookup_expr='lte')
    event_type            = django_filters.CharFilter(field_name='event_type', lookup_expr='icontains')

    def filter_status(self, queryset, name, value):
        v = (value or '').strip().upper()
        if not v:
            return queryset

        if v == 'PLANNING':
            # Planning bucket includes legacy in-progress pipeline states.
            return queryset.filter(status__in=['PLANNING', 'NEW', 'QUALIFIED', 'FOLLOW_UP', 'QUOTED'])

        if v == 'SUCCESS':
            # Success bucket includes legacy confirmed + inquiries already converted to confirmed events.
            return queryset.filter(
                Q(status__in=['SUCCESS', 'CONFIRMED']) |
                Q(converted_event__status='CONFIRMED')
            )

        if v == 'LOST':
            # Lost bucket includes legacy rejected values.
            return queryset.filter(status__in=['LOST', 'REJECTED'])

        return queryset.filter(status=v)

    class Meta:
        model  = Inquiry
        fields = ['status', 'source_channel', 'tentative_date_after', 'tentative_date_before', 'event_type']
