from django.contrib.auth.backends import BaseBackend
from db.models import UserMaster


class EmailAuthenticationBackend(BaseBackend):
    def authenticate(self, request, email=None, password=None, **kwargs):
        try:
            user = UserMaster.objects.get(email=email)
        except UserMaster.DoesNotExist:
            return None
        if user.check_password(password):
            return user
        return None

    def get_user(self, user_id):
        try:
            return UserMaster.objects.get(pk=user_id)
        except UserMaster.DoesNotExist:
            return None