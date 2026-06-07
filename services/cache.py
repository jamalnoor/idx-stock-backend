"""
Cache Service
Menggunakan Redis jika tersedia, fallback ke in-memory dict.
Railway menyediakan Redis add-on gratis.
"""

import os
import json
import time
import logging
from typing import Optional, Any

logger = logging.getLogger(__name__)


class CacheService:
    def __init__(self):
        self._redis = None
        self._memory: dict = {}  # {key: (value, expire_at)}
        self._try_connect_redis()

    def _try_connect_redis(self):
        redis_url = os.getenv("REDIS_URL") or os.getenv("REDIS_PRIVATE_URL")
        if not redis_url:
            logger.info("REDIS_URL tidak ada, pakai in-memory cache")
            return
        try:
            import redis
            self._redis = redis.from_url(redis_url, decode_responses=True)
            self._redis.ping()
            logger.info("Redis terhubung")
        except Exception as e:
            logger.warning(f"Redis gagal: {e} — pakai in-memory")
            self._redis = None

    def get(self, key: str) -> Optional[Any]:
        if self._redis:
            try:
                val = self._redis.get(key)
                return json.loads(val) if val else None
            except Exception:
                pass

        entry = self._memory.get(key)
        if entry:
            val, exp = entry
            if time.time() < exp:
                return val
            del self._memory[key]
        return None

    def set(self, key: str, value: Any, ttl: int = 300):
        if self._redis:
            try:
                self._redis.setex(key, ttl, json.dumps(value))
                return
            except Exception:
                pass

        self._memory[key] = (value, time.time() + ttl)

    def delete(self, key: str):
        if self._redis:
            try:
                self._redis.delete(key)
            except Exception:
                pass
        self._memory.pop(key, None)
