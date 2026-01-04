"""E2B Sandbox Inspector - Debug, monitor, and interact with running E2B sandboxes."""

from e2b_sandbox_inspector.async_client import AsyncSandboxInspector
from e2b_sandbox_inspector.schemas import (
    CodeResult,
    CommandResult,
    FileInfo,
    SandboxInfo,
    SandboxMetrics,
    SandboxState,
    Summary,
)
from e2b_sandbox_inspector.sync_client import SandboxInspector

__all__ = [
    # Clients
    "SandboxInspector",
    "AsyncSandboxInspector",
    # Schemas
    "SandboxInfo",
    "SandboxMetrics",
    "SandboxState",
    "CommandResult",
    "CodeResult",
    "FileInfo",
    "Summary",
]

__version__ = "0.1.0"
