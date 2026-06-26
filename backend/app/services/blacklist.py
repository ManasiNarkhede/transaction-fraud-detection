"""Blacklist service for IPs and device fingerprints."""

import logging

from app.infrastructure.redis_client import get_redis
from app.services.key_builder import KeyBuilder

logger = logging.getLogger(__name__)


class Blacklist:
    """Manages blacklisted IPs and device fingerprints in Redis."""

    async def is_ip_blacklisted(self, ip: str) -> bool:
        """Check if an IP address is blacklisted."""
        redis_client = get_redis()
        if redis_client is None:
            return False
        try:
            key = KeyBuilder.blacklist_ip(ip)
            result = await redis_client.exists(key)
            return bool(result > 0)
        except Exception as exc:
            logger.warning(
                "ip_blacklist_check_failed", extra={"ip": ip, "error": str(exc)}
            )
            return False

    async def is_device_blacklisted(self, fingerprint: str) -> bool:
        """Check if a device fingerprint is blacklisted."""
        redis_client = get_redis()
        if redis_client is None:
            return False
        try:
            key = KeyBuilder.blacklist_device(fingerprint)
            result = await redis_client.exists(key)
            return bool(result > 0)
        except Exception as exc:
            logger.warning(
                "device_blacklist_check_failed",
                extra={"fingerprint": fingerprint, "error": str(exc)},
            )
            return False

    async def blacklist_ip(self, ip: str, ttl: int = 86400) -> bool:
        """Add an IP address to the blacklist."""
        redis_client = get_redis()
        if redis_client is None:
            return False
        try:
            key = KeyBuilder.blacklist_ip(ip)
            await redis_client.set(key, 1, ex=ttl)
            return True
        except Exception as exc:
            logger.warning(
                "ip_blacklist_set_failed", extra={"ip": ip, "error": str(exc)}
            )
            return False

    async def blacklist_device(self, fingerprint: str, ttl: int = 86400) -> bool:
        """Add a device fingerprint to the blacklist."""
        redis_client = get_redis()
        if redis_client is None:
            return False
        try:
            key = KeyBuilder.blacklist_device(fingerprint)
            await redis_client.set(key, 1, ex=ttl)
            return True
        except Exception as exc:
            logger.warning(
                "device_blacklist_set_failed",
                extra={"fingerprint": fingerprint, "error": str(exc)},
            )
            return False
