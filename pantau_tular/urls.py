"""
URL configuration for pantau_tular project.

The `urlpatterns` list routes URLs to views. For more information please see:
    https://docs.djangoproject.com/en/5.1/topics/http/urls/
Examples:
Function views
    1. Add an import:  from my_app import views
    2. Add a URL to urlpatterns:  path('', views.home, name='home')
Class-based views
    1. Add an import:  from other_app.views import Home
    2. Add a URL to urlpatterns:  path('', Home.as_view(), name='home')
Including another URLconf
    1. Import the include() function: from django.urls import include, path
    2. Add a URL to urlpatterns:  path('blog/', include('blog.urls'))
"""
from django.contrib import admin
from django.urls import path, include, re_path
from django_prometheus import exports
from django.http import JsonResponse
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from curator_feature.views import DashboardDownloadEventAPIView, DiseaseListCreateView

def health(request):               
    return JsonResponse({"status": "ok"})

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('pt_backend.urls')),
    path('metrics/', exports.ExportToDjangoView, name='prometheus-django-metrics'),
    path('authentication/', include("authentication.urls")),
    path('admin-feature/', include('admin_feature.urls')),
    path('api/downloads/log/', DashboardDownloadEventAPIView.as_view(), name='dashboard-download-log'),
    path('api/logs/', include('curator_feature.urls')),
    path('api/curator-feature/', include('curator_feature.urls')),
    # Backwards-compatible alias to canonical location (preserve POST behavior)
    path('api/diseases/', DiseaseListCreateView.as_view(), name='api-diseases-alias'),
    path('health/', health),
    path("", include("admin_feature.urls")),
    path("curator-feature/", include("curator_feature.urls")),
    path("auth/token/", TokenObtainPairView.as_view(), name="token_obtain_pair"),
    path("auth/token/refresh/", TokenRefreshView.as_view(), name="token_refresh"),
    path("expert-feature/", include("expert_user_feature.urls")),
    re_path(r"^news/?", include("news_feature.urls")),
    re_path(
        r"^api/news/?",
        include(("news_feature.urls", "news_feature"), namespace="news_feature_api"),
    ),
]
