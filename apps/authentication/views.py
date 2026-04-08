from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenObtainPairView

from .models import User
from .serializers import (
    CustomTokenObtainPairSerializer,
    RegisterSerializer,
    TenantLoginSerializer,
    UserSerializer,
)


class RegisterView(APIView):
    permission_classes = (AllowAny,)

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user = serializer.save()
        refresh = RefreshToken.for_user(user)
        return Response({
            'user': UserSerializer(user).data,
            'access': str(refresh.access_token),
            'refresh': str(refresh),
        }, status=status.HTTP_201_CREATED)


class LoginView(TokenObtainPairView):
    permission_classes = (AllowAny,)
    serializer_class = CustomTokenObtainPairSerializer


class LogoutView(APIView):

    def post(self, request):
        try:
            token = RefreshToken(request.data['refresh'])
            token.blacklist()
        except Exception:
            pass
        return Response(status=status.HTTP_204_NO_CONTENT)


class MeView(APIView):

    def get(self, request):
        return Response(UserSerializer(request.user).data)

    def patch(self, request):
        serializer = UserSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data)


class FindTenantView(APIView):
    """
    POST /api/auth/find-tenant/
    Public. Accepts { email } and returns the tenant slug that owns that email.
    Lets the login page skip asking users for a Workspace ID.
    """
    permission_classes = (AllowAny,)

    def post(self, request):
        email = (request.data.get('email') or '').strip().lower()
        if not email:
            return Response({'detail': 'Email is required.'}, status=status.HTTP_400_BAD_REQUEST)
        user = User.objects.filter(email__iexact=email).select_related('tenant').first()
        if not user:
            return Response({'detail': 'No account found for this email.'}, status=status.HTTP_404_NOT_FOUND)
        return Response({'slug': user.tenant.slug})


class TenantLoginView(APIView):
    """
    POST /api/app/<slug>/auth/login/
    Tenant-scoped login. Slug is resolved by TenantResolverMiddleware before
    this view runs, so request.tenant / request.tenant_id are already set.
    Returns accessToken, refreshToken, user, and tenant info.
    """
    permission_classes = (AllowAny,)

    def post(self, request, slug):
        serializer = TenantLoginSerializer(
            data=request.data, context={'request': request}
        )
        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']

        refresh = RefreshToken.for_user(user)
        # Embed tenant + role claims into both refresh and access tokens
        refresh['tenant_id'] = str(user.tenant_id)
        refresh['tenant_slug'] = request.tenant_slug
        refresh['role'] = user.role
        refresh['email'] = user.email

        tenant = request.tenant

        return Response({
            'accessToken': str(refresh.access_token),
            'refreshToken': str(refresh),
            'user': {
                'id': str(user.id),
                'email': user.email,
                'role': user.role,
            },
            'tenant': {
                'name': tenant['name'],
                'slug': tenant['slug'],
                'config': tenant['config'],
            },
        })
