import hashlib
import secrets

class Security:
    API_KEY_PREFIX = "sk_live_"
    @staticmethod
    def generate_api_key():
        return f"{Security.API_KEY_PREFIX}{secrets.token_urlsafe(32)}"

    @staticmethod
    def hash_api_key(api_key):
        return hashlib.sha256(
            api_key.encode("utf-8")
        ).hexdigest()

    @staticmethod
    def get_prefix(api_key):
        return api_key[:16]