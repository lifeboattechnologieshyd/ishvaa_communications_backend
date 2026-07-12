from db.models import ApiKey
from shared.security import Security


class ApiKeyService:
    @staticmethod
    def create_api_key(user, data):
        api_key = Security.generate_api_key()
        exists = ApiKey.objects.filter(
            organization=user.organization,
            name=data.get("name")
        ).exists()
        if exists:
            raise Exception("API Key name already exists.")

        api_key_object = ApiKey.objects.create(
            organization=user.organization,
            name=data.get("name"),
            prefix=Security.get_prefix(api_key),
            secret_hash=Security.hash_api_key(api_key)
        )
        return {
            "id": str(api_key_object.id),
            "name": api_key_object.name,
            "api_key": api_key
        }

    @staticmethod
    def list_api_keys(user):
        api_keys = ApiKey.objects.filter(
            organization=user.organization,
            is_active=True
        ).values(
            "id",
            "name",
            "prefix",
            "last_used_at",
            "created_at",
            "expires_at"
        ).order_by("-created_at")
        return list(api_keys)