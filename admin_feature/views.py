from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.core.cache import cache
from authentication.security import APIKeyAuthentication
from pt_backend.models import Role
from django.utils import timezone
from datetime import datetime, timedelta
from pt_backend.models import User, Case
from .services import DatasetsService
from django.conf import settings
import jwt

# Create your views here.

class RolesSummaryAPIView(APIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = []

    def get(self, request):
        names = list(Role.objects.values_list('name', flat=True).order_by('name'))
        return Response({
            'count': len(names),
            'roles': names,
        }, status=status.HTTP_200_OK)


class FailedLoginStatsAPIView(APIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = []

    def get(self, request):
        # Global counters stored in cache
        total_failed = cache.get('auth:failed_login_total', 0)
        events = cache.get('auth:failed_login_events', [])

        # Unique emails (prefer cached set size if available)
        unique_count = cache.get('auth:failed_login_unique_emails_count')
        if unique_count is None:
            unique_count = len({e.get('email') for e in events if e.get('email')})

        # Compute last 24 hours from events
        now = timezone.now()
        threshold = now - timedelta(hours=24)
        count_24h = 0
        for e in events:
            ts = e.get('timestamp')
            if not ts:
                continue
            try:
                dt = datetime.fromisoformat(ts)
                # Handle naive datetimes by assuming UTC
                if dt.tzinfo is None:
                    dt = dt.replace(tzinfo=timezone.utc)
                if dt >= threshold:
                    count_24h += 1
            except Exception:
                continue

        return Response({
            'total_failed': total_failed,
            'total_unique_emails': unique_count,
            'last_24h': count_24h,
            'logs_url': '/admin-feature/failed-logins/logs'
        }, status=status.HTTP_200_OK)


class FailedLoginEventsAPIView(APIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = []

    def get(self, request):
        # Return the most recent 200 failed login events (email, timestamp, ip)
        events = cache.get('auth:failed_login_events', [])
        # reverse chronological for last 200
        recent = list(reversed(events[-200:]))
        return Response({
            'count': len(recent),
            'events': recent,
        }, status=status.HTTP_200_OK)
    
class UsersSummaryAPIView(APIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = []

    def get(self, request):
        total_users = User.objects.count()
        active_users = User.objects.filter(last_login__isnull=False).count()
        return Response(
            {
                "total_users": total_users,
                "active_users": active_users,
            },
            status=status.HTTP_200_OK,
        )
    
class DatasetsSummaryAPIView(APIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = []

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.datasets_service = DatasetsService()

    def get(self, request):
        # Define "dataset" as the number of Case records
        total_datasets = self.datasets_service.get_total_datasets()
        return Response(
            {
                "total_datasets": total_datasets,
            },
            status=status.HTTP_200_OK,
        )


class StatsAPIView(APIView):
    """Single endpoint consumed by FE /admin-dashboard for top cards.

    Returns:
    - totalUsers: int
    - activeUsers: int
    - datasets: int
    - failedLogins: int (from cache counters)
    - roles: list[str]
    """

    authentication_classes = [APIKeyAuthentication]
    permission_classes = []

    def get(self, request):
        total_users = User.objects.count()
        active_users = User.objects.filter(last_login__isnull=False).count()
        datasets_service = DatasetsService()
        datasets = datasets_service.get_total_datasets()
        roles = list(Role.objects.values_list('name', flat=True).order_by('name'))

        # Failed login total from cache (default 0)
        failed_logins = cache.get('auth:failed_login_total', 0)

        return Response(
            {
                "totalUsers": total_users,
                "activeUsers": active_users,
                "datasets": datasets,
                "failedLogins": failed_logins,
                "roles": roles,
            },
            status=status.HTTP_200_OK,
        )


class UserInfoAPIView(APIView):
    """Return the logged-in user's display name and role for the dashboard header.

    Contract:
    - Input: Authorization: Bearer <JWT access token generated by LoginAPIView>
    - Output: { name: str, role: str }
    - Errors: 401 if token missing/invalid
    """

    authentication_classes = [APIKeyAuthentication]
    permission_classes = []

    def get(self, request):
        auth_header = request.headers.get("Authorization", "")
        if not auth_header.startswith("Bearer "):
            return Response({"detail": "Authentication token required"}, status=status.HTTP_401_UNAUTHORIZED)

        token = auth_header.split(" ", 1)[1]
        try:
            payload = jwt.decode(token, settings.SECRET_KEY, algorithms=["HS256"])
        except (jwt.ExpiredSignatureError, jwt.InvalidTokenError):  # pragma: no cover
            # Treat any JWT validation failure as unauthorized
            return Response({"detail": "Invalid token"}, status=status.HTTP_401_UNAUTHORIZED)  # pragma: no cover

        # Prefer embedded claims (AuthService adds name, role, email) with DB fallback
        name = payload.get("name")
        role = payload.get("role")
        if not name or not role:
            user_id = payload.get("user_id")
            if not user_id:
                return Response({"detail": "Invalid token payload"}, status=status.HTTP_401_UNAUTHORIZED)
            try:
                user = User.objects.get(id=user_id)
                name = user.name
                role = user.role
            except User.DoesNotExist:
                return Response({"detail": "User not found"}, status=status.HTTP_401_UNAUTHORIZED)

        return Response({"name": name, "role": role}, status=status.HTTP_200_OK)
