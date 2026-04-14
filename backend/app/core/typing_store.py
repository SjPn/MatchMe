"""Эфемерное состояние «печатает» для одного процесса API (без Redis)."""

from __future__ import annotations

import time
from threading import Lock

TTL_SEC = 4.0

_typing: dict[tuple[int, int], float] = {}
_lock = Lock()


def ping_typing(conversation_id: int, user_id: int) -> None:
    with _lock:
        _typing[(conversation_id, user_id)] = time.monotonic()


def other_users_typing(conversation_id: int, except_user_id: int) -> list[int]:
    now = time.monotonic()
    with _lock:
        stale = [k for k, t in _typing.items() if k[0] == conversation_id and now - t > TTL_SEC]
        for k in stale:
            del _typing[k]
        return [
            uid
            for (cid, uid), t in _typing.items()
            if cid == conversation_id and uid != except_user_id and now - t <= TTL_SEC
        ]
