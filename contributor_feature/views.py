from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from rest_framework import generics, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.response import Response
from rest_framework.views import APIView

from authentication.permissions import IsAdminAuthenticated, IsTokenAuthenticated
from authentication.security import CustomJWTAuthentication
from pt_backend.models import Case, News
from .models import ContributorApprovalRole, ContributorCaseSubmission
from .permissions import IsContributorApproverRole, IsContributorRole
from .serializers import (
    ContributorApprovalRoleUpdateSerializer,
    ContributorCaseReadSerializer,
    ContributorCaseReviewSerializer,
    ContributorCaseWriteSerializer,
)


class ContributorBaseView(generics.GenericAPIView): 
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsTokenAuthenticated, IsContributorRole]


class ContributorCaseListCreateView(ContributorBaseView, generics.ListCreateAPIView): 
    serializer_class = ContributorCaseReadSerializer
    queryset = ContributorCaseSubmission.objects.select_related(
        "disease", "location", "created_by", "reviewed_by"
    )

    def get_serializer_class(self):
        if self.request.method == "POST":
            return ContributorCaseWriteSerializer
        return ContributorCaseReadSerializer

    def get_queryset(self):
        qs = super().get_queryset()
        user = self.request.user
        if not ContributorApprovalRole.user_is_approver(user):
            qs = qs.filter(created_by=user)

        state = self.request.query_params.get("state")
        if state:
            qs = qs.filter(state__iexact=state.strip())
        return qs.order_by("-created_at", "-id")

    def create(self, request, *args, **kwargs):
        serializer = ContributorCaseWriteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        submission = serializer.save(created_by=request.user, updated_by=request.user)
        read_serializer = ContributorCaseReadSerializer(
            submission, context=self.get_serializer_context()
        )
        headers = self.get_success_headers(read_serializer.data)
        return Response(read_serializer.data, status=status.HTTP_201_CREATED, headers=headers)


class ContributorCaseDetailView(ContributorBaseView, generics.RetrieveUpdateDestroyAPIView): 
    queryset = ContributorCaseSubmission.objects.select_related(
        "disease", "location", "created_by", "reviewed_by"
    )
    lookup_field = "id"

    def get_serializer_class(self): # pragma: no cover
        if self.request.method in ("PUT", "PATCH"):
            return ContributorCaseWriteSerializer
        return ContributorCaseReadSerializer

    def get_object(self):
        submission = super().get_object()
        if not self._can_access(submission):
            raise PermissionDenied("You do not have access to this submission.")
        return submission

    def _can_access(self, submission):
        user = self.request.user
        return submission.created_by_id == user.id or ContributorApprovalRole.user_is_approver(user)

    def perform_update(self, serializer):  # pragma: no cover
        submission = serializer.instance
        user = self.request.user
        if not submission.is_pending and not ContributorApprovalRole.user_is_approver(user):
            raise PermissionDenied("Only reviewers may edit processed submissions.")
        if submission.created_by_id != user.id and not ContributorApprovalRole.user_is_approver(user):
            raise PermissionDenied("Only the author or reviewers may edit this submission.")
        serializer.save(updated_by=user)

    def perform_destroy(self, instance): # pragma: no cover
        user = self.request.user
        if instance.created_by_id != user.id:
            raise PermissionDenied("Only the author may delete this submission.")
        if not instance.is_pending:
            raise PermissionDenied("Reviewed submissions cannot be deleted.")
        instance.delete()


class ContributorCaseReviewView(APIView): 
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsTokenAuthenticated, IsContributorApproverRole]

    def post(self, request, pk):
        submission = get_object_or_404(ContributorCaseSubmission, pk=pk)
        if not submission.is_pending:
            return Response(
                {"detail": "Submission has already been reviewed."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        serializer = ContributorCaseReviewSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        action = serializer.validated_data["action"]
        note = serializer.validated_data.get("note", "")

        if action == "approve":
            submission = self._approve_submission(submission, request.user, note)
        else:
            submission = self._reject_submission(submission, request.user, note)

        data = ContributorCaseReadSerializer(
            submission, context={"request": request}
        ).data
        return Response(data, status=status.HTTP_200_OK)

    def _approve_submission(self, submission, reviewer, note):
        with transaction.atomic():
            case = Case.objects.create(
                gender=submission.gender,
                age=submission.age,
                city=submission.city,
                status=submission.status,
                severity=submission.severity,
                disease=submission.disease,
                location=submission.location,
                created_by=submission.created_by,
            )
            news_payload = submission.news_payload_for_case()
            if news_payload:
                News.objects.create(case=case, **news_payload)

            submission.state = ContributorCaseSubmission.ReviewState.APPROVED
            submission.review_note = note or ""
            submission.reviewed_at = timezone.now()
            submission.reviewed_by = reviewer
            submission.approved_case = case
            submission.updated_by = reviewer
            submission.save(
                update_fields=[
                    "state",
                    "review_note",
                    "reviewed_at",
                    "reviewed_by",
                    "approved_case",
                    "updated_by",
                    "updated_at",
                ]
            )
        return submission

    def _reject_submission(self, submission, reviewer, note):
        submission.state = ContributorCaseSubmission.ReviewState.REJECTED
        submission.review_note = note
        submission.reviewed_at = timezone.now()
        submission.reviewed_by = reviewer
        submission.updated_by = reviewer
        submission.save(
            update_fields=[
                "state",
                "review_note",
                "reviewed_at",
                "reviewed_by",
                "updated_by",
                "updated_at",
            ]
        )
        return submission


class ContributorApprovalRoleView(APIView): 
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsTokenAuthenticated, IsAdminAuthenticated]

    def get(self, request):
        roles = sorted(ContributorApprovalRole.allowed_role_names())
        return Response({"roles": roles}, status=status.HTTP_200_OK)

    def put(self, request):
        serializer = ContributorApprovalRoleUpdateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        ContributorApprovalRole.set_allowed_roles(serializer.role_objects)
        response_roles = [role.name for role in serializer.role_objects]
        return Response({"roles": response_roles}, status=status.HTTP_200_OK)
