from django.urls import path
from .views import AdminUserLogsAPIView, AdminUserLogDetailAPIView, AdminUserLogUpdateAPIView

urlpatterns = [
    path("api/admin/user-logs/", AdminUserLogsAPIView.as_view(), name="admin_user_logs"),
    path("api/admin/user-logs/<int:id>/", AdminUserLogUpdateAPIView.as_view(), name="log-update"),
    path("api/admin/user-logs/<int:id>/detail/", AdminUserLogDetailAPIView.as_view(), name="log-detail"),
]
