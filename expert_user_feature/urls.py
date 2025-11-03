from django.urls import path
from .views import (
    ExpertCaseCSVUploadView,
    ExpertCaseListView,
    ExpertCaseBulkDeleteView,
    ExpertBatchListView,
    ExpertBatchDeleteView,
)

urlpatterns = [
    path("experts/cases/", ExpertCaseListView.as_view(), name="expert-cases"),
    path("experts/cases/upload-csv/", ExpertCaseCSVUploadView.as_view(), name="expert-case-upload-csv"),
    path("experts/cases/delete-all/", ExpertCaseBulkDeleteView.as_view(), name="expert-case-delete-all"),

    # ✅ NEW
    path("experts/batches/", ExpertBatchListView.as_view(), name="expert-batch-list"),
    path("experts/batches/<uuid:batch_id>/delete/", ExpertBatchDeleteView.as_view(), name="expert-batch-delete"),
]