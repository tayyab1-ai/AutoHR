"""Lightweight user wrapper for Django session auth against portal.models.User."""


class HrAuthUser:
    """Minimal interface Django expects for login() / get_user()."""

    def __init__(self, db_user):
        self.db_user = db_user

    @property
    def _meta(self):
        """Let Django session auth serialize our UUID pk (login() needs _meta.pk)."""
        return self.db_user._meta

    @property
    def pk(self):
        return self.db_user.pk

    @property
    def id(self):
        return self.db_user.id

    @property
    def email(self):
        return self.db_user.email

    @property
    def is_authenticated(self):
        return True

    @property
    def is_anonymous(self):
        return False

    @property
    def is_active(self):
        return bool(self.db_user.is_active)

    def get_username(self):
        return self.db_user.email

    def save(self, update_fields=None, **kwargs):
        """No-op for Django auth signals (portal User has no last_login field)."""
        pass
