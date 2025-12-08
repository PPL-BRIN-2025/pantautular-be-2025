from django.urls import path
from .views import (AllCaseLocationsView, SpatialComparisonView, CitySeverityStatsView, 
                    DiseaseSeverityStatsView, CaseDetailView, FiltersView, 
                    StatisticsView, LocationSeverityStatsView, SeverityFilteringStatsView,
                    ProvinceHumidityView, ProvincePrecipitationView, ProvinceTemperatureView,
                    WeightedSeverityAnalysisView, SafeCaseLookupAPIView)
from . import views

urlpatterns = [
    path('cases/locations/', AllCaseLocationsView.as_view(), name='all-case-locations'),
    path('cases/spatial-comparisons/', SpatialComparisonView.as_view(), name='spatial-comparisons'),
    path('api/filters/', FiltersView.as_view(), name='filters'),
    path('cases/<uuid:case_id>/', CaseDetailView.as_view(), name='case-detail'),
    path('api/diseases/severity-stats/', DiseaseSeverityStatsView.as_view(), name='disease-severity-stats'),
    path('api/locations/province/severity-stats/', LocationSeverityStatsView.as_view(), name='province-severity-stats'),
    path('api/locations/city/severity-stats/', CitySeverityStatsView.as_view(), name='city-severity-stats'),
    path('api/severity-stats/filter/', SeverityFilteringStatsView.as_view(), name='severity-filtering-stats'),
    path('api/statistics/', StatisticsView.as_view(), name='statistics'),
    path('api/province-humidity/', ProvinceHumidityView.as_view(), name='province-humidity'),
    path('api/province-precipitation/', ProvincePrecipitationView.as_view(), name='province-precipitation'),
    path('api/province-temperature/', ProvinceTemperatureView.as_view(), name='province-temperature'),
    path('api/province-weighted-severity/', WeightedSeverityAnalysisView.as_view(), name='province-weighted-severity'),
    path('api/cases/safe-lookup/', SafeCaseLookupAPIView.as_view(), name='cases-safe-lookup'),
    path('health/', views.health_check, name='health_check'),
]
