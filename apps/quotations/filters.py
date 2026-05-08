import django_filters

from .models import Quotation


class QuotationFilter(django_filters.FilterSet):
    inquiry = django_filters.UUIDFilter(field_name='inquiry_id')

    class Meta:
        model = Quotation
        fields = ['inquiry']
