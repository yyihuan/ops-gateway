"""Shared exception types for the runner package."""

from __future__ import annotations


class RunnerError(Exception):
    """Base exception for user-facing runner failures."""


class CommandFailure(RunnerError):
    """Raised when a reviewed command returns a non-zero exit status."""

    def __init__(self, step_id: str, phase: str, command_id: str, returncode: int) -> None:
        self.step_id = step_id
        self.phase = phase
        self.command_id = command_id
        self.returncode = returncode
        super().__init__(
            f"step={step_id} phase={phase} command={command_id} failed with code {returncode}"
        )


__all__ = ["CommandFailure", "RunnerError"]
