from django.urls import path
from .views import hello_world, AllCaseLocationsView

urlpatterns = [
    path('', hello_world, name='hello_world'),
    path('cases/locations/', AllCaseLocationsView.as_view(), name='all-case-locations')
]
