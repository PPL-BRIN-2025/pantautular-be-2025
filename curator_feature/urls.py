from django.urls import path

# import semua view yang dipakai
from curator_feature.views import (
    ChartDataAPIView,
    DashboardDownloadEventAPIView,
    DownloadLogAPIView,
    ChartsSimpleView,
    CuratorCaseListCreateView,
    CuratorCaseDetailView,
    DiseaseListCreateView,
    CuratorDiseaseListCreateView,
    CuratorDataLogListCreateAPIView,  
)

urlpatterns = [
    # --- Chart & Download endpoints ---
    path("charts/data", ChartDataAPIView.as_view(), name="curator-charts-data"),
    path("download", DownloadLogAPIView.as_view(), name="curator-download-log"),
    path("downloads/log/", DashboardDownloadEventAPIView.as_view(), name="curator-dashboard-download-log"),
    path("charts", ChartsSimpleView.as_view(), name="curator-charts-simple"),

    # --- Public diseases (GET) / curator-only POST
    path("diseases/", DiseaseListCreateView.as_view(), name="curator-diseases-list"),

    # --- Curator Case CRUD endpoints ---
    path("curator/cases/", CuratorCaseListCreateView.as_view(), name="curator-cases"),
    path("curator/cases/<uuid:id>/", CuratorCaseDetailView.as_view(), name="curator-case-detail"),
    path("curator/diseases/", CuratorDiseaseListCreateView.as_view(), name="curator-disease-list-create"),

    # --- Curator audit logs endpoint ---
    path("api/curator/audit-logs/", CuratorDataLogListCreateAPIView.as_view(), name="curator_audit_logs"),
]
