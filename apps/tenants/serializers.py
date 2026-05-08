from rest_framework import serializers

from apps.quotations.models import TemplateType

from .models import Tenant


class TenantSerializer(serializers.ModelSerializer):
    class Meta:
        model = Tenant
        fields = (
            'id',
            'slug',
            'name',
            'plan',
            'config',
            'trial_started_at',
            'trial_ends_at',
            'subscription_status',
            'default_template',
            'default_quotation_template',
        )
        read_only_fields = (
            'id',
            'slug',
            'trial_started_at',
            'trial_ends_at',
            'subscription_status',
            'default_quotation_template',
        )


class OnboardSerializer(serializers.Serializer):
    companyName = serializers.CharField(max_length=255)
    email = serializers.EmailField()
    password = serializers.CharField(min_length=8, write_only=True)
    country = serializers.CharField(max_length=5, default='IN')
    plan = serializers.CharField(max_length=20, default='starter')
    defaultTemplate = serializers.ChoiceField(
        choices=TemplateType.choices,
        required=False,
        allow_null=True,
    )
