from django.urls import path
from .views import (SignupAPIView, LoginAPIView)

urlpatterns = [
    path('register', SignupAPIView.as_view(), name='sign-up'),
    path('login', LoginAPIView.as_view(), name='login'),
]
