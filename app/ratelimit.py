"""Per-IP sliding-window rate limiting.

The public demo hands every request to a paid LLM, so an unmetered endpoint would
let a single visitor drain the Groq quota. This is deliberately in-memory: it costs
nothing, needs no Redis, and is sufficient for a single-instance demo deployment.
For multi-instance production you would swap the store for Redis.
"""

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request


class SlidingWindowLimiter:
    def __init__(self, max_requests: int, window_seconds: int):
        self.max_requests = max_requests
        self.window = window_seconds
        self._hits: defaultdict[str, deque[float]] = defaultdict(deque)
        self._lock = threading.Lock()

    def _prune(self, bucket: deque[float], now: float) -> None:
        cutoff = now - self.window
        while bucket and bucket[0] < cutoff:
            bucket.popleft()

    def check(self, key: str) -> tuple[bool, int]:
        """Return (allowed, seconds_until_retry)."""
        now = time.monotonic()
        with self._lock:
            bucket = self._hits[key]
            self._prune(bucket, now)

            if len(bucket) >= self.max_requests:
                retry_after = int(self.window - (now - bucket[0])) + 1
                return False, retry_after

            bucket.append(now)

            # Opportunistic cleanup so idle IPs do not accumulate forever.
            if len(self._hits) > 2048:
                for k in [k for k, v in self._hits.items() if not v]:
                    del self._hits[k]

            return True, 0


def client_ip(request: Request) -> str:
    """Real client IP behind a proxy — FastAPI Cloud terminates TLS upstream."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


def make_dependency(limiter: SlidingWindowLimiter):
    async def dependency(request: Request) -> None:
        allowed, retry_after = limiter.check(client_ip(request))
        if not allowed:
            raise HTTPException(
                status_code=429,
                detail=(
                    f"Rate limit reached ({limiter.max_requests} analyses per "
                    f"{limiter.window // 60} minutes). Try again in {retry_after}s — "
                    "or clone the repo and run it locally with your own API key."
                ),
                headers={"Retry-After": str(retry_after)},
            )

    return dependency
