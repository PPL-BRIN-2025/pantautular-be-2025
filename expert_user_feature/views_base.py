from rest_framework import generics
from authentication.security import CustomJWTAuthentication
from authentication.permissions import IsTokenAuthenticated
from .permissions import IsExpertUserRole


class ExpertBaseView(generics.GenericAPIView):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsTokenAuthenticated, IsExpertUserRole]
