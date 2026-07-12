from functools import wraps

from django.utils import timezone

from shared.Constants import FORBIDDEN, INACTIVE_USER, UNAUTHORIZED
from shared.utils import CustomResponse
from db.models import ApiKey
from shared.security import Security


def roles_required(*roles):
    def decorator(view_func):
        @wraps(view_func)
        def wrapper(self, request, *args, **kwargs):
            user = request.user
            if not user or not user.is_authenticated:
                return CustomResponse().errorResponse(
                    data={},
                    description=UNAUTHORIZED
                )
            if not user.is_active:
                return CustomResponse().errorResponse(
                    data={},
                    description=INACTIVE_USER
                )
            if user.role not in roles:
                return CustomResponse().errorResponse(
                    data={},
                    description=FORBIDDEN
                )
            return view_func(self, request, *args, **kwargs)
        return wrapper
    return decorator


# this decorator will be used for public api's
def api_key_required(view_func):

    @wraps(view_func)
    def wrapper(self, request, *args, **kwargs):
        api_key = request.headers.get("X-API-KEY")
        if not api_key:
            return CustomResponse().errorResponse(
                data={},
                description="API Key is required."
            )
        hashed_key = Security.hash_api_key(api_key)
        api_key_object = ApiKey.objects.filter(
            secret_hash=hashed_key,
            is_active=True
        ).select_related("organization").first()
        if not api_key_object:
            return CustomResponse().errorResponse(
                data={},
                description=UNAUTHORIZED
            )
        request.organization = api_key_object.organization
        request.api_key = api_key_object
        api_key_object.last_used_at = timezone.now()
        api_key_object.save(update_fields=["last_used_at"])
        return view_func(self, request, *args, **kwargs)
    return wrapper