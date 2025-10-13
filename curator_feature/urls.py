from django.urls import path

from .views import CuratorDataLogListCreateAPIView
from curator_feature.views import ChartDataAPIView, DashboardDownloadEventAPIView, DownloadLogAPIView, ChartsSimpleView, CuratorDataLogListCreateAPIView

urlpatterns = [
    path("charts/data", ChartDataAPIView.as_view(), name="curator-charts-data"),
    path("download", DownloadLogAPIView.as_view(), name="curator-download-log"),
    path("downloads/log/", DashboardDownloadEventAPIView.as_view(), name="curator-dashboard-download-log"),
    path("charts", ChartsSimpleView.as_view(), name="curator-charts-simple"),
    path("api/curator/audit-logs/", CuratorDataLogListCreateAPIView.as_view(), name="curator_audit_logs"),
]
