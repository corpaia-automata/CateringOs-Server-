from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from shared.permissions import IsTenantScopedJWT

from .services import dashboard_payload, revenue_trend_payload


class DashboardReportView(APIView):
    permission_classes = [IsAuthenticated, IsTenantScopedJWT]

    def get(self, request, *args, **kwargs):
        return Response(dashboard_payload(request.tenant_id))


class RevenueTrendView(APIView):
    permission_classes = [IsAuthenticated, IsTenantScopedJWT]

    def get(self, request, *args, **kwargs):
        range_key = request.query_params.get('range', 'weekly')
        return Response(revenue_trend_payload(request.tenant_id, range_key))


class TopDishesView(APIView):
    permission_classes = [IsAuthenticated, IsTenantScopedJWT]

    def get(self, request, *args, **kwargs):
        return Response({'results': []})
