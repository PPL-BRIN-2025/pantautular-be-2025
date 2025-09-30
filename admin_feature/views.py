from datetime import datetime
from django.utils.dateparse import parse_datetime
from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status, generics

from .models import AdminUserLog
from .serializers import AdminUserLogSerializer, AdminUserLogDetailSerializer

from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import PtBackendUser
from .serializers import PtBackendUserSerializer


class AdminUserLogsAPIView(APIView):
    """
    GET /api/admin/user-logs/?page=1&pageSize=10&search=&sort=last_login:desc
    """

    def get(self, request):
        try:
            page = int(request.query_params.get("page", 1))
        except ValueError:
            page = 1
        try:
            page_size = int(request.query_params.get("pageSize", 10))
        except ValueError:
            page_size = 10
        page = max(1, page)
        page_size = max(1, min(100, page_size))

        search = (request.query_params.get("search") or "").strip()
        sort = request.query_params.get("sort") or "last_login:desc"
        order = "-last_login" if sort.endswith(":desc") else "last_login"

        qs = PtBackendUser.objects.all()

        if search:
            qs = qs.filter(
                Q(name__icontains=search) |
                Q(email__icontains=search)
            )

        total = qs.count()
        qs = qs.order_by(order)

        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        items = qs[start_idx:end_idx]

        data = PtBackendUserSerializer(items, many=True).data
        return Response({
            "data": data,
            "page": page,
            "pageSize": page_size,
            "total": total
        }, status=status.HTTP_200_OK)

        def to_dt(v):
            if not v:
                return None
            dt = parse_datetime(v)
            if dt is None:
                try:
                    dt = datetime.fromisoformat(v)
                except Exception:
                    return None
            return dt

        start_dt = to_dt(start_raw)
        end_dt = to_dt(end_raw)

        if start_dt:
            qs = qs.filter(timestamp__gte=start_dt)
        if end_dt:
            qs = qs.filter(timestamp__lte=end_dt)

        total = qs.count()
        qs = qs.order_by(order)

        start_idx = (page - 1) * page_size
        end_idx = start_idx + page_size
        items = qs[start_idx:end_idx]

        data = AdminUserLogSerializer(items, many=True).data
        return Response({
            "data": data,
            "page": page,
            "pageSize": page_size,
            "total": total
        })

    def post(self, request):
        payload = request.data.copy()
        if not payload.get("timestamp"):
            payload["timestamp"] = datetime.utcnow().isoformat()

        ser = AdminUserLogSerializer(data=payload)
        if ser.is_valid():
            obj = ser.save()
            return Response(AdminUserLogSerializer(obj).data, status=status.HTTP_201_CREATED)
        return Response({"errors": ser.errors}, status=400)


class AdminUserLogDetailAPIView(generics.RetrieveAPIView):
    """
    GET /api/admin/user-logs/<id>/detail/
    """
    queryset = AdminUserLog.objects.all()
    serializer_class = AdminUserLogDetailSerializer
    lookup_field = "id"


class AdminUserLogUpdateAPIView(generics.RetrieveUpdateAPIView):
    """
    GET /api/admin/user-logs/<id>/
    PATCH /api/admin/user-logs/<id>/
    """
    queryset = AdminUserLog.objects.all()
    serializer_class = AdminUserLogSerializer
    lookup_field = "id"

