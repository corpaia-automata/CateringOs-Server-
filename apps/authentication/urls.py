from django.urls import path
from rest_framework_simplejwt.views import TokenRefreshView

from apps.tenants.views import OnboardView

from .views import FindTenantView, LoginView, LogoutView, MeView, RegisterView, UnifiedLoginView

urlpatterns = [
    path('register/', RegisterView.as_view(), name='auth-register'),
    path('signup/', OnboardView.as_view(), name='auth-signup'),
    path('login/', UnifiedLoginView.as_view(), name='auth-login'),
    path('token/', LoginView.as_view(), name='auth-token-login'),
    path('find-tenant/', FindTenantView.as_view(), name='auth-find-tenant'),
    path('refresh/', TokenRefreshView.as_view(), name='auth-refresh'),
    path('logout/', LogoutView.as_view(), name='auth-logout'),
    path('me/', MeView.as_view(), name='auth-me'),
]
