from django.contrib.auth.hashers import check_password

from .auth_user import HrAuthUser
from .models import User


class HrEmailBackend:
    """Authenticate HR users by email + password stored in PostgreSQL users.password_hash."""

    def authenticate(self, request, email=None, username=None, password=None, **kwargs):
        email = (email or kwargs.get("email") or username or "").strip().lower()
        if not email or password is None or password == "":
            return None
        db_user = User.objects.filter(email__iexact=email, is_active=True).first()
        if not db_user or not db_user.password_hash:
            return None
        stored = db_user.password_hash.strip()
        if not check_password(password, stored):
            return None
        return HrAuthUser(db_user)

    def get_user(self, user_id):
        try:
            db_user = User.objects.get(pk=user_id, is_active=True)
        except User.DoesNotExist:
            return None
        return HrAuthUser(db_user)
