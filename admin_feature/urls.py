from django.urls import path
from .views import AdminUserLogsAPIView

urlpatterns = [
    path("api/admin/user-logs/", AdminUserLogsAPIView.as_view(), name="admin_user_logs"),
]
