from django.urls import path
from django.http import HttpResponse

def feature_placeholder(request):
    return HttpResponse("Expert User Feature Placeholder")

urlpatterns = [
    path("", feature_placeholder, name="expert-feature-placeholder"),
]
