from django.urls import path

from curator_feature.views import DownloadLogAPIView

urlpatterns = [
    path("download", DownloadLogAPIView.as_view(), name="curator-download-log"),
]
