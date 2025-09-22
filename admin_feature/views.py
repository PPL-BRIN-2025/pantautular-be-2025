from django.shortcuts import render

from datetime import datetime
from django.utils.dateparse import parse_datetime
from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from .models import AdminUserLog
from .serializers import AdminUserLogSerializer

class AdminUserLogsAPIView(APIView):
    """
    GET /admin/user-logs/?page=1&pageSize=10&search=&start=&end=&sort=timestamp:desc
    POST /admin/user-logs/
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
        start_raw = request.query_params.get("start")
        end_raw = request.query_params.get("end")
        sort = request.query_params.get("sort") or "timestamp:desc"

        order = "-timestamp" if sort.endswith(":desc") else "timestamp"

        qs = AdminUserLog.objects.all()
        if search:
            qs = qs.filter(
                Q(username__icontains=search) |
                Q(email__icontains=search) |
                Q(detail__icontains=search)
            )

        def to_dt(v):
            if not v:
                return None
            dt = parse_datetime(v)
            if dt is None:
                try:
                    dt = datetime.fromisoformat(v)
                except Exception:
                    dt = None
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

