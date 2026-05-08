from django.apps import AppConfig


class QuotationsConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'apps.quotations'

    def ready(self):
        from apps.quotations import signals

        signals.connect_quotation_signals()
