"""Small in-memory sliding-window rate limiter (per process). Adequate for a single-instance deployment."""
from __future__ import annotations

import threading
import time
from collections import defaultdict, deque

from fastapi import HTTPException, Request

_hits: dict[str, deque] = defaultdict(deque)
_lock = threading.Lock()


def rate_limit(name: str, limit: int, window_seconds: int):
    def dependency(request: Request) -> None:
        client = request.client.host if request.client else "unknown"
        key = f"{name}:{client}"
        now = time.monotonic()
        with _lock:
            q = _hits[key]
            while q and now - q[0] > window_seconds:
                q.popleft()
            if len(q) >= limit:
                raise HTTPException(status_code=429, detail="Too many requests; please wait and try again.",
                                    headers={"Retry-After": str(window_seconds)})
            q.append(now)

    return dependency


def reset() -> None:
    with _lock:
        _hits.clear()
