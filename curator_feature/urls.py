from django.urls import path
from .views import CuratorCasesListAPIView

urlpatterns = [
    path("cases/", CuratorCasesListAPIView.as_view(), name="curator_cases_list"),
]
