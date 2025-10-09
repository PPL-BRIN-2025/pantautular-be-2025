from django.urls import path

from curator_feature.views import DownloadLogAPIView, DashboardDownloadEventAPIView

urlpatterns = [
    path("download", DownloadLogAPIView.as_view(), name="curator-download-log"),
    path("downloads/log/", DashboardDownloadEventAPIView.as_view(), name="curator-dashboard-download-log"),
]
