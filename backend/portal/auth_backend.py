from .auth_user import HrAuthUser
from .models import User


class HrSessionBackend:
    """Session auth for HR users provisioned via Google OAuth (no password login)."""

    def authenticate(self, request, **kwargs):
        return None

    def get_user(self, user_id):
        try:
            db_user = User.objects.get(pk=user_id, is_active=True)
        except User.DoesNotExist:
            return None
        return HrAuthUser(db_user)
