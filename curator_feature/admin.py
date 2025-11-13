from django.contrib import admin
from .models import CuratorDataLog

@admin.register(CuratorDataLog)
class CuratorDataLogAdmin(admin.ModelAdmin):
    list_display = ("id", "data_id", "title", "submitted_by", "last_edited")
    list_filter = ("submitted_by",)
    search_fields = ("data_id", "title", "submitted_by")
    readonly_fields = ("data_id", "title", "submitted_by", "last_edited", "note")

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False
