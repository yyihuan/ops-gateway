"""Audit logging helpers for runner events."""

from __future__ import annotations

import datetime as dt
import json
import pathlib
from collections.abc import Callable, Mapping
from typing import Any


def utc_now() -> str:
    """Return the current UTC time in the stable audit-log format."""

    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


class AuditLogger:
    """Write runner events to JSONL and fan them out to registered listeners."""

    def __init__(self, log_path: pathlib.Path, *, base_fields: Mapping[str, Any] | None = None) -> None:
        """Initialize an audit logger with stable per-run context fields."""

        self._log_path = log_path
        self._base_fields = dict(base_fields or {})
        self._listeners: list[Callable[[dict[str, Any]], None]] = []

    def add_listener(self, callback: Callable[[dict[str, Any]], None]) -> None:
        """Register a callback that receives every emitted payload."""

        self._listeners.append(callback)

    def log(self, event_type: str, **data: Any) -> dict[str, Any]:
        """Persist an event and notify registered listeners."""

        payload = {
            "ts": utc_now(),
            **self._base_fields,
            "event": event_type,
            **data,
        }
        with self._log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, ensure_ascii=False) + "\n")
        for listener in self._listeners:
            listener(payload)
        return payload


__all__ = ["AuditLogger", "utc_now"]
