from django.urls import path
from .views import AllCaseLocationsView, CaseDetailView, FiltersView, SeverityDatesView
from .views import AllCaseLocationsView, FiltersView, CaseDetailView, SeverityDatesView

urlpatterns = [
    path('cases/locations/', AllCaseLocationsView.as_view(), name='all-case-locations'),
    path('api/filters/', FiltersView.as_view(), name='filters'),
    path('cases/<uuid:case_id>/', CaseDetailView.as_view(), name='case-detail'),
    path('api/severity-dates/', SeverityDatesView.as_view(), name='severity-dates'),
    path('cases/<uuid:case_id>/', CaseDetailView.as_view(), name='case-detail'),
]

