from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status

from pt_backend.models import Case, Disease, Location, News
from authentication.security import CustomJWTAuthentication
from authentication.permissions import IsTokenAuthenticated
from .permissions import IsExpertUserRole


class ExpertAddCaseBadView(APIView):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsTokenAuthenticated, IsExpertUserRole]

    def post(self, request):
        data = request.data

        # Inline lookups (hard-coded logic)
        disease = Disease.objects.filter(name=data.get("disease")).first()
        if not disease:
            return Response({"error": "Disease not found"}, status=status.HTTP_400_BAD_REQUEST)

        location_data = data.get("location", {})
        location = Location.objects.filter(
            city=location_data.get("city")
        ).first()
        if not location:
            location = Location.objects.create(
                city=location_data.get("city"),
                province=location_data.get("province"),
                latitude=location_data.get("latitude"),
                longitude=location_data.get("longitude"),
            )

        case = Case.objects.create(
            disease=disease,
            location=location,
            gender=data.get("gender"),
            age=data.get("age"),
            city=data.get("city"),
            status=data.get("status"),
            severity=data.get("severity"),
        )

        news_data = data.get("news", {})
        News.objects.create(
            case=case,
            portal=news_data.get("portal"),
            title=news_data.get("title"),
            type=news_data.get("type"),
            content=news_data.get("content"),
            url=news_data.get("url"),
            author=news_data.get("author"),
            date_published=news_data.get("date_published"),
            img_url=news_data.get("img_url", ""),
        )

        return Response({"message": "Case created"}, status=status.HTTP_201_CREATED)
