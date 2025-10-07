from django.contrib import admin
from .models import AdminUserLog

@admin.register(AdminUserLog)
class AdminUserLogAdmin(admin.ModelAdmin):
    list_display = ("id", "username", "email", "detail", "timestamp")
    list_filter = ("detail",)
    search_fields = ("username", "email", "detail", "note")
    ordering = ("-timestamp",)
