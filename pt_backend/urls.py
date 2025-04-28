from django.urls import path
from .views import (AllCaseLocationsView, CitySeverityStatsView, 
                    DiseaseSeverityStatsView, CaseDetailView, FiltersView, 
                    StatisticsView, LocationSeverityStatsView, SeverityFilteringStatsView,
                    ProvinceHumidityView)

urlpatterns = [
    path('cases/locations/', AllCaseLocationsView.as_view(), name='all-case-locations'),
    path('api/filters/', FiltersView.as_view(), name='filters'),
    path('cases/<uuid:case_id>/', CaseDetailView.as_view(), name='case-detail'),
    path('api/diseases/severity-stats/', DiseaseSeverityStatsView.as_view(), name='disease-severity-stats'),
    path('api/locations/province/severity-stats/', LocationSeverityStatsView.as_view(), name='province-severity-stats'),
    path('api/locations/city/severity-stats/', CitySeverityStatsView.as_view(), name='city-severity-stats'),
    path('api/severity-stats/filter/', SeverityFilteringStatsView.as_view(), name='severity-filtering-stats'),
    path('api/statistics/', StatisticsView.as_view(), name='statistics'),
    path('api/province-humidity/', ProvinceHumidityView.as_view(), name='province-humidity'),
]
