"""Persistent storage for the global runner approval mode."""

from __future__ import annotations

import datetime as dt
import json
import pathlib
import sys

from devops_runner.constants import VALID_AUTO_APPROVAL_MODES
from devops_runner.errors import RunnerError


def _utc_now() -> str:
    """Return the current UTC timestamp in a stable ISO format.

    This stays local instead of importing `audit.utc_now()` so the persistence
    layer remains independent from the audit module.
    """

    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0).isoformat()


class ApprovalModeStore:
    """Read and persist the global approval mode state file."""

    def __init__(self, path: pathlib.Path) -> None:
        """Initialize the store with the target state file path."""

        self.path = path

    def read_mode(self) -> str:
        """Return the persisted approval mode or `manual` on failure."""

        if not self.path.exists():
            return "manual"
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            print(
                f"warning: failed to read approval mode state file {self.path}: {exc}; falling back to manual",
                file=sys.stderr,
            )
            return "manual"
        mode = payload.get("mode")
        if mode not in VALID_AUTO_APPROVAL_MODES:
            print(
                f"warning: invalid approval mode '{mode}' in {self.path}; falling back to manual",
                file=sys.stderr,
            )
            return "manual"
        return mode

    def write_mode(self, mode: str) -> None:
        """Persist the selected approval mode atomically."""

        if mode not in VALID_AUTO_APPROVAL_MODES:
            raise RunnerError(f"unsupported approval mode: {mode}")
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = {
            "mode": mode,
            "updated_at": _utc_now(),
        }
        temp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        temp_path.replace(self.path)


__all__ = ["ApprovalModeStore"]
