from django.contrib import admin

from .models import Tenant


@admin.register(Tenant)
class TenantAdmin(admin.ModelAdmin):
    list_display = ['name', 'slug', 'plan', 'status', 'default_template', 'default_quotation_template']
    search_fields = ['name', 'slug']
