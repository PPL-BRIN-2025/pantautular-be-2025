from django.http import HttpResponse
from django.urls import path

from .views import ExpertDashboardCSVDownloadAPIView, ExpertDashboardDownloadLogAPIView

def feature_placeholder(request):
    return HttpResponse("Expert User Feature Placeholder")

urlpatterns = [
    path("", feature_placeholder, name="expert-feature-placeholder"),
    path("downloads/log/", ExpertDashboardDownloadLogAPIView.as_view(), name="expert-dashboard-download-log"),
    path("downloads/csv/", ExpertDashboardCSVDownloadAPIView.as_view(), name="expert-dashboard-download-csv"),
]
