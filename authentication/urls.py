from django.urls import path
from .views import (SignupAPIView, PasswordResetLinkRequestView, 
                    PasswordResetLinkRequestView, PasswordResetLinkValidateView,
                    PasswordResetConfirmView, ChangePasswordView, LoginAPIView)

urlpatterns = [
    path('register', SignupAPIView.as_view(), name='sign-up'),
    path('login', LoginAPIView.as_view(), name='login'),
    path('password-reset-request', PasswordResetLinkRequestView.as_view(), name='password-reset-request'),
    path('password-reset-validate/<str:uidb64>/<str:token>', PasswordResetLinkValidateView.as_view(), name='password-reset-validate'),
    path('password-reset-confirm/<str:uidb64>/<str:token>', PasswordResetConfirmView.as_view(), name='password-reset-confirm'),
    path('api/auth/change-password/', ChangePasswordView.as_view(), name='change-password'),
]

