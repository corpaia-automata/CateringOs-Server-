from rest_framework.permissions import BasePermission


class IsAuthenticatedJWT(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated)


class IsTenantScopedJWT(BasePermission):
    """
    DRF-layer cross-tenant guard (defence-in-depth on top of the middleware check).

    Passes when:
      - The request is authenticated AND
      - Either there is no request.tenant_id (non-tenant route), OR
        the JWT's tenant_id claim matches request.tenant_id.

    Returns 403 when a valid JWT belongs to a different tenant than the URL slug.
    """
    message = 'Token does not belong to this workspace.'

    def has_permission(self, request, view):
        if not (request.user and request.user.is_authenticated):
            return False
        request_tenant_id = getattr(request, 'tenant_id', None)
        if request_tenant_id is None:
            return True  # non-tenant route — skip cross-tenant check
        token_tenant_id = str(request.auth.get('tenant_id', '')) if request.auth else ''
        return token_tenant_id == request_tenant_id
