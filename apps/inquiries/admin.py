from django.contrib import admin

from .models import Inquiry


@admin.register(Inquiry)
class InquiryAdmin(admin.ModelAdmin):
    list_display   = ('customer_name', 'contact_number', 'source_channel', 'event_type', 'tentative_date', 'status')
    list_filter    = ('status', 'source_channel')
    search_fields  = ('customer_name', 'contact_number', 'event_type')
    ordering       = ('-created_at',)
    readonly_fields = ('id', 'created_at', 'updated_at')
