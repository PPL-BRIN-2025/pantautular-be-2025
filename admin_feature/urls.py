from django.urls import path
from .views import AdminUserListView, AdminUserDeleteView, AdminUserChangeRoleView

urlpatterns = [
    path("users", AdminUserListView.as_view(), name="admin-user-list"),
    path("users/<int:id>", AdminUserDeleteView.as_view(), name="admin-user-delete"),
    path("users/<int:id>/role", AdminUserChangeRoleView.as_view(), name="admin-user-change-role"),
]
