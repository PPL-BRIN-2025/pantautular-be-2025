from django.urls import path
from .views import AllCaseLocationsView, FiltersView, DiseaseCaseInfoView

urlpatterns = [
    path('cases/locations/', AllCaseLocationsView.as_view(), name='all-case-locations'),
    path('api/filters/', FiltersView.as_view(), name='filters'),
    path('api/dashboard/disease-case-info/', DiseaseCaseInfoView.as_view(), name='disease-case-info'),
]
