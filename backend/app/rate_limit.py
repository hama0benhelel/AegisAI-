from collections import deque
from math import ceil
from threading import Lock
from time import monotonic

from fastapi import HTTPException, Request

LIMIT = 10
WINDOW_SECONDS = 60
MAX_CLIENTS = 4096

_attempts = {}
_lock = Lock()


def reject(retry_after):
    raise HTTPException(
        status_code=429,
        detail="Trop de tentatives. Réessayez plus tard.",
        headers={"Retry-After": str(max(1, ceil(retry_after)))},
    )


def limit_login(request: Request):
    client = request.client.host if request.client else "unknown"

    with _lock:
        now = monotonic()
        cutoff = now - WINDOW_SECONDS

        if client not in _attempts:
            # Remove inactive clients; keep memory usage bounded.
            if len(_attempts) >= MAX_CLIENTS:
                stale = [
                    key for key, times in _attempts.items()
                    if not times or times[-1] <= cutoff
                ]
                for key in stale:
                    del _attempts[key]

            if len(_attempts) >= MAX_CLIENTS:
                reject(WINDOW_SECONDS)

            _attempts[client] = deque()

        times = _attempts[client]
        while times and times[0] <= cutoff:
            times.popleft()

        if len(times) >= LIMIT:
            reject(WINDOW_SECONDS - (now - times[0]))

        times.append(now)
