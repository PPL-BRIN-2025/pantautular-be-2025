from django.urls import path
from .views import AllCaseLocationsView

urlpatterns = [
    path('cases/locations/', AllCaseLocationsView.as_view(), name='all-case-locations')
]
