from django.http import HttpResponse
from django.urls import path

from .views import (
    ExpertCaseCSVUploadAPIView,
    ExpertCaseCreateView,
    ExpertCaseDetailView,
    ExpertDashboardCSVDownloadAPIView,
    ExpertDashboardDownloadLogAPIView,
)

def feature_placeholder(request):
    return HttpResponse("Expert User Feature Placeholder")

urlpatterns = [
    path("", feature_placeholder, name="expert-feature-placeholder"),
    path("experts/cases/", ExpertCaseCreateView.as_view(), name="expert-cases"),
    path("experts/cases/upload-csv/", ExpertCaseCSVUploadAPIView.as_view(), name="expert-cases-upload-csv"),
    path("experts/cases/<uuid:pk>/", ExpertCaseDetailView.as_view(), name="expert-case-detail"),
    path("downloads/log/", ExpertDashboardDownloadLogAPIView.as_view(), name="expert-dashboard-download-log"),
    path("downloads/csv/", ExpertDashboardCSVDownloadAPIView.as_view(), name="expert-dashboard-download-csv"),
]
