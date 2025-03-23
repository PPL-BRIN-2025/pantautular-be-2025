from django.urls import path
from .views import AllCaseLocationsView, FiltersView, PrevalenceView

urlpatterns = [
    path('cases/locations/', AllCaseLocationsView.as_view(), name='all-case-locations'),
    path('api/filters/', FiltersView.as_view(), name='filters'),
    path('cases/prevalence/', PrevalenceView.as_view(), name='prevalence'),
]
