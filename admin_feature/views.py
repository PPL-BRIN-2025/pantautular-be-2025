from django.shortcuts import render
from rest_framework.views import APIView
from rest_framework.generics import ListAPIView, DestroyAPIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from authentication.security import CustomJWTAuthentication
from authentication.permissions import IsTokenAuthenticated
from .permissions import IsAdminRole
from .serializers import UserSerializer
from pt_backend.models import User, Role, UserRole

class AdminUserChangeRoleView(APIView):
    """
    PUT /admin/users/<int:id>/role
    Body: { "role_id": 2 }  or  { "role_name": "Curator" }
    Behavior:
      - Update string flag user.role
      - Replace all rows in UserRole for that user with the chosen role (single-role policy)
    """
    authentication_classes = [CustomJWTAuthentication]
    permission_classes = [IsTokenAuthenticated, IsAdminRole]

    @transaction.atomic
    def put(self, request, id):
        try:
            user = User.objects.get(id=id)
        except User.DoesNotExist:
            return Response({"detail": "User not found"}, status=status.HTTP_404_NOT_FOUND)

        role_obj = None
        role_id = request.data.get("role_id")
        role_name = request.data.get("role_name")

        if role_id is not None:
            role_obj = Role.objects.filter(id=role_id).first()
        elif role_name:
            role_obj = Role.objects.filter(name=role_name).first()

        if role_obj is None:
            return Response({"detail": "Invalid role"}, status=status.HTTP_400_BAD_REQUEST)

        # Update string flag (for quick checks in your existing code paths)
        user.role = role_obj.name
        user.save(update_fields=["role"])

        # Replace mapping in UserRole to reflect the chosen role (single-role model)
        UserRole.objects.filter(user=user).delete()
        UserRole.objects.create(user=user, role=role_obj)

        return Response(UserSerializer(user).data, status=status.HTTP_200_OK)
