# admin_feature/urls.py
from django.urls import path
from .views import (
    RolesSummaryAPIView,
    FailedLoginStatsAPIView,
    FailedLoginEventsAPIView,
    UsersSummaryAPIView,
    DatasetsSummaryAPIView,
    StatsAPIView,
    UserInfoAPIView,
)

urlpatterns = [
    path("roles/summary", RolesSummaryAPIView.as_view(), name="roles-summary"),
    path("failed-logins/stats", FailedLoginStatsAPIView.as_view(), name="failed-login-stats"),
    path("failed-logins/logs", FailedLoginEventsAPIView.as_view(), name="failed-login-logs"),
    path("users/summary", UsersSummaryAPIView.as_view(), name="users-summary"),
    path("datasets/summary", DatasetsSummaryAPIView.as_view(), name="datasets-summary"),
    path("stats", StatsAPIView.as_view(), name="admin-stats"),
    path("user-info", UserInfoAPIView.as_view(), name="admin-user-info"),
]
