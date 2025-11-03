from django.http import HttpResponse
from django.urls import path

from .views import (
    # Case CRUD + CSV
    ExpertCaseCreateView,
    ExpertCaseDetailView,
    ExpertCaseCSVUploadAPIView,

    # Batch system
    ExpertCaseListView,
    ExpertCaseBulkDeleteView,
    ExpertBatchListView,
    ExpertBatchDeleteView,

    # Dashboard export + audit
    ExpertDashboardCSVDownloadAPIView,
    ExpertDashboardDownloadLogAPIView,

    # Dataset list + detail
    ExpertDatasetListView,
    ExpertDatasetDetailView,
)


def feature_placeholder(request):
    return HttpResponse("Expert User Feature Placeholder")


urlpatterns = [
    # Placeholder
    path("", feature_placeholder, name="expert-feature-placeholder"),

    # CASE CRUD
    path("experts/cases/", ExpertCaseCreateView.as_view(), name="expert-cases"),
    path("experts/cases/<uuid:pk>/", ExpertCaseDetailView.as_view(), name="expert-case-detail"),

    # CASE LIST (for filtering via ?batch=…)
    path("experts/cases/list/", ExpertCaseListView.as_view(), name="expert-case-list"),

    # CASE BULK DELETE
    path("experts/cases/delete-all/", ExpertCaseBulkDeleteView.as_view(), name="expert-case-delete-all"),

    # CASE CSV UPLOAD
    path("experts/cases/upload-csv/", ExpertCaseCSVUploadAPIView.as_view(), name="expert-cases-upload-csv"),

    # ✅ BATCH LIST + DELETE
    path("experts/batches/", ExpertBatchListView.as_view(), name="expert-batch-list"),
    path("experts/batches/<uuid:batch_id>/delete/", ExpertBatchDeleteView.as_view(), name="expert-batch-delete"),

    # DASHBOARD EXPORT + LOGS
    path("downloads/log/", ExpertDashboardDownloadLogAPIView.as_view(), name="expert-dashboard-download-log"),
    path("downloads/csv/", ExpertDashboardCSVDownloadAPIView.as_view(), name="expert-dashboard-download-csv"),

    # DATASET API
    path("api/expert/datasets/", ExpertDatasetListView.as_view(), name="expert-dataset-list"),
    path("api/expert/datasets/<str:data_id>/", ExpertDatasetDetailView.as_view(), name="expert-dataset-detail"),
]
