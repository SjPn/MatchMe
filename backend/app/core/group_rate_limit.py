"""Лимит сообщений в групповых чатах (in-memory, на процесс)."""

from __future__ import annotations

import time
from collections import deque
from threading import Lock

TTL_SEC = 60.0

_lock = Lock()
# user_id -> deque of monotonic timestamps
_events: dict[int, deque[float]] = {}


def allow_group_message(user_id: int, per_minute: int) -> bool:
    now = time.monotonic()
    with _lock:
        dq = _events.get(user_id)
        if dq is None:
            dq = deque()
            _events[user_id] = dq
        while dq and now - dq[0] > TTL_SEC:
            dq.popleft()
        if len(dq) >= per_minute:
            return False
        dq.append(now)
        return True
