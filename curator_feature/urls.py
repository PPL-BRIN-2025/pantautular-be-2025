from django.urls import path
from .views import CuratorDataLogListCreateAPIView

urlpatterns = [
    path("api/curator/audit-logs/", CuratorDataLogListCreateAPIView.as_view(),
         name="curator_audit_logs"),
]
