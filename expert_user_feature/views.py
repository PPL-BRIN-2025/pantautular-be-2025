from rest_framework import generics, status
from rest_framework.response import Response

from authentication.security import CustomJWTAuthentication
from authentication.permissions import IsTokenAuthenticated
from .permissions import IsExpertUserRole
from .serializers import CaseWriteSerializer


class ExpertAddCaseRefactoredView(generics.CreateAPIView):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsTokenAuthenticated, IsExpertUserRole]
    serializer_class = CaseWriteSerializer
