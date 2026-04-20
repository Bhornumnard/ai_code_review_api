import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, status


class InMemoryRateLimiter:
    """In-memory sliding-window limiter keyed by API key.

    Important behavior:
    - Keeps timestamps for each key.
    - Drops hits older than 60 seconds.
    - Raises HTTP 429 when the key exceeds configured hits/minute.
    - Uses a lock to avoid race conditions in concurrent requests.
    """

    def __init__(self, limit_per_minute: int):
        """Create a limiter with a fixed request quota per minute."""
        self.limit_per_minute = limit_per_minute
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str, limit_per_minute: int | None = None) -> None:
        """Register one request for `key` and enforce the limit.

        If current window usage is already at the threshold, this method
        raises `HTTPException(429)` and the request should be rejected.
        """
        effective_limit = limit_per_minute or self.limit_per_minute
        now = time.time()
        window_start = now - 60
        with self._lock:
            bucket = self._hits[key]
            while bucket and bucket[0] < window_start:
                bucket.popleft()
            if len(bucket) >= effective_limit:
                raise HTTPException(
                    status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                    detail=f"Rate limit exceeded. Max {effective_limit} requests per minute.",
                )
            bucket.append(now)
