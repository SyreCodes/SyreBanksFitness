import hashlib
import time
from collections import defaultdict
from threading import Lock

from redis.exceptions import RedisError

from app.core.config import get_settings
from app.core.exceptions import AppError
from app.core.redis_connection import redis_client


class RateLimiter:
    """Redis fixed windows; explicitly local process fallback only during development/tests."""
    def __init__(self) -> None:
        self.settings = get_settings()
        self.redis = redis_client(self.settings.redis_url, production=self.settings.production)
        self.key_prefix = "sbf:rate:"
        self.local: dict[str, tuple[int, float]] = defaultdict(lambda: (0, 0.0))
        self.lock = Lock()
        self.redis_unavailable_until = 0.0

    def check(self, key: str, limit: int = 10, seconds: int = 60) -> None:
        safe_key = self.key_prefix + hashlib.sha256(key.encode()).hexdigest()
        try:
            if not self.settings.production and time.monotonic() < self.redis_unavailable_until:
                raise RedisError("Development Redis circuit is temporarily open")
            # Lua makes INCR and first expiration indivisible across worker processes.
            count = int(self.redis.eval(
                "local n = redis.call('INCR', KEYS[1]); if n == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]); end; return n",
                1, safe_key, seconds,
            ))
        except RedisError as exc:
            if self.settings.production:
                raise AppError(503, "RATE_LIMIT_UNAVAILABLE", "Authentication is temporarily unavailable") from exc
            if time.monotonic() >= self.redis_unavailable_until:
                self.redis_unavailable_until = time.monotonic() + 15
            with self.lock:
                count, expires = self.local[safe_key]
                if expires < time.monotonic():
                    count, expires = 0, time.monotonic() + seconds
                count += 1
                self.local[safe_key] = (count, expires)
        if count > limit:
            raise AppError(429, "RATE_LIMITED", "Too many requests. Please try again later.")


limiter = RateLimiter()
