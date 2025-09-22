from django.urls import path
from .views import AdminUserLogsAPIView, UserLogDetailAPIView

urlpatterns = [
    path("api/admin/user-logs/", AdminUserLogsAPIView.as_view(), name="admin_user_logs"),
    path("api/admin/user-logs/<int:id>/detail/", UserLogDetailAPIView.as_view(), name="log-detail"),
]
