from django.urls import path
from .views import AllCaseLocationsView, FiltersView, CaseGenderView

urlpatterns = [
    path('cases/locations/', AllCaseLocationsView.as_view(), name='all-case-locations'),
    path('api/filters/', FiltersView.as_view(), name='filters'),
    path('api/cases/gender-distribution/', CaseGenderView.as_view(), name='gender-distribution')
]

