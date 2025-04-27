from django.urls import path
from .views import (SignupAPIView, PasswordResetLinkRequestView, 
                    PasswordResetLinkRequestView,
                    PasswordResetLinkValidateView,
                    ChangePasswordView)

urlpatterns = [
    path('register', SignupAPIView.as_view(), name='sign-up'),
    path('password-reset-request', PasswordResetLinkRequestView.as_view(), name='password-reset-request'),
    path('password-reset-validate/<str:uidb64>/<str:token>', PasswordResetLinkRequestView.as_view(), name='password-reset-validate'),
    path('password-reset-validate/<str:uidb64>/<str:token>', PasswordResetLinkValidateView.as_view(), name='password-reset-validate'),
    path('api/auth/change-password/', ChangePasswordView.as_view(), name='change-password'),
]