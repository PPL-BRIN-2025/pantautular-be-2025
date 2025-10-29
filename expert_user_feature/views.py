from rest_framework import generics
from pt_backend.models import Case
from .views_base import ExpertBaseView
from .serializers import CaseWriteSerializer, CaseReadSerializer


class ExpertCaseCreateView(ExpertBaseView, generics.CreateAPIView):
    queryset = Case.objects.all()

    def get_serializer_class(self):
        return CaseWriteSerializer if self.request.method == "POST" else CaseReadSerializer
