from django.urls import path

from .views import (
    ContributorApprovalRoleView,
    ContributorCaseDetailView,
    ContributorCaseListCreateView,
    ContributorCaseReviewView,
)

urlpatterns = [
    path("cases/", ContributorCaseListCreateView.as_view(), name="contributor-case-list"),
    path(
        "cases/<uuid:id>/",
        ContributorCaseDetailView.as_view(),
        name="contributor-case-detail",
    ),
    path(
        "cases/<uuid:pk>/review/",
        ContributorCaseReviewView.as_view(),
        name="contributor-case-review",
    ),
    path(
        "approvers/roles/",
        ContributorApprovalRoleView.as_view(),
        name="contributor-approver-roles",
    ),
]
