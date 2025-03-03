from django.urls import path
from .views import FiltersView

urlpatterns = [
    path('api/filters/', FiltersView.as_view(), name='filters'),
]