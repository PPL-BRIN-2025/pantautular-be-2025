from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status

from .models import CuratorDataLog, BackendCase
from .serializers import CuratorDataLogSerializer
from .permissions import IsCuratorRole

class CuratorDataLogListCreateAPIView(APIView):
    """
    GET /curator-feature/api/curator/audit-logs/
      ?page=1&pageSize=10&search=&start=&end=&submitted_by=&sort=last_edited:desc

    POST /curator-feature/api/curator/audit-logs/
      { "data_id": "<uuid>", "title": "hospitalisasi", "note": "optional" }
    """
    permission_classes = [IsAuthenticated, IsCuratorRole]

    def get(self, request):
        # pagination
        def _i(v, d=None):
            try: return int(v)
            except: return d
        page = max(1, _i(request.query_params.get("page", 1), 1))
        page_size = max(1, min(100, _i(request.query_params.get("pageSize", 10), 10)))

        # filters
        search = (request.query_params.get("search") or "").strip()
        submitted_by = (request.query_params.get("submitted_by") or "").strip()
        start = request.query_params.get("start") or ""
        end = request.query_params.get("end") or ""

        # sorting
        sort = (request.query_params.get("sort") or "last_edited:desc").lower()
        f = sort.split(":")[0]
        d = sort.split(":")[1] if ":" in sort else "desc"
        allowed = {"last_edited", "title", "submitted_by", "data_id"}
        sort_field = f if f in allowed else "last_edited"
        order_by = f"-{sort_field}" if d == "desc" else sort_field

        qs = CuratorDataLog.objects.all()

        if search:
            qs = qs.filter(
                Q(title__icontains=search) |
                Q(submitted_by__icontains=search) |
                Q(data_id__icontains=search)
            )
        if submitted_by:
            qs = qs.filter(submitted_by__icontains=submitted_by)
        if start:
            qs = qs.filter(last_edited__gte=start)
        if end:
            qs = qs.filter(last_edited__lte=end)

        total = qs.count()
        items = qs.order_by(order_by)[(page-1)*page_size : page*page_size]
        data = CuratorDataLogSerializer(items, many=True).data

        return Response(
            {"data": data, "page": page, "pageSize": page_size, "total": total},
            status=status.HTTP_200_OK,
        )

    def post(self, request):
        # optional helper endpoint to create a log
        payload = request.data.copy()
        # if title not provided, try to derive from pt_backend_case.severity
        if not payload.get("title") and payload.get("data_id"):
            try:
                case = BackendCase.objects.get(id=payload["data_id"])
                payload["title"] = case.severity or "N/A"
            except BackendCase.DoesNotExist:
                pass

        payload["submittedBy"] = getattr(request.user, "username", "") or getattr(request.user, "email", "")
        ser = CuratorDataLogSerializer(data=payload)
        if ser.is_valid():
            ser.save()
            return Response(ser.data, status=status.HTTP_201_CREATED)
        return Response(ser.errors, status=status.HTTP_400_BAD_REQUEST)
