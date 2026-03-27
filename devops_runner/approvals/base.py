"""Abstract interfaces for runner approval backends."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from devops_runner.errors import CommandFailure


class ApprovalBackend(ABC):
    """Shared interface implemented by all approval backends."""

    def start(self) -> None:
        """Start any backend-specific resources."""

        return None

    def stop(self) -> None:
        """Stop any backend-specific resources."""

        return None

    def on_event(self, payload: dict[str, Any]) -> None:
        """Receive audit events emitted during plan execution."""

        return None

    @abstractmethod
    def approve_step(self, step_index: int) -> dict[str, Any] | None:
        """Return the approved step payload or `None` when rejected."""

    @abstractmethod
    def prompt_rollback(self, step: dict[str, Any], error: CommandFailure) -> None:
        """Handle rollback approval after a failed step."""


__all__ = ["ApprovalBackend"]
