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
    AdminUserListView,
    AdminUserDeleteView,
    AdminUserChangeRoleView, AdminUserLogsAPIView, AdminUserLogDetailAPIView, AdminUserLogUpdateAPIView
)

urlpatterns = [
    # Admin dashboard endpoints
    path("roles/summary", RolesSummaryAPIView.as_view(), name="roles-summary"),
    path("failed-logins/stats", FailedLoginStatsAPIView.as_view(), name="failed-login-stats"),
    path("failed-logins/logs", FailedLoginEventsAPIView.as_view(), name="failed-login-logs"),
    path("users/summary", UsersSummaryAPIView.as_view(), name="users-summary"),
    path("datasets/summary", DatasetsSummaryAPIView.as_view(), name="datasets-summary"),
    path("stats", StatsAPIView.as_view(), name="admin-stats"),
    path("user-info", UserInfoAPIView.as_view(), name="admin-user-info"),

    # Admin role management endpoints
    path("users", AdminUserListView.as_view(), name="admin-user-list"),
    path("users/<int:id>", AdminUserDeleteView.as_view(), name="admin-user-delete"),
    path("users/<int:id>/role", AdminUserChangeRoleView.as_view(), name="admin-user-change-role"),
  
    # Admin user log menu endpoints
    path("api/admin/user-logs/", AdminUserLogsAPIView.as_view(), name="admin_user_logs"),
    path("api/admin/user-logs/<int:id>/", AdminUserLogUpdateAPIView.as_view(), name="log-update"),
    path("api/admin/user-logs/<int:id>/detail/", AdminUserLogDetailAPIView.as_view(), name="log-detail"),

]
