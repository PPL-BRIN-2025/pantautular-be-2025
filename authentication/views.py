from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ParseError
from rest_framework.throttling import UserRateThrottle
from pt_backend.models import User

from .serializers import SignupSerializer, ChangePasswordSerializer
from .services import ChangePasswordService
from .security import APIKeyAuthentication
from authentication.registration.service import (
    RegistrationService,
    RegistrationError,
)

from .services import PasswordResetService

import logging

logger = logging.getLogger(__name__)

INTERNAL_SERVER_ERR_MSG = "An unexpected error occurred. Please try again later."

class SignupAPIView(APIView):

    authentication_classes = [APIKeyAuthentication]
    permission_classes     = []                  
    throttle_classes       = [UserRateThrottle]  

    def post(self, request):
        serializer = SignupSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)       

        try:
            dto = RegistrationService.register_user(
                role_name="TENAGA_AHLI",
                **serializer.validated_data,
            )
        except RegistrationError as exc:
            return Response({"detail": str(exc)}, status=status.HTTP_400_BAD_REQUEST)

        return Response({"id": dto.user.id}, status=status.HTTP_201_CREATED)

class PasswordResetLinkRequestView(APIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = []

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.password_reset_service = PasswordResetService()

    def post(self, request):
        try:
            email = request.data.get("email")
            if not email:
                return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)
            
            self.password_reset_service.process_reset_request(email)
            return Response({"message": "Jika akunmu terdaftar, kami sudah mengirim link untuk mereset password akun Anda"},
                             status=status.HTTP_200_OK)
        
        except ParseError:
            return Response({"error": "Invalid JSON in request body"}, status=status.HTTP_400_BAD_REQUEST)

        except User.DoesNotExist:
            return Response({"message": "Jika akunmu terdaftar, kami sudah mengirim link untuk mereset password akun Anda"},
                             status=status.HTTP_200_OK)
        
        except Exception as e:
            logger.error(f"Error sending password reset link: {str(e)}")
            return Response({"error": INTERNAL_SERVER_ERR_MSG}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
class PasswordResetLinkValidateView(APIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = []
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.password_reset_service = PasswordResetService()

    def get(self, request, uidb64, token):
        user = self.password_reset_service.get_user_from_uidb64(uidb64)
        if not user:
            return Response({"valid": False}, status=status.HTTP_400_BAD_REQUEST)

        if self.password_reset_service.validate_token(user, token):
            return Response({"valid": True}, status=status.HTTP_200_OK)
        return Response({"valid": False}, status=status.HTTP_400_BAD_REQUEST)

class ChangePasswordView(APIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = []
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = ChangePasswordService()
    
    def post(self, request):
        try:
            # Pastikan user ada dalam request dengan pengecekan yang lebih sederhana
            if not request.user or not hasattr(request.user, 'email'):
                return Response(
                    {"error": "Authentication required"}, 
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            # Validasi input
            serializer = ChangePasswordSerializer(
                data=request.data, 
                context={'user': request.user}
            )
            
            if not serializer.is_valid():
                return Response(
                    serializer.errors, 
                    status=status.HTTP_400_BAD_REQUEST
                )
            
            # Jalankan service
            result = self.service.update_user_password(
                request.user,
                serializer.validated_data['current_password'],
                serializer.validated_data['new_password']
            )
            
            if not result["success"]:
                return Response(
                    {"error": result["error"]},
                    status=status.HTTP_400_BAD_REQUEST
                )
                
            return Response(
                {"message": result["message"]},
                status=status.HTTP_200_OK
            )
            
        except Exception as e:
            logger.error(f"Error changing password: {str(e)}")
            return Response(
                {"error": f"An error occurred: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )