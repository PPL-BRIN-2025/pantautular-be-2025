from django.contrib import admin

from .models import ContributorApprovalRole, ContributorCaseSubmission


@admin.register(ContributorCaseSubmission)
class ContributorCaseSubmissionAdmin(admin.ModelAdmin):
    list_display = ("id", "disease", "city", "state", "created_by", "created_at")
    list_filter = ("state", "disease__name", "created_at")
    search_fields = ("id", "city", "created_by__email", "created_by__name")
    readonly_fields = ("approved_case", "created_at", "updated_at")


@admin.register(ContributorApprovalRole)
class ContributorApprovalRoleAdmin(admin.ModelAdmin):
    list_display = ("role", "created_at")
    search_fields = ("role__name",)
