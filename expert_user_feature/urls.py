from django.http import HttpResponse
from django.urls import path

from .views import (
    # cases
    ExpertCaseListCreateView,
    ExpertCaseDetailView,
    ExpertCaseCSVUploadView,
    ExpertCaseBulkDeleteView,
    # dashboard downloads
    ExpertDashboardDownloadLogAPIView,
    ExpertDashboardCSVDownloadAPIView,
    # datasets
    ExpertDatasetListView,
    ExpertDatasetDetailView,
    ExpertDatasetRowsView,
    # batches
    ExpertBatchListView,
    ExpertBatchDeleteView,
    # audit logs (opsional)
    ExpertDataLogListView,
)

def feature_placeholder(request):
    return HttpResponse("Expert User Feature Placeholder")

urlpatterns = [
    path("", feature_placeholder, name="expert-feature-placeholder"),

    # Cases
    path("experts/cases/",                 ExpertCaseListCreateView.as_view(), name="expert-cases"),
    path("experts/cases/<uuid:pk>/",       ExpertCaseDetailView.as_view(),     name="expert-case-detail"),
    path("experts/cases/upload-csv/",      ExpertCaseCSVUploadView.as_view(),  name="expert-cases-upload-csv"),
    path("experts/cases/delete-all/",      ExpertCaseBulkDeleteView.as_view(), name="expert-case-delete-all"),

    # Download logging + CSV
    path("downloads/log/",                 ExpertDashboardDownloadLogAPIView.as_view(),  name="expert-dashboard-download-log"),
    path("downloads/csv/",                 ExpertDashboardCSVDownloadAPIView.as_view(),  name="expert-dashboard-download-csv"),

    # Datasets (public read)
    path("api/expert/datasets/",                 ExpertDatasetListView.as_view(),       name="expert-dataset-list"),
    path("api/expert/datasets/<str:data_id>/",   ExpertDatasetDetailView.as_view(),     name="expert-dataset-detail"),
    path("api/expert/datasets/<str:data_id>/rows/", ExpertDatasetRowsView.as_view(),   name="expert-dataset-rows"),

    # Batches
    path("experts/batches/",                     ExpertBatchListView.as_view(),          name="expert-batch-list"),
    path("experts/batches/<uuid:batch_id>/delete/", ExpertBatchDeleteView.as_view(),     name="expert-batch-delete"),

    # Audit log (opsional)
    path("api/expert/audit-logs/",               ExpertDataLogListView.as_view(),        name="expert-audit-logs"),
]
