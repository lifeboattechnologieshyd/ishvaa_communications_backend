from functools import wraps

from db.models import UserRole
from shared.Constants import FORBIDDEN, INVALID_ORGANIZATION
from shared.decorators import roles_required
from shared.enums import PortalType
from shared.utils import CustomResponse


def super_admin_required(view_func):
    @wraps(view_func)
    @roles_required(UserRole.OWNER)
    def wrapper(self, request, *args, **kwargs):
        if request.user.organization is not None:
            return CustomResponse().errorResponse(
                data={},
                description=FORBIDDEN
            )
        return view_func(self, request, *args, **kwargs)
    return wrapper

def organization_owner_required(view_func):
    @wraps(view_func)
    @roles_required(UserRole.OWNER)
    def wrapper(self, request, *args, **kwargs):
        if request.user.organization is None:
            return CustomResponse().errorResponse(
                data={},
                description=INVALID_ORGANIZATION
            )
        return view_func(self, request, *args, **kwargs)
    return wrapper

def organization_admin_required(view_func):
    @wraps(view_func)
    @roles_required(UserRole.ADMIN)
    def wrapper(self, request, *args, **kwargs):
        if request.user.organization is None:
            return CustomResponse().errorResponse(
                data={},
                description=INVALID_ORGANIZATION
            )
        return view_func(self, request, *args, **kwargs)
    return wrapper

def organization_member_required(view_func):
    @wraps(view_func)
    @roles_required(UserRole.MEMBER)
    def wrapper(self, request, *args, **kwargs):
        if request.user.organization is None:
            return CustomResponse().errorResponse(
                data={},
                description=INVALID_ORGANIZATION
            )
        return view_func(self, request, *args, **kwargs)
    return wrapper


def organization_management_required(view_func):
    @wraps(view_func)
    @roles_required(UserRole.OWNER, UserRole.ADMIN)
    def wrapper(self, request, *args, **kwargs):
        if request.user.organization is None:
            return CustomResponse().errorResponse(
                data={},
                description=INVALID_ORGANIZATION
            )
        return view_func(self, request, *args, **kwargs)
    return wrapper

def organization_user_required(view_func):
    @wraps(view_func)
    @roles_required(
        UserRole.OWNER,
        UserRole.ADMIN,
        UserRole.MEMBER
    )

    def wrapper(self, request, *args, **kwargs):
        if request.user.organization is None:
            return CustomResponse().errorResponse(
                data={},
                description=INVALID_ORGANIZATION
            )
        return view_func(self, request, *args, **kwargs)
    return wrapper