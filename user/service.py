from django.contrib.auth import authenticate
from django.utils import timezone
from rest_framework_simplejwt.tokens import RefreshToken


class AuthService:
    @staticmethod
    def login(data):
        email = data.get("email")
        password = data.get("password")
        user = authenticate(
            email=email,
            password=password
        )
        if user is None:
            raise Exception("Invalid email or password.")
        if not user.is_active:
            raise Exception("User account is inactive.")
        if user.organization is None:
            raise Exception("Invalid login.")
        user.last_login = timezone.now()
        user.save(update_fields=["last_login"])
        refresh = RefreshToken.for_user(user)
        return {
            "access_token": str(refresh.access_token),
            "refresh_token": str(refresh),
            "user": user
        }
