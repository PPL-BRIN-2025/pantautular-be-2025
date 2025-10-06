from django.contrib.auth.signals import user_logged_in, user_logged_out, user_login_failed
from django.dispatch import receiver
from admin_feature.audittrail import write_log

@receiver(user_logged_in)
def _on_login(sender, request, user, **kwargs):
    write_log(request=request, user=user, action="LOGIN", detail="User logged in")

@receiver(user_logged_out)
def _on_logout(sender, request, user, **kwargs):
    write_log(request=request, user=user, action="LOGOUT", detail="User logged out")

@receiver(user_login_failed)
def _on_login_failed(sender, credentials, request, **kwargs):
    username = (credentials or {}).get("username", "")
    write_log(request=request, user=None, action="LOGIN_FAILED", detail=f"Login failed for {username}")
