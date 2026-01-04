"""Pydantic models for sandbox inspection results."""

from datetime import datetime, timedelta
from typing import Any, Literal

from pydantic import BaseModel, computed_field

SandboxState = Literal["running", "paused"]


class SandboxInfo(BaseModel):
    """Information about a sandbox instance."""

    sandbox_id: str
    template_id: str
    name: str | None = None
    metadata: dict[str, str] = {}
    state: SandboxState
    started_at: datetime
    end_at: datetime
    cpu_count: int
    memory_mb: int

    @computed_field
    @property
    def uptime(self) -> timedelta:
        """Time since sandbox was created."""
        return datetime.now(self.started_at.tzinfo) - self.started_at

    @computed_field
    @property
    def time_remaining(self) -> timedelta:
        """Time until sandbox times out."""
        remaining = self.end_at - datetime.now(self.end_at.tzinfo)
        return max(remaining, timedelta(0))


class SandboxMetrics(BaseModel):
    """Resource usage metrics for a sandbox."""

    cpu_count: int
    cpu_pct: float
    mem_total_mb: int
    mem_used_mb: int
    disk_total_mb: int
    disk_used_mb: int
    timestamp: datetime

    @computed_field
    @property
    def mem_pct(self) -> float:
        """Memory usage as percentage."""
        if self.mem_total_mb == 0:
            return 0.0
        return round((self.mem_used_mb / self.mem_total_mb) * 100, 1)

    @computed_field
    @property
    def disk_pct(self) -> float:
        """Disk usage as percentage."""
        if self.disk_total_mb == 0:
            return 0.0
        return round((self.disk_used_mb / self.disk_total_mb) * 100, 1)


class CommandResult(BaseModel):
    """Result of executing a bash command."""

    stdout: str
    stderr: str
    exit_code: int

    @property
    def success(self) -> bool:
        """True if command exited with code 0."""
        return self.exit_code == 0


class CodeResult(BaseModel):
    """Result of executing Python code."""

    stdout: str
    stderr: str
    error: str | None = None
    results: list[Any] = []

    @property
    def success(self) -> bool:
        """True if code executed without error."""
        return self.error is None


class FileInfo(BaseModel):
    """Information about a file or directory in a sandbox."""

    name: str
    path: str
    is_dir: bool
    size_bytes: int = 0


class Summary(BaseModel):
    """Overview summary of all sandboxes."""

    running_count: int
    paused_count: int
    total_count: int
    total_cpu: int
    total_memory_mb: int
    oldest_sandbox_id: str | None = None
    oldest_uptime: timedelta | None = None
    newest_sandbox_id: str | None = None
    newest_uptime: timedelta | None = None
