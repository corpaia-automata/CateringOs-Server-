from rest_framework import serializers
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from .models import User


class RegisterSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, min_length=8)
    password_confirm = serializers.CharField(write_only=True)

    class Meta:
        model = User
        fields = ('first_name', 'last_name', 'email', 'password', 'password_confirm', 'phone')

    def validate(self, attrs):
        if attrs['password'] != attrs.pop('password_confirm'):
            raise serializers.ValidationError({'password_confirm': 'Passwords do not match.'})
        return attrs

    def create(self, validated_data):
        return User.objects.create_user(**validated_data)


class UserSerializer(serializers.ModelSerializer):
    full_name = serializers.CharField(read_only=True)

    class Meta:
        model = User
        fields = ('id', 'email', 'first_name', 'last_name', 'phone', 'role', 'full_name', 'is_active')
        read_only_fields = ('id', 'email', 'role', 'full_name', 'is_active')


class CustomTokenObtainPairSerializer(TokenObtainPairSerializer):

    @classmethod
    def get_token(cls, user):
        token = super().get_token(user)
        # Embed custom claims directly into the JWT payload
        token['role'] = user.role
        token['full_name'] = user.full_name
        token['email'] = user.email
        token['tenant_id'] = str(user.tenant_id)
        return token

    def validate(self, attrs):
        data = super().validate(attrs)
        # Include the full user object alongside the tokens
        data['user'] = UserSerializer(self.user).data
        return data


class TenantLoginSerializer(serializers.Serializer):
    """
    Authenticates a user scoped to a specific tenant.
    Requires request.tenant_id to be set by TenantResolverMiddleware.
    """
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        request = self.context['request']
        tenant_id = getattr(request, 'tenant_id', None)
        if not tenant_id:
            raise serializers.ValidationError('Tenant context is missing.')

        try:
            user = User.objects.get(
                tenant_id=tenant_id,
                email=attrs['email'],
                is_active=True,
            )
        except User.DoesNotExist:
            raise serializers.ValidationError('Invalid credentials.')

        if not user.check_password(attrs['password']):
            raise serializers.ValidationError('Invalid credentials.')

        attrs['user'] = user
        return attrs
