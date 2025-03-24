from django.urls import path
from .views import AllCaseLocationsView, FiltersView, CaseGenderView, HealthcareNewsStatisticsView

urlpatterns = [
    path('cases/locations/', AllCaseLocationsView.as_view(), name='all-case-locations'),
    path('api/filters/', FiltersView.as_view(), name='filters'),
    path('api/cases/gender-distribution/', CaseGenderView.as_view(), name='gender-distribution'),
    path('api/healthcare-news/statistics/', HealthcareNewsStatisticsView.as_view(), name='healthcare-news-statistics'),
    path('api/healthcare-news/top-portal/', TopHealthcareNewsPortalView.as_view(), name='top-healthcare-news-portal'),
]
