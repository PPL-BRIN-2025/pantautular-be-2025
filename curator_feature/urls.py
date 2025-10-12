from django.urls import path

from curator_feature.views import ChartDataAPIView, DashboardDownloadEventAPIView, DownloadLogAPIView

urlpatterns = [
    path("charts/data", ChartDataAPIView.as_view(), name="curator-charts-data"),
    path("download", DownloadLogAPIView.as_view(), name="curator-download-log"),
    path("downloads/log/", DashboardDownloadEventAPIView.as_view(), name="curator-dashboard-download-log"),
]
