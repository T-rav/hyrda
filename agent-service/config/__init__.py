"""Configuration module with cached settings."""

from functools import lru_cache

from .settings import Settings

# Global settings cache - instantiated once and reused
_settings_instance: Settings | None = None


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Get cached settings instance (thread-safe, instantiated once).

    Use this instead of Settings() to avoid repeated .env reads.
    """
    global _settings_instance
    if _settings_instance is None:
        _settings_instance = Settings()
    return _settings_instance


__all__ = ["Settings", "get_settings"]
