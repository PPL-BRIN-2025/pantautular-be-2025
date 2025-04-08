from django.urls import path
from .views import AllCaseLocationsView, FiltersView, SeverityDatesView

urlpatterns = [
    path('cases/locations/', AllCaseLocationsView.as_view(), name='all-case-locations'),
    path('api/filters/', FiltersView.as_view(), name='filters'),
    path('api/severity-dates/', SeverityDatesView.as_view(), name='severity-dates'),
]

