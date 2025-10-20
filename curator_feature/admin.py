from django.contrib import admin
from .models import CuratorDataLog

@admin.register(CuratorDataLog)
class CuratorDataLogAdmin(admin.ModelAdmin):
    list_display = ("id", "data_id", "title", "submitted_by", "last_edited")
    list_filter = ("submitted_by",)
    search_fields = ("data_id", "title", "submitted_by")
