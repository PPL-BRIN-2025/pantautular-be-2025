from django.urls import path
from .views import CuratorCaseListCreateView, CuratorCaseDetailView

urlpatterns = [
    # Post
    path("curator/cases/", CuratorCaseListCreateView.as_view(), name="curator-cases"),
    # Update, Delete
    path("curator/cases/<uuid:id>/", CuratorCaseDetailView.as_view(), name="curator-case-detail"),
]
