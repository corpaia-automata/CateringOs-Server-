from django.contrib import admin

from .models import EventMenuItem


@admin.register(EventMenuItem)
class EventMenuItemAdmin(admin.ModelAdmin):
    list_display    = ('event', 'dish_name_snapshot', 'serving_unit_snapshot', 'quantity', 'sort_order', 'is_deleted')
    list_filter     = ('event__status', 'is_deleted')
    search_fields   = ('dish_name_snapshot', 'event__event_code')
    readonly_fields = ('dish_name_snapshot', 'serving_unit_snapshot', 'recipe_snapshot',
                       'created_at', 'updated_at', 'deleted_at')
    ordering        = ('event', 'sort_order', 'created_at')
