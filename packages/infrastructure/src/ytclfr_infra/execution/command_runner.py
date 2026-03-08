"""Utilities for executing and validating external commands."""

import asyncio
from dataclasses import dataclass
from typing import Sequence

from ytclfr_core.errors.exceptions import ExternalCommandError


@dataclass(slots=True)
class CommandResult:
    """Result of an executed external command."""

    return_code: int
    stdout: str
    stderr: str


class CommandRunner:
    """Run external processes and enforce non-zero exit checks."""

    async def run(self, command: Sequence[str]) -> CommandResult:
        """Execute a command asynchronously and validate process status."""
        if not command:
            raise ExternalCommandError("Command cannot be empty.")
        process = await asyncio.create_subprocess_exec(
            *command,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        stdout_b, stderr_b = await process.communicate()
        result = CommandResult(
            return_code=process.returncode or 0,
            stdout=stdout_b.decode("utf-8", errors="replace"),
            stderr=stderr_b.decode("utf-8", errors="replace"),
        )
        if result.return_code != 0:
            raise ExternalCommandError(
                f"Command failed with code {result.return_code}: {' '.join(command)} | {result.stderr}"
            )
        return result

    def run_sync(self, command: Sequence[str]) -> CommandResult:
        """Execute the async runner from synchronous contexts."""
        try:
            return asyncio.run(self.run(command))
        except RuntimeError as exc:
            raise ExternalCommandError(
                "Cannot run sync command while an event loop is already running."
            ) from exc
