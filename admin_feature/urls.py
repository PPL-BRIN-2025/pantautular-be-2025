from django.urls import path
from .views import RolesSummaryAPIView, FailedLoginStatsAPIView, FailedLoginEventsAPIView
from .views import UsersSummaryAPIView, DatasetsSummaryAPIView

urlpatterns = [
    path('roles/', RolesSummaryAPIView.as_view(), name='admin-roles-summary'),
    path('failed-logins/', FailedLoginStatsAPIView.as_view(), name='admin-failed-login-stats'),
    path('failed-logins/logs', FailedLoginEventsAPIView.as_view(), name='admin-failed-login-logs'),
    path('users/summary', UsersSummaryAPIView.as_view(), name='admin-users-summary'),
    path('datasets/summary', DatasetsSummaryAPIView.as_view(), name='admin-datasets-summary'),
]
