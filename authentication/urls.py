from django.urls import path
from .views import (SignupAPIView, PasswordResetLinkRequestView, 
                    PasswordResetLinkValidateView, PasswordResetConfirmView)

urlpatterns = [
    path('register', SignupAPIView.as_view(), name='sign-up'),
    path('password-reset-request', PasswordResetLinkRequestView.as_view(), name='password-reset-request'),
    path('password-reset-validate/<str:uidb64>/<str:token>', PasswordResetLinkValidateView.as_view(), name='password-reset-validate'),
    path('password-reset-confirm/<str:uidb64>/<str:token>', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
]