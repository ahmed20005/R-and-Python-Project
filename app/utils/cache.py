import redis
import json
from typing import Optional, Any
from app.utils.config import get_settings
from app.utils.logger import get_logger

settings = get_settings()
logger = get_logger()


class RedisCache:
    def __init__(self):
        self.client = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            db=settings.REDIS_DB,
            decode_responses=True
        )
        self.default_expire = settings.CACHE_EXPIRE_SECONDS
    
    def get(self, key: str) -> Optional[Any]:
        try:
            value = self.client.get(key)
            if value:
                logger.debug(f"Cache hit for key: {key}")
                return json.loads(value)
            logger.debug(f"Cache miss for key: {key}")
            return None
        except Exception as e:
            logger.error(f"Error getting cache key {key}: {e}")
            return None
    
    def set(self, key: str, value: Any, expire: Optional[int] = None) -> bool:
        try:
            expire_time = expire or self.default_expire
            self.client.setex(key, expire_time, json.dumps(value))
            logger.debug(f"Cached key: {key} with expire: {expire_time}s")
            return True
        except Exception as e:
            logger.error(f"Error setting cache key {key}: {e}")
            return False
    
    def delete(self, key: str) -> bool:
        try:
            self.client.delete(key)
            logger.debug(f"Deleted cache key: {key}")
            return True
        except Exception as e:
            logger.error(f"Error deleting cache key {key}: {e}")
            return False
    
    def delete_pattern(self, pattern: str) -> bool:
        try:
            keys = self.client.keys(pattern)
            if keys:
                self.client.delete(*keys)
                logger.debug(f"Deleted cache keys matching pattern: {pattern}")
            return True
        except Exception as e:
            logger.error(f"Error deleting cache pattern {pattern}: {e}")
            return False
    
    def exists(self, key: str) -> bool:
        try:
            return self.client.exists(key)
        except Exception as e:
            logger.error(f"Error checking cache key {key}: {e}")
            return False


# Singleton instance
cache = RedisCache()


def get_cache() -> RedisCache:
    return cache
