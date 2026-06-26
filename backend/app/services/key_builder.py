"""Cache key naming utility."""


class KeyBuilder:
    """Builds Redis cache keys with consistent fraudguard: prefix."""

    _PREFIX = "fraudguard"

    @staticmethod
    def user_profile(user_id: str) -> str:
        """Key for user profile data."""
        return f"{KeyBuilder._PREFIX}:user:profile:{user_id}"

    @staticmethod
    def user_history(user_id: str) -> str:
        """Key for user transaction history."""
        return f"{KeyBuilder._PREFIX}:user:history:{user_id}"

    @staticmethod
    def fraud_rules(owner_id: str) -> str:
        """Key for a user's fraud rules configuration."""
        return f"{KeyBuilder._PREFIX}:fraud:rules:{owner_id}"

    @staticmethod
    def blacklist_ip(ip: str) -> str:
        """Key for blacklisted IP."""
        return f"{KeyBuilder._PREFIX}:blacklist:ip:{ip}"

    @staticmethod
    def blacklist_device(fingerprint: str) -> str:
        """Key for blacklisted device fingerprint."""
        return f"{KeyBuilder._PREFIX}:blacklist:device:{fingerprint}"

    @staticmethod
    def rate_limit(entity: str, window: str) -> str:
        """Key for rate limit counter."""
        return f"{KeyBuilder._PREFIX}:ratelimit:{entity}:{window}"

    @staticmethod
    def feature_vector(user_id: str) -> str:
        """Key for cached ML feature vector."""
        return f"{KeyBuilder._PREFIX}:ml:features:{user_id}"
