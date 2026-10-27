"""Per-address request limits that slow password guessing, booking floods and chatbot overuse.

Counts are kept in this process's memory, so each API process limits on its own and a restart clears them.
"""

from collections import defaultdict, deque
from math import ceil
from threading import Lock
from time import monotonic

from fastapi import Depends, Request

from app.errors import TooManyRequestsError

# Addresses idle for longer than the longest window are forgotten.
LONGEST_WINDOW_SECONDS = 60 * 60
SWEEP_EVERY_HITS = 1000


class RateLimiter:
    def __init__(self) -> None:
        self._hits: defaultdict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()
        self._since_sweep = 0

    def hit(self, key: str, limit: int, window_seconds: int) -> None:
        """Count one request for `key`, or raise if it already made `limit` within the window."""
        now = monotonic()
        with self._lock:
            hits = self._hits[key]
            while hits and hits[0] <= now - window_seconds:
                hits.popleft()
            if len(hits) >= limit:
                raise TooManyRequestsError(retry_after=max(1, ceil(hits[0] + window_seconds - now)))
            hits.append(now)
            self._since_sweep += 1
            if self._since_sweep >= SWEEP_EVERY_HITS:
                self._sweep(now)

    def _sweep(self, now: float) -> None:
        self._since_sweep = 0
        for key in [key for key, hits in self._hits.items() if hits[-1] <= now - LONGEST_WINDOW_SECONDS]:
            del self._hits[key]


def rate_limit(name: str, limit: int, window_seconds: int):
    """A route dependency allowing each client address `limit` requests per `window_seconds`."""
    if window_seconds > LONGEST_WINDOW_SECONDS:
        raise ValueError("Rate limit windows cannot be longer than an hour.")

    def check(request: Request) -> None:
        limiter: RateLimiter | None = request.app.state.rate_limiter
        if limiter is None:
            return
        limiter.hit(f"{name}:{client_address(request)}", limit, window_seconds)

    return Depends(check)


def client_address(request: Request) -> str:
    """The visitor's address: from the CDN's header when one is configured, else from the connection."""
    header: str | None = request.app.state.client_address_header
    value = request.headers.get(header) if header else None
    if value:
        return value.strip()
    return request.client.host if request.client else "unknown"


LOGIN_LIMIT = rate_limit("login", 10, 5 * 60)
REGISTRATION_LIMIT = rate_limit("register", 5, 60 * 60)
GUEST_BOOKING_LIMIT = rate_limit("guest-booking", 10, 60 * 60)
GUEST_ACCESS_LIMIT = rate_limit("guest-access", 60, 10 * 60)
CHATBOT_LIMIT = rate_limit("chatbot", 15, 60)
