from rest_framework import serializers

from .models import Inquiry, PreEstimate, PreEstimateCategory, PreEstimateItem


class InquirySerializer(serializers.ModelSerializer):

    class Meta:
        model  = Inquiry
        fields = (
            'id', 'customer_name', 'contact_number', 'email',
            'source_channel', 'event_type', 'tentative_date',
            'guest_count', 'estimated_budget', 'notes', 'status',
            'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'created_at', 'updated_at')


# ---------------------------------------------------------------------------
# PreEstimate serializers
# ---------------------------------------------------------------------------

class PreEstimateItemSerializer(serializers.ModelSerializer):
    class Meta:
        model  = PreEstimateItem
        fields = ('id', 'name', 'unit', 'quantity', 'rate', 'total', 'created_at')
        read_only_fields = ('id', 'total', 'created_at')


class PreEstimateCategorySerializer(serializers.ModelSerializer):
    items = PreEstimateItemSerializer(many=True, read_only=True)

    class Meta:
        model  = PreEstimateCategory
        fields = ('id', 'name', 'order', 'items')
        read_only_fields = ('id',)


class PreEstimateDetailSerializer(serializers.ModelSerializer):
    categories = PreEstimateCategorySerializer(many=True, read_only=True)

    class Meta:
        model  = PreEstimate
        fields = (
            'id', 'inquiry',
            'event_type', 'service_type', 'location', 'guest_count', 'target_margin',
            'total_cost', 'total_quote', 'total_profit',
            'categories',
            'created_at', 'updated_at',
        )
        read_only_fields = ('id', 'total_cost', 'total_quote', 'total_profit', 'created_at', 'updated_at')


class PreEstimateCreateSerializer(serializers.ModelSerializer):
    class Meta:
        model  = PreEstimate
        fields = ('inquiry', 'event_type', 'service_type', 'location', 'guest_count', 'target_margin')

    def validate_inquiry(self, inquiry):
        request = self.context.get('request')
        if request and str(inquiry.tenant_id) != str(request.tenant_id):
            raise serializers.ValidationError('Inquiry not found.')
        return inquiry

    def validate_target_margin(self, value):
        if value <= 0 or value >= 100:
            raise serializers.ValidationError('target_margin must be between 0 and 100 (exclusive).')
        return value


class PreEstimateItemCreateSerializer(serializers.ModelSerializer):
    category_id = serializers.PrimaryKeyRelatedField(
        queryset=PreEstimateCategory.objects.all(),
        source='category',
    )

    class Meta:
        model  = PreEstimateItem
        fields = ('id', 'category_id', 'name', 'unit', 'quantity', 'rate', 'total', 'created_at')
        read_only_fields = ('id', 'total', 'created_at')

    def validate_category_id(self, category):
        pre_estimate = self.context.get('pre_estimate')
        if pre_estimate and category.pre_estimate_id != pre_estimate.pk:
            raise serializers.ValidationError('Category does not belong to this PreEstimate.')
        return category
