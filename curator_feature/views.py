from django.db.models import Q
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from .models import BackendCase
from .permissions import IsCuratorRole

class CuratorCasesListAPIView(APIView):
    """
    GET /curator-feature/cases/?page=1&pageSize=10&search=&gender=&minAge=&maxAge=&status=&severity=&disease_id=&location_id=&sort=age:desc
    """
    permission_classes = [IsAuthenticated, IsCuratorRole]

    def get(self, request):
        def _i(v, default=None):
            try: return int(v)
            except: return default
        page = max(1, _i(request.query_params.get("page", 1), 1))
        page_size = max(1, min(100, _i(request.query_params.get("pageSize", 10), 10)))

        # filters
        search = (request.query_params.get("search") or "").strip()
        gender = (request.query_params.get("gender") or "").strip()
        status_f = (request.query_params.get("status") or "").strip()
        severity = (request.query_params.get("severity") or "").strip()
        disease_id = (request.query_params.get("disease_id") or "").strip()
        location_id = (request.query_params.get("location_id") or "").strip()
        min_age = _i(request.query_params.get("minAge"))
        max_age = _i(request.query_params.get("maxAge"))

        # sorting
        sort = (request.query_params.get("sort") or "id:asc").lower()
        field = sort.split(":")[0]
        direction = sort.split(":")[1] if ":" in sort else "asc"
        sort_field = field if field in {"id","age","city","status","severity"} else "id"
        order_by = f"-{sort_field}" if direction == "desc" else sort_field

        qs = BackendCase.objects.all()
        if search:
            qs = qs.filter(
                Q(city__icontains=search) |
                Q(status__icontains=search) |
                Q(severity__icontains=search)
            )
        if gender:
            qs = qs.filter(gender__iexact=gender)
        if status_f:
            qs = qs.filter(status__iexact=status_f)
        if severity:
            qs = qs.filter(severity__icontains=severity)
        if disease_id:
            qs = qs.filter(disease_id=disease_id)
        if location_id:
            qs = qs.filter(location_id=location_id)
        if min_age is not None:
            qs = qs.filter(age__gte=min_age)
        if max_age is not None:
            qs = qs.filter(age__lte=max_age)

        total = qs.count()
        items = qs.order_by(order_by)[(page-1)*page_size : page*page_size]
        data = list(items.values("id","gender","age","city","status","disease_id","location_id","severity"))

        return Response({"data": data, "page": page, "pageSize": page_size, "total": total}, status=status.HTTP_200_OK)
