from django.urls import path
from .views import AllCaseLocationsView, FiltersView, StatisticsView

urlpatterns = [
    path('cases/locations/', AllCaseLocationsView.as_view(), name='all-case-locations'),
    path('api/filters/', FiltersView.as_view(), name='filters'),
    path('api/dashboard/disease-case-info/', StatisticsView.as_view(), name='statistics'),
]

