from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from rest_framework.throttling import UserRateThrottle
from .repositories import UserRepository
from .services import AuthService
from .serializers import SignupSerializer, LoginSerializer
from .security import APIKeyAuthentication
from authentication.registration.service import (
    RegistrationService,
    RegistrationError,
)

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