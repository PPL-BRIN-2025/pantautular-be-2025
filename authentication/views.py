from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.exceptions import ParseError
from rest_framework.throttling import UserRateThrottle
from pt_backend.models import User

from authentication.throttling import PasswordResetRateThrottle
from .serializers import SignupSerializer, ChangePasswordSerializer
from .services import ChangePasswordService
from rest_framework.throttling import UserRateThrottle
# from .repositories import UserRepository
from .repository import UserRepository
from .services import (
    AuthService, 
    UserFinderService, 
    PasswordTokenService, 
    ResetLinkService, 
    PasswordResetService
)
from .serializers import SignupSerializer, LoginSerializer
from .security import APIKeyAuthentication
from authentication.registration.service import (
    RegistrationService,
    RegistrationError,
)

from .services import (ChangePasswordService, PasswordValidationService)
from rest_framework_simplejwt.tokens import AccessToken
import jwt

from django.conf import settings
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
    throttle_classes = [PasswordResetRateThrottle]

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Initialize all required services with proper dependency injection
        repository = UserRepository()
        user_finder = UserFinderService(repository)
        password_token_service = PasswordTokenService(repository)
        reset_link_service = ResetLinkService()
        
        self.password_reset_service = PasswordResetService(
            user_finder=user_finder,
            password_token_service=password_token_service,
            reset_link_service=reset_link_service
        )

    def post(self, request):
        try:
            email = request.data.get("email")
            if not email:
                return Response({"error": "Email is required"}, status=status.HTTP_400_BAD_REQUEST)
            
            # Use the new method name from the updated service
            success = self.password_reset_service.initiate_password_reset(email)
            
            # Always return a generic message for security (regardless of success)
            return Response(
                {"message": "Jika akunmu terdaftar, kami sudah mengirim link untuk mereset password akun Anda"},
                status=status.HTTP_200_OK
            )
        
        except ParseError:
            return Response({"error": "Invalid JSON in request body"}, status=status.HTTP_400_BAD_REQUEST)

        except User.DoesNotExist:
            # Still return generic message even when user doesn't exist
            return Response(
                {"message": "Jika akunmu terdaftar, kami sudah mengirim link untuk mereset password akun Anda"},
                status=status.HTTP_200_OK
            )
        
        except Exception as e:
            logger.error(f"Error sending password reset link: {str(e)}")
            return Response({"error": INTERNAL_SERVER_ERR_MSG}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class PasswordResetLinkValidateView(APIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = []
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        # Initialize all required services with proper dependency injection
        repository = UserRepository()
        user_finder = UserFinderService(repository)
        password_token_service = PasswordTokenService(repository)
        reset_link_service = ResetLinkService()
        
        self.password_reset_service = PasswordResetService(
            user_finder=user_finder,
            password_token_service=password_token_service,
            reset_link_service=reset_link_service
        )

    def get(self, request, uidb64, token):
        # Use the new verify_reset_attempt method that handles both getting the user and validating the token
        user = self.password_reset_service.verify_reset_attempt(uidb64, token)
        
        if user:
            return Response({"valid": True}, status=status.HTTP_200_OK)
        else:
            return Response({"valid": False}, status=status.HTTP_400_BAD_REQUEST)

class PasswordResetConfirmView(APIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = []

    def __init__(self, **kwargs):
        self.password_token_service = PasswordTokenService(UserRepository())
        self.password_validation_service = PasswordValidationService()
        self.change_password_service = ChangePasswordService()

    def post(self, request, uidb64, token):
        new_password = request.data.get("password")
        if not new_password:
            return Response({"detail": "Password diperlukan"}, status=status.HTTP_400_BAD_REQUEST)
        
        new_password_confirm = request.data.get("password-confirm")
        if not new_password_confirm:
            return Response({"detail": "Konfirmasi password diperlukan"}, status=status.HTTP_400_BAD_REQUEST)

        if not self.password_validation_service.validate_password_match(new_password, new_password_confirm):
            return Response({"detail": "Password tidak cocok"}, status=status.HTTP_400_BAD_REQUEST)
        
        is_valid, error_message = self.password_validation_service.validate_password_strength(new_password)
        if not is_valid:
            return Response({"detail": error_message}, status=status.HTTP_400_BAD_REQUEST)
        
        user = self.password_token_service.get_user_from_uidb64(uidb64)
        if not user:
            return Response({"detail": "Link tidak valid"}, status=status.HTTP_400_BAD_REQUEST)

        if not self.password_token_service.validate_token(user, token):
            return Response({"detail": "Token tidak valid atau sudah kedaluwarsa"}, status=status.HTTP_400_BAD_REQUEST)

        if not self.change_password_service.change_password(user.email, new_password):
            return Response({"detail": "Gagal mengganti password"}, status=status.HTTP_400_BAD_REQUEST)
            
        return Response({"detail": "Password berhasil diganti"}, status=status.HTTP_200_OK)
    
class ChangePasswordView(APIView):
    authentication_classes = [APIKeyAuthentication]
    permission_classes = []
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.service = ChangePasswordService()
    
    def post(self, request):
        try:
            # Extract JWT token from Authorization header
            auth_header = request.headers.get('Authorization')
            if not auth_header or not auth_header.startswith('Bearer '):
                return Response(
                    {"error": "Authentication token required"}, 
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            token = auth_header.split(' ')[1]
            
            # Decode JWT token manually
            try:
                # Use the same algorithm and key as used in AuthService.login()
                payload = jwt.decode(token, settings.SECRET_KEY, algorithms=['HS256'])
                user_id = payload.get('user_id')
                
                if not user_id:
                    return Response(
                        {"error": "Invalid token"}, 
                        status=status.HTTP_401_UNAUTHORIZED
                    )
                
                # Retrieve user from database
                user = User.objects.get(id=user_id)
                
                # Proceed with password change using retrieved user
                serializer = ChangePasswordSerializer(
                    data=request.data, 
                    context={'user': user}  # Use retrieved user
                )
                
                if not serializer.is_valid():
                    return Response(
                        serializer.errors, 
                        status=status.HTTP_400_BAD_REQUEST
                    )
                
                result = self.service.update_user_password(
                    user,  # Use retrieved user
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
                
            except jwt.ExpiredSignatureError:
                return Response(
                    {"error": "Token expired"}, 
                    status=status.HTTP_401_UNAUTHORIZED
                )
            except jwt.InvalidTokenError:
                return Response(
                    {"error": "Invalid token"}, 
                    status=status.HTTP_401_UNAUTHORIZED
                )
            except User.DoesNotExist:
                return Response(
                    {"error": "User not found"}, 
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
        except Exception as e:
            logger.error(f"Error changing password: {str(e)}")
            return Response(
                {"error": f"An error occurred: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class LoginAPIView(APIView):
    authentication_classes = [APIKeyAuthentication]
    throttle_classes = [UserRateThrottle]
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        user_repository = UserRepository()
        self.auth_service = AuthService(user_repository)

    def post(self, request):
        serializer = LoginSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        
        try:
            tokens = self.auth_service.login(
                email=serializer.validated_data['email'],
                password=serializer.validated_data['password']
            )

            if tokens and isinstance(tokens, dict) and tokens.get('locked'):
                return Response(
                    {"detail": tokens['message']},
                    status=status.HTTP_423_LOCKED
                )
            
            if not tokens:
                return Response(
                    {"detail": "Invalid email or password"},
                    status=status.HTTP_401_UNAUTHORIZED
                )
            
            return Response(
                {
                    "detail": "Login successful",
                    "access_token": tokens["access_token"]
                },
                status=status.HTTP_200_OK
            )
            
        except Exception:
            return Response(
                {"detail": "Login failed. Please try again."},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )