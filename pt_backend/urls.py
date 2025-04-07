from django.urls import path
from .views import AllCaseLocationsView, FiltersView, CaseDetailView

urlpatterns = [
    path('cases/locations/', AllCaseLocationsView.as_view(), name='all-case-locations'),
    path('api/filters/', FiltersView.as_view(), name='filters'),
    path('cases/<uuid:case_id>/', CaseDetailView.as_view(), name='case-detail'),
]

