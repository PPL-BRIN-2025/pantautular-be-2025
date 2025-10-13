from django.urls import path

from curator_feature.views import (
    ChartDataAPIView,
    DashboardDownloadEventAPIView,
    DownloadLogAPIView,
    ChartsSimpleView,
    CuratorCaseListCreateView,
    CuratorCaseDetailView,
)

urlpatterns = [
    # --- Chart & Download endpoints ---
    path("charts/data", ChartDataAPIView.as_view(), name="curator-charts-data"),
    path("download", DownloadLogAPIView.as_view(), name="curator-download-log"),
    path("downloads/log/", DashboardDownloadEventAPIView.as_view(), name="curator-dashboard-download-log"),
    path("charts", ChartsSimpleView.as_view(), name="curator-charts-simple"),

    # --- Curator Case CRUD endpoints ---
    path("curator/cases/", CuratorCaseListCreateView.as_view(), name="curator-cases"),
    path("curator/cases/<uuid:id>/", CuratorCaseDetailView.as_view(), name="curator-case-detail"),
]
