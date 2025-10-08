from django.shortcuts import render

# Create your views here.
from rest_framework import generics
from authentication.security import CustomJWTAuthentication
from authentication.permissions import IsTokenAuthenticated
from .permissions import IsCuratorRole
from .serializers import CaseWriteSerializer, CaseReadSerializer
from pt_backend.models import Case


class _CuratorBaseView(generics.GenericAPIView):
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsTokenAuthenticated, IsCuratorRole]


class CuratorCaseListCreateView(_CuratorBaseView, generics.ListCreateAPIView):
    queryset = Case.objects.select_related("disease", "location").prefetch_related("news").order_by("-id")

    def get_serializer_class(self):
        return CaseReadSerializer if self.request.method == "GET" else CaseWriteSerializer
